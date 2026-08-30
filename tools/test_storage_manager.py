"""
Tests for HyperDeck storage management.

Exercises the parts of StorageManager that are hard to check by hand at an event: which
clips get chosen for reclamation and in what order, and the downtime gating that keeps
file operations away from match recordings.

Unlike the other scripts in this folder these tests need no running server; the
HyperDeck, arena, database and FTP connections are all faked.

Run from the repository root with:
    uv run tools/test_storage_manager.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from frc_video_referee.cheesy_arena.model import MatchState  # noqa: E402
from frc_video_referee.db.model import Alliance, RecordedMatch  # noqa: E402
from frc_video_referee.hyperdeck.ftp import TransferAborted  # noqa: E402
from frc_video_referee.hyperdeck.model import (  # noqa: E402
    Clip,
    CodecFormat,
    MediaWorkingSetEntry,
    TransportMode,
    VideoFormat,
)
from frc_video_referee.storage import (  # noqa: E402
    StorageActivity,
    StorageManager,
    StorageSettings,
)
from frc_video_referee.web.model import StorageState  # noqa: E402

CLIP_BYTES = 1_000_000_000
CLIP_FRAMES = 9000
CLIP_FPS = 60.0
CLIP_SECONDS = CLIP_FRAMES / CLIP_FPS  # 150s per clip
BYTES_PER_SECOND = CLIP_BYTES / CLIP_SECONDS


def make_clip(clip_id: int, name: str) -> Clip:
    return Clip(
        clipUniqueId=clip_id,
        filePath=name,
        fileSize=CLIP_BYTES,
        codecFormat=CodecFormat(codec="H.264", container="MOV"),
        videoFormat=VideoFormat(
            name="1920x1080p60",
            frameRate=CLIP_FPS,
            height=1080,
            width=1920,
            interlaced=False,
        ),
        durationTimecode="00:02:30:00",
        frameCount=CLIP_FRAMES,
    )


def make_match(
    var_id: str, arena_id: int, clip_id: int, age_minutes: int
) -> RecordedMatch:
    timestamp = datetime.now().astimezone() - timedelta(minutes=age_minutes)
    return RecordedMatch(
        var_id=var_id,
        arena_id=arena_id,
        clip_id=clip_id,
        clip_file_name=f"{var_id}.mov",
        match_start_timestamp=timestamp,
        recording_start_timestamp=timestamp,
        teams={Alliance.RED: [1, 2, 3], Alliance.BLUE: [4, 5, 6]},
    )


class FakeHyperdeck:
    def __init__(self, clips: Dict[int, Clip], remaining_record_time: float):
        # Copied so that separate fake decks in one test stay independent
        self.all_clips = dict(clips)
        self.connected = True
        self.transport_mode = TransportMode.InputPreview
        self._remaining = remaining_record_time
        self.subscribers = {}
        self.refresh_count = 0

    def subscribe(self, notifier, callback):
        self.subscribers.setdefault(notifier, []).append(callback)

    def get_active_working_set(self) -> MediaWorkingSetEntry:
        return MediaWorkingSetEntry(
            index=0,
            activeDisk=True,
            volume="sdcard",
            deviceName="SD Card",
            remainingRecordTime=int(self._remaining),
            totalSpace=100 * CLIP_BYTES,
            remainingSpace=int(self._remaining * BYTES_PER_SECOND),
            clipCount=len(self.all_clips),
        )

    def set_remaining(self, seconds: float):
        self._remaining = seconds

    async def refresh_clip_list(self):
        self.refresh_count += 1

    async def refresh_working_set(self):
        self.refresh_count += 1


class FakeArena:
    def __init__(self, committed_arena_ids: List[int]):
        self.match_time = SimpleNamespace(match_state=MatchState.PRE_MATCH)
        self.arena_status = SimpleNamespace(can_start_match=False)
        self.match_results = {
            arena_id: SimpleNamespace(result=SimpleNamespace(score=10))
            for arena_id in committed_arena_ids
        }
        self.subscribers = {}

    def subscribe(self, notifier, callback):
        self.subscribers.setdefault(notifier, []).append(callback)


class FakeDB:
    def __init__(self, matches: Dict[str, RecordedMatch]):
        self._matches = matches

    def load_all_matches(self):
        return dict(self._matches)


class FakeWebsocket:
    def __init__(self):
        self.events = {}
        self.notifications = []

    def add_event_type(self, event_type, emitter):
        self.events[event_type] = emitter

    async def notify(self, event_type, data=None):
        self.notifications.append(event_type)


class FakeFTP:
    """Stands in for the deck's FTP server.

    Deleting removes the clip from the fake deck as well, mirroring what a real deck
    reports once the clip list is refreshed.
    """

    def __init__(self, hyperdeck=None, fail_on=None, short_download=None):
        self.hyperdeck = hyperdeck
        self.deleted: List[str] = []
        self.downloaded: List[str] = []
        self.fail_on = fail_on or set()
        self.short_download = short_download or set()
        self.abort_on_download = False

    async def list_directories(self):
        return ["sdcard", "ssd1"]

    async def delete(self, remote_path):
        if remote_path in self.fail_on:
            raise RuntimeError("simulated FTP failure")
        self.deleted.append(remote_path)
        if self.hyperdeck is not None:
            name = remote_path.rsplit("/", 1)[-1]
            for clip_id, clip in list(self.hyperdeck.all_clips.items()):
                if clip.filePath == name:
                    del self.hyperdeck.all_clips[clip_id]

    async def download(self, remote_path, local_path, abort):
        if self.abort_on_download or abort.is_set():
            raise TransferAborted("simulated abort")
        self.downloaded.append(remote_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"x")
        if remote_path in self.short_download:
            return CLIP_BYTES - 1
        return CLIP_BYTES


def build_manager(
    *,
    clips: Dict[int, Clip],
    matches: Dict[str, RecordedMatch],
    committed_arena_ids: List[int],
    remaining_record_time: float,
    settings: StorageSettings | None = None,
    protected: set | None = None,
    idle: bool = True,
):
    settings = settings or StorageSettings(min_matches_retained=0)
    hyperdeck = FakeHyperdeck(clips, remaining_record_time)
    arena = FakeArena(committed_arena_ids)
    db = FakeDB(matches)
    websocket = FakeWebsocket()

    manager = StorageManager(
        settings, hyperdeck, "hyperdeck.local:8001", arena, db, websocket
    )

    reclaimed: List[tuple] = []

    class Host:
        def get_storage_activity(self):
            return StorageActivity(idle=idle, protected_match_ids=protected or set())

        async def record_clip_reclaimed(self, var_id, archive_path):
            reclaimed.append((var_id, archive_path))

    manager.set_host(Host())
    ftp = FakeFTP(hyperdeck=hyperdeck)
    manager._ftp = ftp
    return manager, hyperdeck, arena, ftp, reclaimed


FAILURES: List[str] = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(name)


async def test_no_work_when_space_is_plentiful():
    print("\n=== Plenty of space: nothing queued ===")
    clips = {1: make_clip(1, "orphan.mov")}
    manager, _, _, _, _ = build_manager(
        clips=clips, matches={}, committed_arena_ids=[], remaining_record_time=99999
    )
    manager._rebuild_queue()
    check("queue stays empty", len(manager._queue) == 0)
    check("state is OK", manager._compute_state() == StorageState.OK)


async def test_orphans_are_reclaimed_first():
    print("\n=== Low space: orphan clips are queued ahead of matches ===")
    clips = {
        1: make_clip(1, "Q01.mov"),
        2: make_clip(2, "stray_recording.mov"),
        3: make_clip(3, "Q02.mov"),
    }
    matches = {
        "Q01": make_match("Q01", 101, 1, age_minutes=120),
        "Q02": make_match("Q02", 102, 3, age_minutes=60),
    }
    manager, _, _, _, _ = build_manager(
        clips=clips,
        matches=matches,
        committed_arena_ids=[101, 102],
        remaining_record_time=600,
    )
    candidates = manager._build_candidates()
    check("orphan is first candidate", candidates[0].file_path == "stray_recording.mov")
    check("orphan has no match", candidates[0].var_id is None)
    check(
        "matches follow, oldest first",
        [c.var_id for c in candidates[1:]] == ["Q01", "Q02"],
        f"got {[c.var_id for c in candidates[1:]]}",
    )


async def test_retention_and_eligibility_rules():
    print("\n=== Matches that must never be reclaimed ===")
    clips = {i: make_clip(i, f"Q{i:02d}.mov") for i in range(1, 6)}
    matches = {
        f"Q{i:02d}": make_match(f"Q{i:02d}", 100 + i, i, age_minutes=200 - i * 10)
        for i in range(1, 6)
    }
    # Q05 is uncommitted, so it must be skipped even though it is old enough
    manager, _, _, _, _ = build_manager(
        clips=clips,
        matches=matches,
        committed_arena_ids=[101, 102, 103, 104],
        remaining_record_time=600,
        settings=StorageSettings(min_matches_retained=2),
        protected={"Q02"},
    )
    ids = [c.var_id for c in manager._build_candidates()]
    check("uncommitted match excluded", "Q05" not in ids)
    check("protected (loaded) match excluded", "Q02" not in ids)
    check("two most recent matches retained", "Q04" not in ids and "Q05" not in ids)
    check("eligible matches remain", ids == ["Q01", "Q03"], f"got {ids}")


async def test_queue_size_matches_space_needed():
    print("\n=== Queue is sized to the space actually needed ===")
    clips = {i: make_clip(i, f"orphan{i}.mov") for i in range(1, 21)}
    # 600s of headroom, target 5400s => needs 4800s => 32 clips' worth of bytes...
    # each clip is 150s of recording, so 32 clips. Only 20 exist, so all are queued.
    manager, _, _, _, _ = build_manager(
        clips=clips, matches={}, committed_arena_ids=[], remaining_record_time=600
    )
    manager._rebuild_queue()
    check("all available clips queued when far below target", len(manager._queue) == 20)

    # With only a small shortfall, only a couple of clips should be queued
    manager2, _, _, _, _ = build_manager(
        clips=clips,
        matches={},
        committed_arena_ids=[],
        remaining_record_time=600,
        settings=StorageSettings(
            min_matches_retained=0, low_space_threshold=700, target_record_time=900
        ),
    )
    manager2._rebuild_queue()
    check(
        "small shortfall queues few clips",
        len(manager2._queue) == 2,
        f"got {len(manager2._queue)}",
    )


async def test_hysteresis():
    print("\n=== Hysteresis between trigger and target ===")
    clips = {i: make_clip(i, f"orphan{i}.mov") for i in range(1, 5)}
    manager, hyperdeck, _, _, _ = build_manager(
        clips=clips, matches={}, committed_arena_ids=[], remaining_record_time=600
    )
    manager._rebuild_queue()
    check("triggered when below threshold", manager._triggered)

    # Between the threshold and the target, cleanup must keep going
    hyperdeck.set_remaining(3000)
    manager._rebuild_queue()
    check("still triggered between threshold and target", manager._triggered)

    # Reaching the target clears the trigger and the queue
    hyperdeck.set_remaining(6000)
    manager._rebuild_queue()
    check("trigger clears at target", not manager._triggered)
    check("queue cleared at target", len(manager._queue) == 0)


async def test_downtime_gating():
    print("\n=== Downtime gating ===")
    clips = {1: make_clip(1, "orphan.mov")}
    manager, hyperdeck, arena, _, _ = build_manager(
        clips=clips, matches={}, committed_arena_ids=[], remaining_record_time=600
    )
    check("idle pre-match counts as downtime", manager._downtime_available())

    arena.arena_status.can_start_match = True
    check("field ready blocks work", not manager._downtime_available())
    arena.arena_status.can_start_match = False

    arena.match_time.match_state = MatchState.AUTO_PERIOD
    check("match in progress blocks work", not manager._downtime_available())
    arena.match_time.match_state = MatchState.PRE_MATCH

    hyperdeck.transport_mode = TransportMode.InputRecord
    check("recording blocks work", not manager._downtime_available())
    hyperdeck.transport_mode = TransportMode.InputPreview

    hyperdeck.connected = False
    check("disconnected deck blocks work", not manager._downtime_available())
    hyperdeck.connected = True

    # A busy controller (reviewing or recording) also blocks
    manager2, _, _, _, _ = build_manager(
        clips=clips,
        matches={},
        committed_arena_ids=[],
        remaining_record_time=600,
        idle=False,
    )
    check("busy controller blocks work", not manager2._downtime_available())


async def test_quiet_period_must_elapse():
    print("\n=== Quiet period ===")
    clips = {1: make_clip(1, "orphan.mov")}
    manager, _, _, ftp, _ = build_manager(
        clips=clips, matches={}, committed_arena_ids=[], remaining_record_time=600
    )
    manager._rebuild_queue()

    await manager._tick()
    check("first tick only starts the quiet timer", ftp.deleted == [])
    await manager._tick()
    check("still waiting out the quiet period", ftp.deleted == [])

    # Pretend the quiet period has elapsed
    manager._quiet_since -= manager._settings.quiet_period
    await manager._tick()
    check("work runs once quiet", ftp.deleted == ["/sdcard/orphan.mov"])


async def test_field_going_hot_aborts_and_resumes():
    print("\n=== Field going hot interrupts work ===")
    clips = {i: make_clip(i, f"orphan{i}.mov") for i in range(1, 4)}
    manager, _, arena, ftp, _ = build_manager(
        clips=clips, matches={}, committed_arena_ids=[], remaining_record_time=600
    )
    manager._rebuild_queue()
    queued = len(manager._queue)

    # A match becomes imminent
    await manager._handle_field_hot()
    arena.arena_status.can_start_match = True
    await manager._tick()
    check("no work while the field is hot", ftp.deleted == [])
    check("queue is preserved for later", len(manager._queue) == queued)
    check("quiet timer reset", manager._quiet_since is None)

    # ...and the downtime after the match resumes it
    arena.arena_status.can_start_match = False
    await manager._tick()
    manager._quiet_since -= manager._settings.quiet_period
    await manager._tick()
    check("work resumes after the match", len(ftp.deleted) == 1)


async def test_offload_verifies_before_deleting(tmp: Path):
    print("\n=== Offload is verified before deletion ===")
    clips = {1: make_clip(1, "orphan.mov")}
    settings = StorageSettings(min_matches_retained=0, offload_path=tmp / "archive")
    manager, _, _, ftp, reclaimed = build_manager(
        clips=clips,
        matches={},
        committed_arena_ids=[],
        remaining_record_time=600,
        settings=settings,
    )
    manager._rebuild_queue()
    manager._quiet_since = 0.0
    await manager._tick()
    await manager._tick()
    check("clip was offloaded", ftp.downloaded == ["/sdcard/orphan.mov"])
    check("clip was then deleted", ftp.deleted == ["/sdcard/orphan.mov"])

    # A truncated transfer must leave the file on the deck
    manager2, _, _, ftp2, _ = build_manager(
        clips=clips,
        matches={},
        committed_arena_ids=[],
        remaining_record_time=600,
        settings=settings,
    )
    ftp2.short_download = {"/sdcard/orphan.mov"}
    manager2._rebuild_queue()
    manager2._quiet_since = 0.0
    await manager2._tick()
    await manager2._tick()
    check("incomplete offload does not delete", ftp2.deleted == [])
    check("failure is reported", manager2._last_error is not None)


async def test_match_reclaim_is_recorded():
    print("\n=== Reclaiming a match's clip notifies the controller ===")
    clips = {1: make_clip(1, "Q01.mov")}
    matches = {"Q01": make_match("Q01", 101, 1, age_minutes=120)}
    manager, _, _, ftp, reclaimed = build_manager(
        clips=clips,
        matches=matches,
        committed_arena_ids=[101],
        remaining_record_time=600,
    )
    manager._rebuild_queue()
    manager._quiet_since = 0.0
    await manager._tick()
    await manager._tick()
    check("match clip deleted", ftp.deleted == ["/sdcard/Q01.mov"])
    check("controller notified", reclaimed == [("Q01", None)], f"got {reclaimed}")


async def test_failing_file_does_not_block_queue():
    print("\n=== A file that keeps failing is dropped ===")
    clips = {i: make_clip(i, f"orphan{i}.mov") for i in range(1, 3)}
    manager, _, _, ftp, _ = build_manager(
        clips=clips, matches={}, committed_arena_ids=[], remaining_record_time=600
    )
    ftp.fail_on = {"/sdcard/orphan1.mov"}
    manager._rebuild_queue()

    for _ in range(manager._settings.max_attempts + 2):
        manager._quiet_since = 0.0
        await manager._tick()

    check("bad file gave up", manager._attempts.get("orphan1.mov", 0) >= 3)
    check("good file still processed", "/sdcard/orphan2.mov" in ftp.deleted)


async def test_dry_run_touches_nothing():
    print("\n=== Dry run ===")
    clips = {1: make_clip(1, "orphan.mov")}
    manager, _, _, ftp, reclaimed = build_manager(
        clips=clips,
        matches={},
        committed_arena_ids=[],
        remaining_record_time=600,
        settings=StorageSettings(min_matches_retained=0, dry_run=True),
    )
    manager._rebuild_queue()
    manager._quiet_since = 0.0
    await manager._tick()
    await manager._tick()
    check("nothing deleted in dry run", ftp.deleted == [])
    check("queue still drains", len(manager._queue) == 0)


async def main():
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        await test_no_work_when_space_is_plentiful()
        await test_orphans_are_reclaimed_first()
        await test_retention_and_eligibility_rules()
        await test_queue_size_matches_space_needed()
        await test_hysteresis()
        await test_downtime_gating()
        await test_quiet_period_must_elapse()
        await test_field_going_hot_aborts_and_resumes()
        await test_offload_verifies_before_deleting(tmp)
        await test_match_reclaim_is_recorded()
        await test_failing_file_does_not_block_queue()
        await test_dry_run_touches_nothing()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED: {FAILURES}")
        return 1
    print("All storage management checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
