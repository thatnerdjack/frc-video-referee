"""Automatic storage management for the HyperDeck's media.

Over a long event the HyperDeck's media fills up with match recordings, and once it is
full the deck can no longer record. This module reclaims space by deleting (and
optionally first offloading) old clips over FTP.

The work is deliberately queued rather than performed as soon as the disk gets tight.
File operations against the deck must never compete with a match recording, so the queue
is only drained during genuine downtime: the controller idle, the arena sitting in
PRE_MATCH without being ready to start, and all of that having been true for a settling
period. Anything in flight is abandoned the moment the field goes hot.
"""

import asyncio
import logging
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, NamedTuple, Protocol, Set

from pydantic import BaseModel

from frc_video_referee.cheesy_arena.client import ArenaNotifier, CheesyArenaClient
from frc_video_referee.cheesy_arena.model import MatchState
from frc_video_referee.db import DB
from frc_video_referee.hyperdeck.client import HyperdeckClient, HyperdeckNotifier
from frc_video_referee.hyperdeck.ftp import (
    HyperdeckFTPClient,
    HyperdeckFTPSettings,
    TransferAborted,
)
from frc_video_referee.hyperdeck.model import TransportMode
from frc_video_referee.web import WebsocketManager
from frc_video_referee.web.model import StorageState, StorageStatus

logger = logging.getLogger(__name__)

STORAGE_STATUS_EVENT = "storage_status"
"""Event name used on the websocket interface"""

QUEUE_REBUILD_INTERVAL = 30.0
"""Seconds between re-evaluations of the queue from within the main loop.

The deck pushes its disk usage over the websocket, but relying on those events alone
would leave the queue unbuilt whenever space runs low without one arriving.
"""


class StorageSettings(BaseModel, use_attribute_docstrings=True):
    """Settings for automatic management of the HyperDeck's storage"""

    enabled: bool = True
    """Whether to automatically reclaim space on the HyperDeck as it fills up"""

    low_space_threshold: float = 2700.0
    """Reclaim space once remaining record time falls below this many seconds"""

    target_record_time: float = 5400.0
    """Stop reclaiming space once remaining record time reaches this many seconds"""

    quiet_period: float = 20.0
    """Seconds of continuous downtime required before storage work may begin"""

    poll_interval: float = 2.0
    """Seconds between checks for an available downtime window"""

    min_matches_retained: int = 8
    """Never delete the clips for this many most recent matches, regardless of space"""

    offload_path: Path | None = None
    """Optional local folder to copy clips into before deleting them from the HyperDeck"""

    dry_run: bool = False
    """Log the files that would be reclaimed without actually offloading or deleting them"""

    max_attempts: int = 3
    """Give up on a file after this many failed attempts so one bad file cannot block the queue"""

    ftp: HyperdeckFTPSettings = HyperdeckFTPSettings()
    """Settings for the HyperDeck's FTP server, used for all file operations"""


class StorageActivity(NamedTuple):
    """A snapshot of what the controller is doing, used to gate storage work"""

    idle: bool
    """True when the controller is neither recording nor reviewing a match"""
    protected_match_ids: Set[str]
    """Matches that must not have their clips reclaimed right now"""


BUSY_ACTIVITY = StorageActivity(idle=False, protected_match_ids=set())
"""Conservative default used before a host is registered: never act."""


class StorageHost(Protocol):
    """The parts of the controller that storage management depends on.

    Declared structurally so that this module does not import the controller, keeping
    the dependency one-directional.
    """

    def get_storage_activity(self) -> StorageActivity: ...

    async def record_clip_reclaimed(
        self, var_id: str, archive_path: str | None
    ) -> None: ...


class StorageError(Exception):
    """A storage management operation could not be completed."""


class StorageTask(NamedTuple):
    """A single queued file reclamation"""

    file_path: str
    """Path of the clip on the deck's media, as reported by the control API"""
    file_size: int
    """Size of the clip in bytes"""
    var_id: str | None
    """The recorded match this clip belongs to, or None for an orphan clip"""
    description: str
    """Human-readable description used in logs and the UI"""


class StorageManager:
    """Queues and performs HyperDeck storage reclamation during downtime."""

    def __init__(
        self,
        settings: StorageSettings,
        hyperdeck: HyperdeckClient,
        hyperdeck_address: str,
        arena: CheesyArenaClient,
        db: DB,
        websocket: WebsocketManager,
    ):
        self._settings = settings
        self._hyperdeck = hyperdeck
        self._arena = arena
        self._db = db
        self._websocket = websocket

        # The control API address carries an HTTP port which does not apply to FTP
        host = (
            hyperdeck_address.rsplit(":", 1)[0]
            if ":" in hyperdeck_address
            else hyperdeck_address
        )
        self._ftp = HyperdeckFTPClient(host, settings.ftp)

        self._host: StorageHost | None = None
        self._queue: Deque[StorageTask] = deque()
        self._abort = asyncio.Event()
        self._quiet_since: float | None = None
        self._processing = False
        self._triggered = False
        self._state = StorageState.DISABLED if not settings.enabled else StorageState.OK
        self._last_error: str | None = None
        self._attempts: Dict[str, int] = {}
        self._ftp_root: str | None = None
        self._last_rebuild = 0.0

        self._hyperdeck.subscribe(
            HyperdeckNotifier.DISK_SPACE_UPDATED, self._handle_disk_space_update
        )
        # Both of these mean the field is going hot; anything in flight must stop now
        self._arena.subscribe(
            ArenaNotifier.ARENA_READY_TO_START, self._handle_field_hot
        )
        self._arena.subscribe(ArenaNotifier.MATCH_STARTED, self._handle_field_hot)

        self._websocket.add_event_type(
            STORAGE_STATUS_EVENT, self._get_storage_status_event
        )

    def set_host(self, host: StorageHost) -> None:
        """Register the controller that storage work is gated on."""
        self._host = host

    def _activity(self) -> StorageActivity:
        if self._host is None:
            return BUSY_ACTIVITY
        return self._host.get_storage_activity()

    #####################
    # Downtime gating   #
    #####################

    def _downtime_available(self) -> bool:
        """Whether it is currently safe to perform file operations on the deck."""
        if not self._activity().idle:
            return False
        if self._arena.match_time.match_state != MatchState.PRE_MATCH:
            return False
        if self._arena.arena_status.can_start_match:
            return False
        if not self._hyperdeck.connected:
            return False
        if self._hyperdeck.transport_mode == TransportMode.InputRecord:
            return False
        return True

    async def _handle_field_hot(self) -> None:
        """Abandon any in-progress storage work because a match is imminent."""
        self._quiet_since = None
        if not self._abort.is_set():
            self._abort.set()
            if self._processing:
                logger.info("Field is going hot, aborting in-progress storage work")

    ####################
    # Queue management #
    ####################

    async def _handle_disk_space_update(self) -> None:
        """Re-evaluate the storage situation whenever the deck reports its disk usage."""
        if not self._settings.enabled or self._processing:
            return
        self._rebuild_queue()
        self._last_rebuild = time.monotonic()
        await self._update_state()

    def _estimate_bytes_per_second(self) -> float:
        """Estimate the recording bitrate so freed bytes can be converted to record time."""
        # Deriving this from an existing clip stays valid even when the disk is full,
        # unlike dividing the remaining space by the remaining record time
        for clip in self._hyperdeck.all_clips.values():
            frame_rate = clip.videoFormat.frameRate
            if frame_rate <= 0 or clip.frameCount <= 0 or clip.fileSize <= 0:
                continue
            return clip.fileSize / (clip.frameCount / frame_rate)

        entry = self._hyperdeck.get_active_working_set()
        if entry.remainingRecordTime > 0:
            return entry.remainingSpace / entry.remainingRecordTime
        return 0.0

    def _build_candidates(self) -> List[StorageTask]:
        """List the clips eligible for reclamation, most expendable first."""
        activity = self._activity()
        matches = self._db.load_all_matches()
        clips = self._hyperdeck.all_clips
        claimed = {m.clip_id for m in matches.values() if m.clip_id is not None}

        candidates: List[StorageTask] = []

        # Orphan clips first: present on the deck but belonging to no recorded match, so
        # nothing in the VAR system can ever want to play them back. Clip IDs increase
        # over time, so ascending order is oldest first.
        for clip_id in sorted(clips):
            if clip_id in claimed:
                continue
            clip = clips[clip_id]
            candidates.append(
                StorageTask(
                    file_path=clip.filePath,
                    file_size=clip.fileSize,
                    var_id=None,
                    description=f"orphan clip {clip.filePath}",
                )
            )

        # Then committed matches, oldest first
        ordered = sorted(matches.values(), key=lambda m: m.match_start_timestamp)
        retained: Set[str] = set()
        if self._settings.min_matches_retained > 0:
            retained = {
                m.var_id for m in ordered[-self._settings.min_matches_retained :]
            }

        for match in ordered:
            if match.var_id in retained:
                continue
            if match.var_id in activity.protected_match_ids:
                continue
            if match.clip_deleted or match.clip_id is None:
                continue
            clip = clips.get(match.clip_id)
            if clip is None:
                # Already gone from the deck
                continue
            # Only reclaim matches whose scores the scorekeeper has already committed
            arena_match = self._arena.match_results.get(match.arena_id)
            if arena_match is None or arena_match.result is None:
                continue
            candidates.append(
                StorageTask(
                    file_path=clip.filePath,
                    file_size=clip.fileSize,
                    var_id=match.var_id,
                    description=f"match {match.var_id}",
                )
            )

        return candidates

    def _rebuild_queue(self) -> None:
        """Recompute the work queue from live deck and match state.

        The queue is rebuilt from scratch rather than persisted so that it can never
        act on stale information about what is on the deck.
        """
        entry = self._hyperdeck.get_active_working_set()
        headroom = entry.remainingRecordTime

        if headroom < self._settings.low_space_threshold:
            if not self._triggered:
                logger.info(
                    f"HyperDeck storage is low ({headroom}s of record time remaining), "
                    f"queueing cleanup work"
                )
            self._triggered = True
        elif headroom >= self._settings.target_record_time:
            if self._triggered:
                logger.info(
                    f"HyperDeck storage has recovered ({headroom}s of record time remaining)"
                )
            self._triggered = False
            self._queue.clear()

        if not self._triggered:
            return

        needed_seconds = max(0.0, self._settings.target_record_time - headroom)
        rate = self._estimate_bytes_per_second()
        needed_bytes = needed_seconds * rate

        queue: Deque[StorageTask] = deque()
        freed = 0
        for candidate in self._build_candidates():
            if (
                self._attempts.get(candidate.file_path, 0)
                >= self._settings.max_attempts
            ):
                continue
            queue.append(candidate)
            freed += candidate.file_size
            if needed_bytes > 0:
                if freed >= needed_bytes:
                    break
            elif queue:
                # Without a usable bitrate estimate, reclaim one file at a time and
                # re-evaluate against real numbers after each deletion
                break

        if len(queue) != len(self._queue):
            logger.info(f"Storage cleanup queue now holds {len(queue)} item(s)")
        self._queue = queue

    ##################
    # Task execution #
    ##################

    async def _resolve_ftp_root(self) -> str:
        """Find the FTP directory corresponding to the deck's active media volume."""
        if self._settings.ftp.root is not None:
            return self._settings.ftp.root
        if self._ftp_root is not None:
            return self._ftp_root

        volume = self._hyperdeck.get_active_working_set().volume
        directories = await self._ftp.list_directories()
        for directory in directories:
            if directory.strip("/") == volume:
                self._ftp_root = directory.strip("/")
                logger.info(
                    f"Resolved HyperDeck FTP root for clips to '{self._ftp_root}'"
                )
                return self._ftp_root

        # Never guess at a directory when the consequence is deleting the wrong files
        raise StorageError(
            f"Could not find an FTP directory matching the active volume '{volume}' "
            f"(found: {directories}). Set storage.ftp.root to specify it explicitly."
        )

    async def _execute_task(self, task: StorageTask) -> None:
        """Offload (if configured) and then delete a single clip."""
        if self._abort.is_set():
            raise TransferAborted("Aborted before starting")

        root = await self._resolve_ftp_root()
        remote_path = f"/{root}/{task.file_path}"
        archive_path: str | None = None

        if self._settings.offload_path is not None:
            local_path = self._settings.offload_path / Path(task.file_path).name
            if self._settings.dry_run:
                logger.info(f"[dry run] Would offload {remote_path} to {local_path}")
            else:
                logger.info(f"Offloading {remote_path} to {local_path}")
                written = await self._ftp.download(remote_path, local_path, self._abort)
                # Never delete from the deck unless the archive is verifiably complete
                if task.file_size > 0 and written != task.file_size:
                    local_path.unlink(missing_ok=True)
                    raise StorageError(
                        f"Offload of {remote_path} wrote {written} bytes, "
                        f"expected {task.file_size}"
                    )
                logger.info(f"Offloaded {task.description} ({written} bytes)")
            archive_path = str(local_path)

        if self._settings.dry_run:
            logger.info(f"[dry run] Would delete {remote_path} ({task.description})")
            return

        await self._ftp.delete(remote_path)
        logger.info(f"Reclaimed storage from {task.description}")

        # Refresh our view of the deck so the next evaluation uses real numbers
        await self._hyperdeck.refresh_clip_list()
        await self._hyperdeck.refresh_working_set()

        if task.var_id is not None and self._host is not None:
            await self._host.record_clip_reclaimed(task.var_id, archive_path)

    async def _process_next_task(self) -> None:
        """Run the task at the head of the queue, retrying or dropping it on failure."""
        task = self._queue[0]
        self._processing = True
        await self._update_state()
        try:
            await self._execute_task(task)
        except TransferAborted as e:
            # Expected whenever a match is about to start; keep the task for next time
            logger.info(f"Storage work on {task.description} interrupted: {e}")
        except Exception as e:
            attempts = self._attempts.get(task.file_path, 0) + 1
            self._attempts[task.file_path] = attempts
            self._last_error = f"{task.description}: {e}"
            if attempts >= self._settings.max_attempts:
                logger.error(
                    f"Giving up on {task.description} after {attempts} attempts: {e}"
                )
                self._queue.popleft()
            else:
                logger.warning(
                    f"Storage work on {task.description} failed "
                    f"(attempt {attempts}/{self._settings.max_attempts}): {e}"
                )
        else:
            self._last_error = None
            self._attempts.pop(task.file_path, None)
            self._queue.popleft()
        finally:
            self._processing = False
            await self._update_state()

    ############
    # Main loop #
    ############

    async def run(self) -> None:
        """Drain the storage cleanup queue whenever the field is quiet."""
        if not self._settings.enabled:
            logger.info("Automatic HyperDeck storage management is disabled")
            return

        logger.info(
            f"Starting HyperDeck storage management "
            f"(cleanup below {self._settings.low_space_threshold}s of record time, "
            f"target {self._settings.target_record_time}s"
            f"{', dry run' if self._settings.dry_run else ''})"
        )

        while True:
            await asyncio.sleep(self._settings.poll_interval)
            try:
                await self._tick()
            except Exception as e:
                logger.exception(f"Error in storage management loop: {e}")

    async def _tick(self) -> None:
        if not self._downtime_available():
            if self._quiet_since is not None:
                logger.debug("Downtime window closed, pausing storage work")
                self._quiet_since = None
            self._abort.set()
            await self._update_state()
            return

        self._abort.clear()

        now = time.monotonic()
        if self._quiet_since is None:
            self._quiet_since = now
            return
        if now - self._quiet_since < self._settings.quiet_period:
            return

        if not self._queue and now - self._last_rebuild >= QUEUE_REBUILD_INTERVAL:
            self._rebuild_queue()
            self._last_rebuild = now

        if not self._queue:
            await self._update_state()
            return

        await self._process_next_task()

    ##############
    # UI status  #
    ##############

    def _compute_state(self) -> StorageState:
        if not self._settings.enabled:
            return StorageState.DISABLED
        if self._processing:
            return StorageState.CLEANING
        if self._last_error is not None:
            return StorageState.ERROR
        if self._queue:
            return StorageState.PENDING
        return StorageState.OK

    async def _update_state(self) -> None:
        state = self._compute_state()
        if state == self._state:
            return
        logger.debug(f"Storage state change from {self._state.value} to {state.value}")
        self._state = state
        await self._websocket.notify(STORAGE_STATUS_EVENT)

    def _get_storage_status_event(self) -> dict:
        return StorageStatus(
            state=self._state,
            pending_items=len(self._queue),
            offload_enabled=self._settings.offload_path is not None,
            last_error=self._last_error,
        ).model_dump()
