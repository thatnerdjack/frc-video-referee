import asyncio
import enum
import logging
import re
from datetime import datetime
from typing import List, Set
import uuid

from pydantic import BaseModel
from frc_video_referee import db
from frc_video_referee.cheesy_arena.model import Foul
from frc_video_referee.db.model import (
    Alliance,
    MatchEvent,
    MatchEventType,
    RecordedMatch,
)
from frc_video_referee.hyperdeck.client import HyperdeckClient, HyperdeckNotifier
from frc_video_referee.cheesy_arena.client import ArenaNotifier, CheesyArenaClient
from frc_video_referee.hyperdeck.model import PlaybackType
from frc_video_referee.storage import StorageActivity
from frc_video_referee.model import (
    AddVARReviewCommand,
    ExitReviewCommand,
    LoadMatchCommand,
    UpdateEventCommand,
    WarpToTimeCommand,
)
from frc_video_referee.web import WebsocketManager
from frc_video_referee.web.model import (
    ControllerStatus,
    HyperdeckStatus,
    MatchListEntry,
)

logger = logging.getLogger(__name__)

# Event names used on the websocket interface
CONTROLLER_STATUS_EVENT = "controller_status"
MATCH_TIMING_EVENT = "match_timing"
CURRENT_MATCH_DATA_EVENT = "current_match_data"
CURRENT_MATCH_TIME_EVENT = "current_match_time"
REALTIME_SCORE_EVENT = "realtime_score"
MATCH_LIST_EVENT = "match_list"
ARENA_CONNECTION_EVENT = "arena_connection"
HYPERDECK_CONNECTION_EVENT = "hyperdeck_connection"
HYPERDECK_STATUS_EVENT = "hyperdeck_status"


class VARSettings(BaseModel):
    """Settings for the VAR controller"""

    auto_scoring_delay: float = 3.0
    """Delay in seconds after AUTO ends before scoring is evaluated"""

    endgame_scoring_delay: float = 3.0
    """Delay in seconds after the match ends before scoring is evaluated"""

    recording_extra_time: float = 2.0
    """Extra time in seconds after endgame scoring to keep the recording running"""

    match_number_digits: int = 2
    """Minimum number of digits to use for match numbers in recording filenames"""

    var_review_backdate_time: float = 0.0
    """Amount of time to backdate VAR review button presses during a match"""


class ControllerState(enum.Enum):
    Idle = enum.auto()
    """No recording or playback in progress, showing live camera feed"""
    Recording = enum.auto()
    """Currently recording a match"""
    ReviewingCurrentMatch = enum.auto()
    """Reviewing the current match that was just recorded but has not been committed"""
    ReviewingHistoricalMatch = enum.auto()
    """Reviewing a historical match that was previously recorded and committed"""


class VARController:
    """Main controller and business logic for the Video Assistant Referee (VAR) system"""

    def __init__(
        self,
        settings: VARSettings,
        arena: CheesyArenaClient,
        hyperdeck: HyperdeckClient,
        websocket: WebsocketManager,
        db: db.DB,
    ):
        self._settings = settings
        self._arena = arena
        self._hyperdeck = hyperdeck
        self._websocket = websocket
        self._db = db

        self._lock = asyncio.Lock()
        self._state = ControllerState.Idle
        self._matches = {
            id: MatchListEntry(var_data=match)
            for id, match in db.load_all_matches().items()
        }
        self._current_match: MatchListEntry | None = None

        # Register callbacks for events that the controller is interested in
        arena_subscriptions = [
            # Match lifecycle events
            (ArenaNotifier.ARENA_READY_TO_START, self._handle_arena_ready_to_start),
            (ArenaNotifier.MATCH_STARTED, self._handle_match_start),
            (ArenaNotifier.AUTO_PERIOD_ENDED, self._handle_auto_period_end),
            (ArenaNotifier.MATCH_ENDED, self._handle_match_end),
            (ArenaNotifier.MATCH_COMMITTED_OR_DISCARDED, self._handle_match_commit),
            # UI data update notifications
            (
                ArenaNotifier.CONNECTION_STATE_UPDATED,
                self._handle_arena_connection_state_update,
            ),
            (
                ArenaNotifier.HISTORICAL_SCORES_UPDATED,
                self._handle_historical_scores_update,
            ),
            (
                ArenaNotifier.REALTIME_SCORE_UPDATED,
                self._handle_realtime_score_update,
            ),
            (
                ArenaNotifier.MATCH_TIMING_UPDATED,
                self._handle_match_timing_update,
            ),
            (
                ArenaNotifier.MATCH_TIME_UPDATED,
                self._handle_match_time_update,
            ),
            (
                ArenaNotifier.MATCH_DATA_UPDATED,
                self._handle_match_data_update,
            ),
        ]
        for event, handler in arena_subscriptions:
            self._arena.subscribe(event, handler)

        hyperdeck_subscriptions = [
            # UI data update notifications
            (
                HyperdeckNotifier.CONNECTION_STATE_UPDATED,
                self._handle_hyperdeck_connection_state_update,
            ),
            (
                HyperdeckNotifier.TRANSPORT_MODE_UPDATED,
                self._handle_hyperdeck_transport_mode_update,
            ),
            (
                HyperdeckNotifier.PLAYBACK_STATE_UPDATED,
                self._handle_hyperdeck_playback_state_update,
            ),
            (
                HyperdeckNotifier.CLIP_LIST_UPDATED,
                self._handle_hyperdeck_clip_list_update,
            ),
            (
                HyperdeckNotifier.DISK_SPACE_UPDATED,
                self._handle_hyperdeck_disk_space_update,
            ),
        ]
        for event, handler in hyperdeck_subscriptions:
            self._hyperdeck.subscribe(event, handler)

        self._websocket.add_event_type(
            CONTROLLER_STATUS_EVENT, self._get_controller_status_event
        )
        self._websocket.add_event_type(
            MATCH_LIST_EVENT,
            lambda: {id: match.model_dump() for id, match in self._matches.items()},
        )
        self._websocket.add_event_type(
            MATCH_TIMING_EVENT,
            lambda: self._arena.match_timing.model_dump(),
        )
        self._websocket.add_event_type(
            CURRENT_MATCH_TIME_EVENT,
            lambda: self._arena.match_time.model_dump(),
        )
        self._websocket.add_event_type(
            CURRENT_MATCH_DATA_EVENT,
            lambda: self._arena.match_data.match_info.model_dump(),
        )
        self._websocket.add_event_type(
            REALTIME_SCORE_EVENT,
            lambda: self._arena.realtime_score.model_dump(),
        )
        self._websocket.add_event_type(
            ARENA_CONNECTION_EVENT, lambda: {"connected": self._arena.connected}
        )
        self._websocket.add_event_type(
            HYPERDECK_CONNECTION_EVENT, lambda: {"connected": self._hyperdeck.connected}
        )
        self._websocket.add_event_type(
            HYPERDECK_STATUS_EVENT, self._get_hyperdeck_status_event
        )

        self._websocket.add_command_handler(
            "load_match",
            LoadMatchCommand,
            self._handle_load_match_command,
        )
        self._websocket.add_command_handler(
            "warp_to_time",
            WarpToTimeCommand,
            self._handle_warp_to_time_command,
        )
        self._websocket.add_command_handler(
            "add_var_review",
            AddVARReviewCommand,
            self._handle_add_var_review_command,
        )
        self._websocket.add_command_handler(
            "exit_review",
            ExitReviewCommand,
            self._handle_exit_review_command,
        )
        self._websocket.add_command_handler(
            "update_event",
            UpdateEventCommand,
            self._handle_update_event_command,
        )

        self._refresh_hyperdeck_clip_presence()
        self._refresh_arena_match_data()

    #########################################
    # Helpers for managing controller state #
    #########################################

    def _set_state(self, state: ControllerState):
        """Set the current state of the controller."""
        if self._state == state:
            return
        logger.info(f"Controller state change from {self._state.name} to {state.name}")
        self._state = state

    def _create_id_for_current_match(self) -> str:
        """Generate an ID for the current match based on arena data."""
        arena_match = self._arena.match_data
        match_base_name = arena_match.match_info.short_name

        # Pad numbers in the match name to at least N digits for better alphabetization
        # Examples with 2 digits: "Q1" -> "Q01", "Q12" -> "Q12", "P3" -> "P03", "SF1" -> "SF01"
        match_base_name = re.sub(
            r"(\d+)",
            lambda m: m.group(1).zfill(self._settings.match_number_digits),
            match_base_name,
        )

        if arena_match.is_replay:
            match_base_name += "_replay"

        match_id = match_base_name
        match_seqnum = 0
        while match_id in self._matches:
            match_seqnum += 1
            match_id = f"{match_base_name}_{match_seqnum}"

        return match_id

    def _create_event_id(self) -> str:
        return uuid.uuid4().hex

    def _get_current_match_time(self) -> float:
        """Get the current match time in seconds."""
        if self._current_match is None:
            return 0.0
        # TODO: Clean this up to anchor events to match start rather than recorder start
        time_seconds = (
            datetime.now().astimezone()
            - self._current_match.var_data.recording_start_timestamp
        ).total_seconds()
        return max(0.0, time_seconds)

    async def _save_and_unload_current_match(self, update_hyperdeck: bool = True):
        """Save the current match to the database and unload it."""
        if self._current_match:
            logger.debug(f"Unloading match {self._current_match.var_data.var_id}")
            if self._state == ControllerState.Recording:
                if update_hyperdeck:
                    await self._hyperdeck.stop_recording()
                self._set_state(ControllerState.Idle)
                await self._websocket.notify(CONTROLLER_STATUS_EVENT)
            self._matches[self._current_match.var_data.var_id] = self._current_match
            self._db.save_match(self._current_match.var_data)
            self._current_match = None
            if update_hyperdeck:
                await self._hyperdeck.show_live_view()

    def _add_match_event(self, event: MatchEvent):
        """Add an event to the current match."""
        if self._current_match is None:
            logger.warning("No current match to add event to")
            return

        logger.info(
            f"Match {self._current_match.var_data.var_id}: {event.event_type.value} event at {event.time}"
        )

        self._current_match.var_data.events.append(event)
        self._db.save_match(self._current_match.var_data)

    async def _finalize_match_recording(self):
        """Finalize the current match recording."""
        async with self._lock:
            if self._state != ControllerState.Recording:
                logger.debug("Not in recording state, nothing to finalize")
                return

            assert self._current_match is not None, "No current match to finalize"
            logger.info(
                f"Match {self._current_match.var_data.var_id} ended, stopping recording"
            )

            clip_id = await self._hyperdeck.stop_recording()
            self._current_match.var_data.clip_id = clip_id
            self._current_match.clip_available = self._hyperdeck.has_playable_clip(
                clip_id
            )
            self._db.save_match(self._current_match.var_data)
            await self._websocket.notify(MATCH_LIST_EVENT)
            self._set_state(ControllerState.ReviewingCurrentMatch)
            await self._websocket.notify(CONTROLLER_STATUS_EVENT)

            auto_end_event = None
            for event in self._current_match.var_data.events:
                if event.event_type == MatchEventType.AUTO_SCORING:
                    auto_end_event = event
                    break
            time_to_display = auto_end_event.time if auto_end_event else 0.0
            await self._hyperdeck.warp_to_clip(clip_id, time_to_display)

    def get_storage_activity(self) -> StorageActivity:
        """Report what the controller is doing so storage work can be gated on it.

        Consumed by the StorageManager, which must not touch files on the deck while a
        match is being recorded or reviewed.
        """
        protected_match_ids: Set[str] = set()
        if self._current_match is not None:
            protected_match_ids.add(self._current_match.var_data.var_id)
        return StorageActivity(
            idle=self._state == ControllerState.Idle,
            protected_match_ids=protected_match_ids,
        )

    async def record_clip_reclaimed(
        self, var_id: str, archive_path: str | None
    ) -> None:
        """Record that a match's clip has been removed from the HyperDeck.

        The controller is the only writer of match records, so storage management routes
        this through here rather than writing to the database itself.
        """
        async with self._lock:
            match_entry = self._matches.get(var_id)
            if match_entry is None:
                logger.warning(f"Reclaimed clip for unknown match {var_id}")
                return

            match_entry.var_data.clip_deleted = True
            match_entry.var_data.archive_path = archive_path
            match_entry.clip_available = False
            self._db.save_match(match_entry.var_data)
            logger.info(
                f"Match {var_id} clip reclaimed from the HyperDeck"
                + (f", archived to {archive_path}" if archive_path else "")
            )
            await self._websocket.notify(MATCH_LIST_EVENT)

    def _refresh_hyperdeck_clip_presence(self):
        for var_match in self._matches.values():
            clip_id = var_match.var_data.clip_id
            var_match.clip_available = (
                clip_id is not None and self._hyperdeck.has_playable_clip(clip_id)
            )

    def _refresh_arena_match_data(self):
        for var_match in self._matches.values():
            var_match.arena_data = self._arena.match_results.get(
                var_match.var_data.arena_id
            )

    async def _check_for_foul_changes(self):
        """Check if any fouls have been added or changed in the realtime score."""
        async with self._lock:
            if self._state != ControllerState.Recording or self._current_match is None:
                return

            current_fouls = {
                event.arena_foul_id: event
                for event in self._current_match.var_data.events
                if event.arena_foul_id is not None
            }

            def find_team_idx(team_id: int, alliance: Alliance) -> int | None:
                if self._current_match is None or team_id == 0:
                    return None
                teams = self._current_match.var_data.teams[alliance]
                try:
                    return teams.index(team_id)
                except ValueError:
                    return None

            red_fouls = self._arena.realtime_score.red.score.fouls or []
            blue_fouls = self._arena.realtime_score.blue.score.fouls or []

            made_change = False

            def process_foul_list(foul_list: List[Foul], alliance: Alliance):
                nonlocal current_fouls
                nonlocal made_change

                for foul in foul_list:
                    if foul.foul_id is None:
                        # Compatibility check for CA versions that don't have FoulId
                        continue
                    if foul.foul_id not in current_fouls:
                        event_type = (
                            MatchEventType.MAJOR_FOUL
                            if foul.is_major
                            else MatchEventType.MINOR_FOUL
                        )
                        team_idx = find_team_idx(foul.team_id, alliance)
                        event = MatchEvent(
                            event_id=self._create_event_id(),
                            event_type=event_type,
                            time=self._get_current_match_time(),
                            alliance=alliance,
                            team_idx=team_idx,
                            arena_foul_id=foul.foul_id,
                        )
                        self._add_match_event(event)
                        made_change = True
                    else:
                        # Check if any changes have occurred to this foul
                        existing_foul = current_fouls[foul.foul_id]

                        # Foul type changes
                        expected_event_type = (
                            MatchEventType.MAJOR_FOUL
                            if foul.is_major
                            else MatchEventType.MINOR_FOUL
                        )
                        if existing_foul.event_type != expected_event_type:
                            existing_foul.event_type = expected_event_type
                            made_change = True

                        # Team changes
                        expected_team_idx = find_team_idx(foul.team_id, alliance)
                        if existing_foul.team_idx != expected_team_idx:
                            existing_foul.team_idx = expected_team_idx
                            made_change = True

            process_foul_list(red_fouls, Alliance.RED)
            process_foul_list(blue_fouls, Alliance.BLUE)

            if made_change:
                self._db.save_match(self._current_match.var_data)
                await self._websocket.notify(MATCH_LIST_EVENT)

    #######################################
    # Handlers for match lifecycle events #
    #######################################

    async def _handle_arena_ready_to_start(self):
        """Handle a notification that the arena is now ready for match start"""
        pass

    async def _handle_match_start(self):
        """Handle a notification that a match has started"""
        async with self._lock:
            match_timestamp = datetime.now().astimezone()
            await self._save_and_unload_current_match(update_hyperdeck=False)
            self._set_state(ControllerState.Recording)

            match_id = self._create_id_for_current_match()

            recording_name = match_id
            clip_id = await self._hyperdeck.start_recording(recording_name)
            logger.debug(f"HyperDeck clip ID: {clip_id} with filename {recording_name}")

            recording_timestamp = datetime.now().astimezone()
            logger.info(
                f"Started recording of match {match_id} at {recording_timestamp.isoformat()}"
            )

            match_teams = {
                Alliance.RED: [
                    self._arena.match_data.match_info.red1,
                    self._arena.match_data.match_info.red2,
                    self._arena.match_data.match_info.red3,
                ],
                Alliance.BLUE: [
                    self._arena.match_data.match_info.blue1,
                    self._arena.match_data.match_info.blue2,
                    self._arena.match_data.match_info.blue3,
                ],
            }

            self._current_match = MatchListEntry(
                var_data=RecordedMatch(
                    var_id=match_id,
                    arena_id=self._arena.match_data.match_info.id,
                    clip_file_name=recording_name,
                    match_start_timestamp=match_timestamp,
                    recording_start_timestamp=recording_timestamp,
                    teams=match_teams,
                ),
                arena_data=self._arena.match_results.get(
                    self._arena.match_data.match_info.id
                ),
            )
            self._matches[match_id] = self._current_match
            self._db.save_match(self._current_match.var_data)
            await self._websocket.notify(CONTROLLER_STATUS_EVENT)
            await self._websocket.notify(MATCH_LIST_EVENT)

    async def _handle_auto_period_end(self):
        """Handle a notification that the AUTO period has ended"""
        async with self._lock:
            if self._state != ControllerState.Recording:
                logger.debug("Not in recording state, ignoring auto period end")
                return

            self._add_match_event(
                MatchEvent(
                    event_id=self._create_event_id(),
                    event_type=MatchEventType.AUTO_SCORING,
                    time=self._get_current_match_time()
                    + self._settings.auto_scoring_delay,
                )
            )
            await self._websocket.notify(MATCH_LIST_EVENT)

    async def _handle_match_end(self):
        """Handle a notification that a match has ended"""

        async def delayed_stop():
            """Delay stopping the recording to allow for endgame scoring"""
            await asyncio.sleep(
                self._settings.endgame_scoring_delay
                + self._settings.recording_extra_time
            )
            await self._finalize_match_recording()

        async with self._lock:
            if self._state == ControllerState.Recording:
                self._add_match_event(
                    MatchEvent(
                        event_id=self._create_event_id(),
                        event_type=MatchEventType.ENDGAME_SCORING,
                        time=self._get_current_match_time()
                        + self._settings.endgame_scoring_delay,
                    )
                )
                await self._websocket.notify(MATCH_LIST_EVENT)
                asyncio.create_task(delayed_stop())

    async def _handle_match_commit(self):
        async with self._lock:
            if self._state == ControllerState.ReviewingHistoricalMatch:
                logger.debug("Reviewing a different match, ignoring commit")
                return

            await self._save_and_unload_current_match()
            self._set_state(ControllerState.Idle)
            await self._websocket.notify(CONTROLLER_STATUS_EVENT)

    ###############################################
    # Emitters for nontrivial UI event payloads   #
    ###############################################

    def _get_controller_status_event(self) -> dict:
        match self._state:
            case ControllerState.Idle:
                recording = False
                realtime_data = True
            case ControllerState.Recording:
                recording = True
                realtime_data = True
            case ControllerState.ReviewingCurrentMatch:
                recording = False
                realtime_data = True
            case ControllerState.ReviewingHistoricalMatch:
                recording = False
                realtime_data = False
            case _:
                assert False, f"Unknown controller state: {self._state}"

        selected_match_id = (
            self._current_match.var_data.var_id if self._current_match else None
        )
        return ControllerStatus(
            recording=recording,
            realtime_data=realtime_data,
            selected_match_id=selected_match_id,
        ).model_dump()

    def _get_hyperdeck_status_event(self) -> dict:
        """Get the current HyperDeck status for the UI."""
        if not self._current_match or self._current_match.var_data.clip_id is None:
            clip_time = 0.0
        else:
            clip_time = self._hyperdeck.get_current_time_within_clip(
                self._current_match.var_data.clip_id
            )
        playing = self._hyperdeck.playback_state.type == PlaybackType.Play
        active_working_set = self._hyperdeck.get_active_working_set()
        return HyperdeckStatus(
            transport_mode=self._hyperdeck.transport_mode,
            playing=playing,
            clip_time=clip_time,
            remaining_record_time=active_working_set.remainingRecordTime,
            total_space=active_working_set.totalSpace,
            remaining_space=active_working_set.remainingSpace,
        ).model_dump()

    ###############################################
    # Handlers for arena-related UI data changing #
    ###############################################

    async def _handle_arena_connection_state_update(self):
        """Handle a notification that the arena connection state has changed"""
        await self._websocket.notify(ARENA_CONNECTION_EVENT)

    async def _handle_historical_scores_update(self):
        """Handle a notification that the historical scores have changed"""
        self._refresh_arena_match_data()
        await self._websocket.notify(MATCH_LIST_EVENT)

    async def _handle_realtime_score_update(self):
        """Handle a notification that the realtime score has changed"""
        await self._check_for_foul_changes()
        await self._websocket.notify(REALTIME_SCORE_EVENT)

    async def _handle_match_data_update(self):
        """Handle a notification that the match data has changed"""
        await self._websocket.notify(CURRENT_MATCH_DATA_EVENT)

    async def _handle_match_timing_update(self):
        """Handle a notification that the match timing has changed"""
        await self._websocket.notify(MATCH_TIMING_EVENT)

    async def _handle_match_time_update(self):
        """Handle a notification that the match time has changed"""
        await self._websocket.notify(CURRENT_MATCH_TIME_EVENT)

    ###################################################
    # Handlers for hyperdeck-related UI data changing #
    ###################################################

    async def _handle_hyperdeck_connection_state_update(self):
        """Handle a notification that the HyperDeck connection state has changed"""
        await self._websocket.notify(HYPERDECK_CONNECTION_EVENT)

    async def _handle_hyperdeck_transport_mode_update(self):
        """Handle a notification that the HyperDeck transport mode has changed"""
        await self._websocket.notify(HYPERDECK_STATUS_EVENT)

    async def _handle_hyperdeck_playback_state_update(self):
        """Handle a notification that the HyperDeck playback state has changed"""
        await self._websocket.notify(HYPERDECK_STATUS_EVENT)

    async def _handle_hyperdeck_clip_list_update(self):
        """Handle a notification that the HyperDeck clip list has changed"""
        self._refresh_hyperdeck_clip_presence()
        await self._websocket.notify(MATCH_LIST_EVENT)

    async def _handle_hyperdeck_disk_space_update(self):
        """Handle a notification that the HyperDeck disk space information has changed"""
        await self._websocket.notify(HYPERDECK_STATUS_EVENT)

    #########################################
    # Handlers for commands from the VAR UI #
    #########################################

    async def _handle_load_match_command(self, command: LoadMatchCommand):
        """Handle a command to load a match for review."""
        async with self._lock:
            if (
                self._state == ControllerState.Idle
                or self._state == ControllerState.ReviewingHistoricalMatch
            ):
                if command.match_id not in self._matches:
                    logger.error(f"Match {command.match_id} not found")
                    return

                self._current_match = self._matches[command.match_id]
                self._state = ControllerState.ReviewingHistoricalMatch
                clip_id = self._current_match.var_data.clip_id
                if clip_id and self._hyperdeck.has_playable_clip(clip_id):
                    await self._hyperdeck.warp_to_clip(clip_id, 0.0)
                await self._websocket.notify(CONTROLLER_STATUS_EVENT)

    async def _handle_warp_to_time_command(self, command: WarpToTimeCommand):
        """Handle a command to warp the video player to a specific time."""
        async with self._lock:
            if (
                self._state != ControllerState.ReviewingHistoricalMatch
                and self._state != ControllerState.ReviewingCurrentMatch
            ):
                return
            if (
                self._current_match is None
                or self._current_match.var_data.var_id != command.match_id
            ):
                # Race condition, ignore the command
                return
            clip_id = self._current_match.var_data.clip_id
            if clip_id and self._hyperdeck.has_playable_clip(clip_id):
                await self._hyperdeck.warp_to_clip(clip_id, command.time)

    async def _internal_add_var_review(self, event_type: MatchEventType, time: float):
        """Internal method to add an event to the current match."""
        if self._current_match is None:
            return
        if self._state == ControllerState.Recording:
            # Backdate the event time a bit to account for human reaction times
            time = max(0.0, time - self._settings.var_review_backdate_time)
        event = MatchEvent(
            event_id=self._create_event_id(),
            event_type=event_type,
            time=time,
        )
        self._add_match_event(event)
        await self._websocket.notify(MATCH_LIST_EVENT)

    async def _handle_add_var_review_command(self, command: AddVARReviewCommand):
        """Handle a command to add a VAR review event to the current match."""
        async with self._lock:
            if self._current_match is None:
                return
            if self._current_match.var_data.var_id != command.match_id:
                logger.warning(
                    f"Cannot add VAR review event for match {command.match_id} when current match is {self._current_match.var_data.var_id}"
                )
                return
            await self._internal_add_var_review(MatchEventType.VAR_REVIEW, command.time)

    async def external_add_var_review(self):
        """Handle an external request to add a VAR review event at the current time."""
        async with self._lock:
            if self._state != ControllerState.Recording:
                return
            await self._internal_add_var_review(
                MatchEventType.HR_REVIEW, self._get_current_match_time()
            )

    async def _handle_exit_review_command(self, _command: ExitReviewCommand):
        """Handle a command to exit review mode and go to the live view."""
        async with self._lock:
            if self._state == ControllerState.ReviewingHistoricalMatch:
                await self._save_and_unload_current_match()
                self._set_state(ControllerState.Idle)
                await self._websocket.notify(CONTROLLER_STATUS_EVENT)

    async def _handle_update_event_command(self, command: UpdateEventCommand):
        """Handle a command to update an existing event in a match."""
        async with self._lock:
            # Find the match
            match_entry = self._matches.get(command.match_id)
            if not match_entry:
                logger.warning(f"Match {command.match_id} not found")
                return

            # Find the event to update
            event_to_update = None
            for event in match_entry.var_data.events:
                if event.event_id == command.event_id:
                    event_to_update = event
                    break

            if not event_to_update:
                logger.warning(
                    f"Event {command.event_id} not found in match {command.match_id}"
                )
                return

            # Apply the updates
            for field, value in command.updates.items():
                if hasattr(event_to_update, field):
                    setattr(event_to_update, field, value)
                    logger.info(
                        f"Updated event {command.event_id} field {field} to {value}"
                    )
                else:
                    logger.warning(f"Event field {field} not found")

            # Save the updated match
            self._db.save_match(match_entry.var_data)
            await self._websocket.notify(MATCH_LIST_EVENT)
