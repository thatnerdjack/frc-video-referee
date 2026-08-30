# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi",
#     "uvicorn",
#     "websockets",
#     "pyftpdlib",
# ]
# ///
"""
Mock BlackMagic HyperDeck API Server

A standalone FastAPI implementation that mocks the BlackMagic HyperDeck Control API
for development and testing purposes. Based on the API subset documented in
docs/Blackmagic_API_subset.md.
"""

import json
import random
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
import uvicorn

# Media / storage simulation. Clips are backed by real (sparse) files so that the FTP
# server has something to serve and delete, without consuming actual disk space.
VOLUME_NAME = "sdcard"
"""Name of the simulated media volume. Also the FTP directory holding clips."""

BYTES_PER_SECOND = 20_000_000
"""Simulated recording bitrate, used to size clip files and estimate record time"""

DEFAULT_DISK_SIZE = 8 * 1024**3
"""Default simulated media capacity, small enough to fill up during testing"""


# Pydantic Models
class CodecFormat(BaseModel):
    codec: str = "H.264"
    container: str = "MP4"


class VideoFormat(BaseModel):
    name: str = "1080p60"
    frameRate: str = "60.00"
    height: int = 1080
    width: int = 1920
    interlaced: bool = False


class ClipInfo(BaseModel):
    clipUniqueId: int
    filePath: str
    fileSize: int = 0
    codecFormat: CodecFormat = Field(default_factory=CodecFormat)
    videoFormat: VideoFormat = Field(default_factory=VideoFormat)
    startTimecode: str = "<dummy>"
    durationTimecode: str = "<dummy>"
    frameCount: int = 500


class MockStorageRequest(BaseModel):
    """Testing hook for adjusting simulated storage"""

    disk_size: Optional[int] = None
    reserved_space: Optional[int] = None


class TimelineClip(BaseModel):
    clipUniqueId: int
    frameCount: int
    timelineIn: int
    durationTimecode: str = "<dummy>"
    clipIn: int = 0
    inTimecode: str = "<dummy>"
    timelineInTimecode: str = "<dummy>"


class TransportMode(BaseModel):
    mode: str = Field(..., pattern="^(InputPreview|InputRecord|Output)$")


class PlaybackRequest(BaseModel):
    type: str = Field(..., pattern="^(Play|Jog|Shuttle|Var)$")
    loop: bool = False
    singleClip: bool = True
    speed: float = 1.0
    position: int = 0


class RecordRequest(BaseModel):
    clipName: Optional[str] = None


class WebSocketSubscribe(BaseModel):
    action: str = Field(..., pattern="^(subscribe|unsubscribe)$")
    properties: List[str]


class WebSocketRequest(BaseModel):
    data: WebSocketSubscribe
    type: str = "request"
    id: Optional[int] = None


@dataclass
class PendingFinalization:
    """Data structure for pending clip finalization."""

    frameCount: int
    durationTimecode: str
    fileSize: int
    timeline_frameCount: int
    finalization_time: float


# Mock State Management
class MockHyperDeckState:
    def __init__(self):
        self.transport_mode = "InputPreview"
        self.clips: List[ClipInfo] = []
        self.timeline_clips: List[TimelineClip] = []
        self.playback_config = {
            "type": "Play",
            "loop": False,
            "singleClip": True,
            "speed": 1.0,
            "position": 0,
        }
        self.clip_index = 0
        self.subscribers: Dict[str, Set[WebSocket]] = {}
        self.clip_start_time: float = time.time()
        self._pending_finalization: Optional[PendingFinalization] = None
        """Pending finalization data including finalization time"""

        self.media_dir: Path = Path(tempfile.mkdtemp(prefix="mock_hyperdeck_"))
        """Root directory served over FTP. Contains one directory per media volume."""
        self.volume_dir: Path = self.media_dir / VOLUME_NAME
        self.volume_dir.mkdir(parents=True, exist_ok=True)
        self.disk_size: int = DEFAULT_DISK_SIZE
        """Simulated capacity of the media in bytes"""
        self.reserved_space: int = 0
        """Extra space treated as consumed, for testing low-storage behaviour"""
        self._materialized: Set[int] = set()
        """IDs of clips whose backing file has been written.

        A clip that is still recording or awaiting finalization has no file yet, and
        must not be mistaken for one that was deleted over FTP.
        """

    #####################
    # Storage simulation #
    #####################

    def clip_file(self, clip: "ClipInfo") -> Path:
        """Path on disk backing a clip."""
        return self.volume_dir / clip.filePath

    def write_clip_file(self, clip: "ClipInfo") -> None:
        """Create a sparse file of the right size to back a clip."""
        path = self.clip_file(clip)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            f.truncate(clip.fileSize)
        self._materialized.add(clip.clipUniqueId)

    @property
    def used_space(self) -> int:
        return sum(clip.fileSize for clip in self.clips) + self.reserved_space

    @property
    def remaining_space(self) -> int:
        return max(0, self.disk_size - self.used_space)

    @property
    def remaining_record_time(self) -> int:
        return int(self.remaining_space / BYTES_PER_SECOND)

    def get_workingset(self) -> Dict:
        """Build the /media/workingset property value."""
        return {
            "size": 1,
            "workingset": [
                {
                    "index": 0,
                    "activeDisk": True,
                    "volume": VOLUME_NAME,
                    "deviceName": "Mock SD Card",
                    "remainingRecordTime": self.remaining_record_time,
                    "totalSpace": self.disk_size,
                    "remainingSpace": self.remaining_space,
                    "clipCount": len(self.clips),
                }
            ],
        }

    def sync_with_disk(self) -> bool:
        """Drop clips whose backing files have been removed out of band (e.g. over FTP).

        Returns True if anything changed.
        """
        surviving = [
            clip
            for clip in self.clips
            if clip.clipUniqueId not in self._materialized
            or self.clip_file(clip).exists()
        ]
        if len(surviving) == len(self.clips):
            return False

        removed = {clip.clipUniqueId for clip in self.clips} - {
            clip.clipUniqueId for clip in surviving
        }
        self._materialized -= removed
        print(f"Clips removed over FTP: {sorted(removed)}")
        self.clips = surviving
        self.timeline_clips = [
            tl for tl in self.timeline_clips if tl.clipUniqueId not in removed
        ]
        # Rebuild timeline positions now that clips have gone
        position = 0
        for timeline_clip in self.timeline_clips:
            timeline_clip.timelineIn = position
            timeline_clip.timelineInTimecode = self._frames_to_timecode(position)
            position += timeline_clip.frameCount
        self.clip_index = min(self.clip_index, max(0, len(self.timeline_clips) - 1))
        return True

    def set_transport_mode(self, mode: str):
        """Set the transport mode."""
        if self.transport_mode in ["InputRecord", "InputPreview"] and mode == "Output":
            if len(self.timeline_clips) == 0:
                raise ValueError("Cannot switch to Output mode without clips")
            self.clip_index = len(self.timeline_clips) - 1
            self.playback_config["position"] = self.timeline_clips[
                self.clip_index
            ].timelineIn

        self.transport_mode = mode

    @property
    def recording(self) -> bool:
        return self.transport_mode == "InputRecord"

    @property
    def current_clip(self) -> Optional[ClipInfo]:
        if self.clip_index < len(self.timeline_clips):
            clip_id = self.timeline_clips[self.clip_index].clipUniqueId
            for clip in self.clips:
                if clip.clipUniqueId == clip_id:
                    return clip
        return None

    @property
    def is_clip_finalized(self) -> bool:
        """Check if the current clip has been finalized (simulation of delay)"""
        if self._pending_finalization is None:
            return True
        return time.time() >= self._pending_finalization.finalization_time

    def _frames_to_timecode(self, frames: int, fps: float = 60.0) -> str:
        """Convert frame number to timecode string."""
        total_seconds = frames / fps
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        frame_part = int((total_seconds % 1) * fps)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame_part:02d}"

    def start_recording(self, clip_name: Optional[str] = None) -> None:
        """Start a recording session."""
        if not clip_name:
            clip_name = f"recording_{int(time.time())}.mp4"

        self.set_transport_mode("InputRecord")

        # Create new clip. IDs must keep increasing even after clips are deleted.
        new_clip_id = max((clip.clipUniqueId for clip in self.clips), default=1336) + 1
        self.clips.append(
            ClipInfo(
                clipUniqueId=new_clip_id,
                filePath=clip_name,
                frameCount=0,  # Will grow during recording
                startTimecode=self._frames_to_timecode(0),
                durationTimecode=self._frames_to_timecode(0),
            )
        )
        if len(self.timeline_clips) == 0:
            next_timeline_in = 0
        else:
            next_timeline_in = (
                self.timeline_clips[-1].timelineIn + self.timeline_clips[-1].frameCount
            )
        self.timeline_clips.append(
            TimelineClip(
                clipUniqueId=new_clip_id,
                frameCount=0,  # Will grow during recording
                durationTimecode=self._frames_to_timecode(0),
                clipIn=0,
                inTimecode=self._frames_to_timecode(0),
                timelineIn=next_timeline_in,  # Simulated position
                timelineInTimecode=self._frames_to_timecode(next_timeline_in),
            )
        )
        self.clip_index = len(self.timeline_clips) - 1
        self.clip_start_time = time.time()

        # A real deck creates the file as soon as recording starts; it is resized when
        # the clip is finalized
        self.write_clip_file(self.clips[-1])

    def stop_recording(self, finalization_delay: float = 0.0) -> None:
        """Stop the recording session.

        Args:
            finalization_delay: Delay in seconds before clip metadata is fully populated (simulates real device behavior)
        """
        current_clip = self.current_clip
        if self.recording and current_clip:
            # Calculate final clip metadata
            elapsed_time = time.time() - self.clip_start_time
            final_frames = int(elapsed_time * 60)  # Simulate recorded duration

            if finalization_delay > 0:
                # Simulate delay in finalizing the clip
                # Set frameCount to 0 initially (will be updated once finalized)
                current_clip.frameCount = 0
                current_clip.durationTimecode = self._frames_to_timecode(0)
                current_clip.fileSize = 0

                # Store the final values to apply later
                self._pending_finalization = PendingFinalization(
                    frameCount=final_frames,
                    durationTimecode=self._frames_to_timecode(final_frames),
                    fileSize=int(final_frames / 60 * BYTES_PER_SECOND),
                    timeline_frameCount=final_frames,
                    finalization_time=time.time() + finalization_delay,
                )
            else:
                # Finalize immediately
                current_clip.frameCount = final_frames
                current_clip.durationTimecode = self._frames_to_timecode(final_frames)
                current_clip.fileSize = int(final_frames / 60 * BYTES_PER_SECOND)
                self.write_clip_file(current_clip)

                # Update the timeline clip
                if self.timeline_clips:
                    timeline_clip = self.timeline_clips[-1]
                    timeline_clip.frameCount = final_frames
                    timeline_clip.durationTimecode = current_clip.durationTimecode

                self._pending_finalization = None

        self.set_transport_mode("InputPreview")

    def finalize_clip_if_ready(self) -> None:
        """Finalize the clip if finalization delay has elapsed"""
        if self._pending_finalization is not None and self.is_clip_finalized:
            current_clip = self.current_clip
            if current_clip:
                # Apply the pending finalization
                current_clip.frameCount = self._pending_finalization.frameCount
                current_clip.durationTimecode = (
                    self._pending_finalization.durationTimecode
                )
                current_clip.fileSize = self._pending_finalization.fileSize
                self.write_clip_file(current_clip)

                # Update the timeline clip
                if self.timeline_clips:
                    timeline_clip = self.timeline_clips[-1]
                    timeline_clip.frameCount = (
                        self._pending_finalization.timeline_frameCount
                    )
                    timeline_clip.durationTimecode = current_clip.durationTimecode

                self._pending_finalization = None

    def set_playback(self, config: PlaybackRequest) -> None:
        """Set playback configuration."""
        self.set_transport_mode("Output")
        self.playback_config.update(config.model_dump(exclude_unset=True))

        # Clamp position to within the timeline
        timeline_end_position = 0
        if self.timeline_clips:
            timeline_end_position = (
                self.timeline_clips[-1].timelineIn + self.timeline_clips[-1].frameCount
            )
        if self.playback_config["position"] > timeline_end_position:
            self.playback_config["position"] = timeline_end_position

        # Update clip index based on position
        position = self.playback_config["position"]
        for i, clip in enumerate(self.timeline_clips):
            if clip.timelineIn <= position < clip.timelineIn + clip.frameCount:
                self.clip_index = i
                break

    def get_property_value(self, property_path: str) -> Dict:
        """Get the current value for a property."""
        if property_path == "/timelines/0":
            return {"clips": [clip.model_dump() for clip in self.timeline_clips]}
        elif property_path == "/transports/0":
            return {"mode": self.transport_mode}
        elif property_path == "/transports/0/playback":
            return self.playback_config
        elif property_path == "/transports/0/record":
            return {"recording": self.recording}
        elif property_path == "/transports/0/clipIndex":
            return {"clipIndex": self.clip_index}
        elif property_path == "/media/workingset":
            return self.get_workingset()
        else:
            return {}

    async def subscribe_property(
        self, websocket: WebSocket, property_path: str
    ) -> None:
        """Subscribe a websocket to property updates."""
        if property_path not in self.subscribers:
            self.subscribers[property_path] = set()
        self.subscribers[property_path].add(websocket)

    async def unsubscribe_property(
        self, websocket: WebSocket, property_path: str
    ) -> None:
        """Unsubscribe a websocket from property updates."""
        if property_path in self.subscribers:
            self.subscribers[property_path].discard(websocket)

    async def notify_property_changed(self, property_path: str) -> None:
        """Notify all subscribers that a property has changed."""
        if property_path in self.subscribers:
            value = self.get_property_value(property_path)
            message = {
                "data": {
                    "action": "propertyValueChanged",
                    "property": property_path,
                    "value": value,
                },
                "type": "event",
            }

            # Send to all subscribers
            for websocket in self.subscribers[property_path].copy():
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception:
                    # Remove disconnected websockets
                    self.subscribers[property_path].discard(websocket)


# Global state instance
mock_state = MockHyperDeckState()

# FastAPI app
app = FastAPI(
    title="Mock BlackMagic HyperDeck API",
    description="Mock implementation of BlackMagic HyperDeck Control API for development",
    version="1.0.0",
)


# Transport Control Endpoints
@app.put("/control/api/v1/transports/0", status_code=204)
async def set_transport_mode(request: TransportMode):
    """Change the overall mode of the device."""
    if request.mode == "InputRecord":
        raise HTTPException(400, detail="Cannot change to InputRecord directly")

    is_recording = mock_state.recording
    if is_recording:
        mock_state.stop_recording()

    mock_state.set_transport_mode(request.mode)
    await mock_state.notify_property_changed("/transports/0")
    if is_recording:
        await mock_state.notify_property_changed("/transports/0/record")


@app.post("/control/api/v1/transports/0/stop", status_code=204)
async def stop_transport():
    """Stop a recording session."""
    if mock_state.recording:
        # Simulate variable finalization delay (0.5-1.5 seconds)
        finalization_delay = random.uniform(0.5, 1.5)
        mock_state.stop_recording(finalization_delay=finalization_delay)
        await mock_state.notify_property_changed("/transports/0")
        await mock_state.notify_property_changed("/transports/0/record")
        await mock_state.notify_property_changed("/timelines/0")


@app.post("/control/api/v1/transports/0/record", status_code=204)
async def start_recording(request: RecordRequest = RecordRequest()):
    """Start a recording session."""
    mock_state.start_recording(request.clipName)
    await mock_state.notify_property_changed("/transports/0")
    await mock_state.notify_property_changed("/transports/0/record")
    await mock_state.notify_property_changed("/timelines/0")


@app.put("/control/api/v1/transports/0/playback", status_code=204)
async def set_playback(request: PlaybackRequest):
    """Set the state of playback."""
    mock_state.set_playback(request)
    await mock_state.notify_property_changed("/transports/0")
    await mock_state.notify_property_changed("/transports/0/playback")
    await mock_state.notify_property_changed("/transports/0/clipIndex")


# Clip Management Endpoints
@app.get("/control/api/v1/transports/0/clip")
async def get_current_clip():
    """Get information about the current clip."""
    # Check if clip should be finalized
    mock_state.finalize_clip_if_ready()

    clip = mock_state.current_clip
    if clip:
        # If clip is not finalized yet, return it without frameCount and clipUniqueId
        # to simulate the real HyperDeck behavior
        if not mock_state.is_clip_finalized:
            # Return incomplete clip data (missing required fields)
            incomplete_clip = clip.model_dump()
            # Remove the fields that aren't ready yet
            incomplete_clip.pop("frameCount", None)
            incomplete_clip.pop("clipUniqueId", None)
            return {"clip": incomplete_clip}
        else:
            return {"clip": clip.model_dump()}
    return {"clip": None}


@app.get("/control/api/v1/clips")
async def get_all_clips():
    """Get information about all stored clips."""
    # Check if clip should be finalized
    mock_state.finalize_clip_if_ready()
    if mock_state.sync_with_disk():
        await mock_state.notify_property_changed("/timelines/0")
        await mock_state.notify_property_changed("/media/workingset")

    return {"clips": [clip.model_dump() for clip in mock_state.clips]}


@app.get("/control/api/v1/media/workingset")
async def get_media_workingset():
    """Get information about the media in the working set."""
    if mock_state.sync_with_disk():
        await mock_state.notify_property_changed("/timelines/0")
    return mock_state.get_workingset()


@app.post("/mock/storage", status_code=204)
async def set_mock_storage(request: MockStorageRequest):
    """Testing hook: adjust the simulated media capacity and usage.

    Lets a test drive the deck towards a full disk without recording hours of footage.
    """
    if request.disk_size is not None:
        mock_state.disk_size = request.disk_size
    if request.reserved_space is not None:
        mock_state.reserved_space = request.reserved_space
    print(
        f"Storage now {mock_state.remaining_space} bytes free "
        f"({mock_state.remaining_record_time}s of record time)"
    )
    await mock_state.notify_property_changed("/media/workingset")


# WebSocket API
@app.websocket("/control/api/v1/event/websocket")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time property updates."""
    await websocket.accept()

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                request = WebSocketRequest(**message)

                if request.data.action == "subscribe":
                    # Subscribe to properties
                    values = {}
                    for prop in request.data.properties:
                        await mock_state.subscribe_property(websocket, prop)
                        values[prop] = mock_state.get_property_value(prop)

                    # Send subscription response
                    response = {
                        "data": {
                            "action": "subscribe",
                            "properties": request.data.properties,
                            "success": True,
                            "values": values,
                        },
                        "type": "response",
                    }
                    if request.id is not None:
                        response["id"] = request.id

                    await websocket.send_text(json.dumps(response))

                elif request.data.action == "unsubscribe":
                    # Unsubscribe from properties
                    for prop in request.data.properties:
                        await mock_state.unsubscribe_property(websocket, prop)

                    # Send unsubscription response
                    response = {
                        "data": {
                            "action": "unsubscribe",
                            "properties": request.data.properties,
                            "success": True,
                        },
                        "type": "response",
                    }
                    if request.id is not None:
                        response["id"] = request.id

                    await websocket.send_text(json.dumps(response))

            except Exception as e:
                # Send error response
                error_response = {
                    "data": {"action": "error", "message": str(e), "success": False},
                    "type": "response",
                }
                await websocket.send_text(json.dumps(error_response))

    except WebSocketDisconnect:
        # Clean up subscriptions for this websocket
        for subscribers in mock_state.subscribers.values():
            subscribers.discard(websocket)


# Health check endpoint
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Mock BlackMagic HyperDeck API",
        "status": "running",
        "transport_mode": mock_state.transport_mode,
        "recording": mock_state.recording,
        "clips_count": len(mock_state.clips),
    }


def start_ftp_server(host: str, port: int) -> None:
    """Serve the simulated media over FTP in a background thread.

    Real HyperDecks expose their media over FTP, and that is the only way to delete
    recordings remotely, so storage management needs it to be present in the mock.
    """
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer

    authorizer = DummyAuthorizer()
    # HyperDecks allow anonymous access with full permissions over their media
    authorizer.add_anonymous(str(mock_state.media_dir), perm="elradfmwMT")

    handler = FTPHandler
    handler.authorizer = authorizer
    handler.banner = "Mock HyperDeck FTP"

    server = FTPServer((host, port), handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"handle_exit": False}, daemon=True
    )
    thread.start()
    print(f"FTP server: ftp://{host}:{port}/ (serving {mock_state.media_dir})")


def run_mock_server(
    host: str = "127.0.0.1",
    port: int = 8001,
    ftp_port: int = 2121,
    disk_size: int = DEFAULT_DISK_SIZE,
):
    """Run the mock HyperDeck API server."""
    mock_state.disk_size = disk_size

    print(f"Starting Mock BlackMagic HyperDeck API server on {host}:{port}")
    print(f"API base URL: http://{host}:{port}/control/api/v1")
    print(f"WebSocket URL: ws://{host}:{port}/control/api/v1/events/websocket")
    print(f"Health check: http://{host}:{port}/")
    print(f"Simulated media: {disk_size} bytes on volume '{VOLUME_NAME}'")

    start_ftp_server(host, ftp_port)

    try:
        uvicorn.run(app, host=host, port=port)
    finally:
        shutil.rmtree(mock_state.media_dir, ignore_errors=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mock BlackMagic HyperDeck API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to")
    parser.add_argument(
        "--ftp-port",
        type=int,
        default=2121,
        help="Port for the mock FTP server. Real HyperDecks use 21, which normally "
        "requires root, so the mock defaults to 2121",
    )
    parser.add_argument(
        "--disk-size",
        type=int,
        default=DEFAULT_DISK_SIZE,
        help="Simulated media capacity in bytes",
    )

    args = parser.parse_args()
    run_mock_server(
        host=args.host,
        port=args.port,
        ftp_port=args.ftp_port,
        disk_size=args.disk_size,
    )
