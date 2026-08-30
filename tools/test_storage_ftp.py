"""
Integration test for HyperDeck storage management against the mock HyperDeck.

Unlike tools/test_storage_manager.py, which fakes everything, this drives the real
HyperDeck client, the real FTP client and the real StorageManager against a running
mock server. It covers the parts that only a real FTP conversation can exercise:
volume discovery, downloads, aborting a transfer mid-flight, and deletion.

Start the mock first:
    uv run tools/mock_hyperdeck.py

Then run:
    uv run tools/test_storage_ftp.py

Both accept --port/--ftp-port if you are not using the defaults.
"""

import argparse
import asyncio
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import List

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from frc_video_referee.cheesy_arena.model import MatchState  # noqa: E402
from frc_video_referee.hyperdeck.client import (  # noqa: E402
    HyperdeckClient,
    HyperdeckClientSettings,
)
from frc_video_referee.hyperdeck.ftp import (  # noqa: E402
    HyperdeckFTPClient,
    HyperdeckFTPSettings,
    TransferAborted,
)
from frc_video_referee.storage import (  # noqa: E402
    StorageActivity,
    StorageManager,
    StorageSettings,
)

FAILURES: List[str] = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(name)


async def record_clip(client: httpx.AsyncClient, name: str, seconds: float) -> int:
    """Record a clip on the mock and wait for it to finalize, as the real client does."""
    await client.post("/transports/0/record", json={"clipName": name})
    await asyncio.sleep(seconds)
    await client.post("/transports/0/stop")
    for _ in range(40):
        response = await client.get("/transports/0/clip")
        clip = response.json().get("clip") or {}
        if clip.get("frameCount"):
            return clip["fileSize"]
        await asyncio.sleep(0.25)
    raise RuntimeError(f"Clip {name} never finalized")


class StubArena:
    """An arena sitting quietly in pre-match, which is when cleanup is allowed."""

    def __init__(self):
        self.match_time = SimpleNamespace(match_state=MatchState.PRE_MATCH)
        self.arena_status = SimpleNamespace(can_start_match=False)
        self.match_results = {}

    def subscribe(self, notifier, callback):
        pass


class StubDB:
    def load_all_matches(self):
        return {}


class StubWebsocket:
    def add_event_type(self, event_type, emitter):
        pass

    async def notify(self, event_type, data=None):
        pass


class StubHost:
    def get_storage_activity(self):
        return StorageActivity(idle=True, protected_match_ids=set())

    async def record_clip_reclaimed(self, var_id, archive_path):
        pass


async def test_ftp_client(address: str, ftp_port: int, workdir: Path):
    print("\n=== FTP client against the mock's FTP server ===")
    host = address.rsplit(":", 1)[0]

    async with httpx.AsyncClient(base_url=f"http://{address}/control/api/v1") as client:
        size = await record_clip(client, "FTPTEST.mp4", seconds=4.0)

    ftp = HyperdeckFTPClient(host, HyperdeckFTPSettings(port=ftp_port))

    directories = await ftp.list_directories()
    check("lists media volumes", "sdcard" in directories, f"got {directories}")

    files = await ftp.list_files("sdcard")
    listed = next((f for f in files if f.name == "FTPTEST.mp4"), None)
    check("lists the recorded clip", listed is not None)
    if listed is not None:
        check("reports the right size", listed.size == size, f"{listed.size} != {size}")

    destination = workdir / "FTPTEST.mp4"
    written = await ftp.download("/sdcard/FTPTEST.mp4", destination, asyncio.Event())
    check("download reports the full size", written == size, f"{written} != {size}")
    check("downloaded file is complete", destination.stat().st_size == size)

    # A transfer must stop promptly when the field goes hot, leaving nothing behind
    partial = workdir / "PARTIAL.mp4"
    abort = asyncio.Event()

    async def trip_abort():
        await asyncio.sleep(0.05)
        abort.set()

    aborter = asyncio.create_task(trip_abort())
    try:
        await ftp.download("/sdcard/FTPTEST.mp4", partial, abort)
        check("aborted transfer raises", False, "the download ran to completion")
    except TransferAborted:
        check("aborted transfer raises TransferAborted", True)
    await aborter
    check("aborted transfer leaves no partial file", not partial.exists())

    await ftp.delete("/sdcard/FTPTEST.mp4")
    files = await ftp.list_files("sdcard")
    check("delete removes the file", all(f.name != "FTPTEST.mp4" for f in files))


async def test_storage_manager(address: str, ftp_port: int):
    print("\n=== StorageManager reclaiming space over FTP ===")

    async with httpx.AsyncClient(base_url=f"http://{address}/control/api/v1") as client:
        for name in ("SM01.mp4", "SM02.mp4", "SM03.mp4"):
            await record_clip(client, name, seconds=1.5)

    hyperdeck = HyperdeckClient(HyperdeckClientSettings(address=address))
    hyperdeck_task = asyncio.create_task(hyperdeck.run())
    await asyncio.sleep(2)

    clips_before = len(hyperdeck.all_clips)
    check("deck reports the recorded clips", clips_before >= 3, f"got {clips_before}")

    # Squeeze the simulated disk so the low-space threshold trips
    async with httpx.AsyncClient(base_url=f"http://{address}") as client:
        working_set = hyperdeck.get_active_working_set()
        response = await client.post(
            "/mock/storage",
            json={"reserved_space": int(working_set.totalSpace * 0.95)},
        )
        response.raise_for_status()
    await asyncio.sleep(0.5)
    await hyperdeck.refresh_working_set()
    print(
        f"  Squeezed to {hyperdeck.get_active_working_set().remainingRecordTime}s of record time"
    )

    manager = StorageManager(
        StorageSettings(
            low_space_threshold=300,
            target_record_time=400,
            min_matches_retained=0,
            quiet_period=0.0,
            ftp=HyperdeckFTPSettings(port=ftp_port),
        ),
        hyperdeck,
        address,
        StubArena(),
        StubDB(),
        StubWebsocket(),
    )
    manager.set_host(StubHost())

    for _ in range(10):
        manager._quiet_since = None
        await manager._tick()
        await manager._tick()
        if not manager._queue:
            break

    await hyperdeck.refresh_clip_list()
    clips_after = len(hyperdeck.all_clips)
    hyperdeck_task.cancel()

    check(
        "clips were reclaimed over FTP",
        clips_after < clips_before,
        f"{clips_before} -> {clips_after}",
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--ftp-port", type=int, default=2121)
    args = parser.parse_args()

    address = f"{args.host}:{args.port}"

    try:
        async with httpx.AsyncClient() as client:
            await client.get(f"http://{address}/", timeout=3.0)
    except Exception:
        print(f"Could not reach the mock HyperDeck at {address}.")
        print("Start it with: uv run tools/mock_hyperdeck.py")
        return 1

    workdir = Path(tempfile.mkdtemp(prefix="storage_ftp_test_"))
    try:
        await test_ftp_client(address, args.ftp_port, workdir)
        await test_storage_manager(address, args.ftp_port)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED: {FAILURES}")
        return 1
    print("All storage FTP integration checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
