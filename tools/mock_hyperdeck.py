# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi",
#     "uvicorn",
#     "websockets",
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
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
import uvicorn


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


class TimelineClip(BaseModel):
    clipUniqueId: int
    frameCount: int
    timelineIn: int
    durationTimecode: str = "<dummy>"
    clipIn: int = 0
    inTimecode: str = "<dummy>"
    timelineInTimecode: str = "<dummy>"


class MediaWorkingSetEntry(BaseModel):
    index: int = 0
    activeDisk: bool = True
    volume: str = "Mock SSD"
    deviceName: str = "Mock SSD"
    remainingRecordTime: int = 7200
    totalSpace: int = 1000000000000
    remainingSpace: int = 500000000000
    clipCount: int = 0


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

    clip_index: int
    """Index of the clip the finalization applies to"""
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
        self.media: MediaWorkingSetEntry = MediaWorkingSetEntry()
        self.subscribers: Dict[str, Set[WebSocket]] = {}
        self.clip_start_time: float = time.time()
        self._pending_finalization: Optional[PendingFinalization] = None
        """Pending finalization data including finalization time"""

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
            clip_id = self.timeline_clips[self.clip_index].clipUniqueId - 1337
            if clip_id < len(self.clips):
                return self.clips[clip_id]
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
        # Any previous clip is always finalized before a new recording begins
        self.finalize_clip_if_ready(force=True)

        if not clip_name:
            clip_name = f"recording_{int(time.time())}.mp4"

        self.set_transport_mode("InputRecord")

        # Create new clip
        new_clip_id = len(self.clips) + 1337
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
        self.media.clipCount = len(self.clips)

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
                    clip_index=self.clip_index,
                    frameCount=final_frames,
                    durationTimecode=self._frames_to_timecode(final_frames),
                    fileSize=2500000,
                    timeline_frameCount=final_frames,
                    finalization_time=time.time() + finalization_delay,
                )
            else:
                # Finalize immediately
                current_clip.frameCount = final_frames
                current_clip.durationTimecode = self._frames_to_timecode(final_frames)
                current_clip.fileSize = 2500000

                # Update the timeline clip
                if self.clip_index < len(self.timeline_clips):
                    timeline_clip = self.timeline_clips[self.clip_index]
                    timeline_clip.frameCount = final_frames
                    timeline_clip.durationTimecode = current_clip.durationTimecode

                self._pending_finalization = None

        self.set_transport_mode("InputPreview")

    def finalize_clip_if_ready(self, force: bool = False) -> bool:
        """Finalize the pending clip if its finalization delay has elapsed.

        Args:
            force: Finalize the clip even if the delay has not elapsed yet

        Returns True if a clip was finalized by this call.
        """
        if self._pending_finalization is not None and (force or self.is_clip_finalized):
            pending = self._pending_finalization
            self._pending_finalization = None

            if pending.clip_index < len(self.clips):
                # Apply the pending finalization to the clip it was recorded for
                clip = self.clips[pending.clip_index]
                clip.frameCount = pending.frameCount
                clip.durationTimecode = pending.durationTimecode
                clip.fileSize = pending.fileSize

            if pending.clip_index < len(self.timeline_clips):
                timeline_clip = self.timeline_clips[pending.clip_index]
                timeline_clip.frameCount = pending.timeline_frameCount
                timeline_clip.durationTimecode = pending.durationTimecode

            return True
        return False

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
            self.media.clipCount = len(self.clips)
            return {"size": 1, "workingset": [self.media.model_dump()]}
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
    await mock_state.notify_property_changed("/media/workingset")


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
    if mock_state.finalize_clip_if_ready():
        await mock_state.notify_property_changed("/timelines/0")

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
    if mock_state.finalize_clip_if_ready():
        await mock_state.notify_property_changed("/timelines/0")

    return {"clips": [clip.model_dump() for clip in mock_state.clips]}


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


def run_mock_server(host: str = "127.0.0.1", port: int = 8001):
    """Run the mock HyperDeck API server."""
    print(f"Starting Mock BlackMagic HyperDeck API server on {host}:{port}")
    print(f"API base URL: http://{host}:{port}/control/api/v1")
    print(f"WebSocket URL: ws://{host}:{port}/control/api/v1/events/websocket")
    print(f"Health check: http://{host}:{port}/")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mock BlackMagic HyperDeck API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to")

    args = parser.parse_args()
    run_mock_server(host=args.host, port=args.port)
