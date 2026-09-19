import asyncio
import enum
import logging
from typing import Awaitable, Callable, Dict, List
import httpx
from pydantic import BaseModel, ValidationError
import websockets

from frc_video_referee.hyperdeck.model import (
    PLACEHOLDER_PLAYBACK_STATE,
    Clip,
    ClipList,
    ClipResponse,
    EventData,
    EventMessage,
    InboundWebsocketMessage,
    MediaWorkingSet,
    MediaWorkingSetEntry,
    PlaybackState,
    PlaybackType,
    RecordRequest,
    RequestMessage,
    ResponseMessage,
    SubscribeRequest,
    SubscribeResponse,
    TimelineClip,
    TimelineClipList,
    TransportMode,
    TransportModeRequest,
)
from frc_video_referee.utils import ExitServer

logger = logging.getLogger(__name__)


class HyperdeckClientSettings(BaseModel):
    address: str = "localhost:8001"
    clip_finalize_poll_interval: float = 0.25
    """Interval in seconds between polling attempts when waiting for clip to finalize after recording stops"""
    clip_finalize_timeout: float = 5.0
    """Maximum time in seconds to wait for clip to finalize after recording stops"""


class HyperdeckNotifier(enum.Enum):
    """Notifiers that can be subscribed by the rest of the system"""

    CONNECTION_STATE_UPDATED = enum.auto()
    """Connection state to the HyperDeck has changed"""
    TRANSPORT_MODE_UPDATED = enum.auto()
    """Transport mode of the HyperDeck has changed"""
    PLAYBACK_STATE_UPDATED = enum.auto()
    """Playback state of the HyperDeck has changed"""
    CLIP_LIST_UPDATED = enum.auto()
    """The list of playable clips on the HyperDeck has updated"""
    DISK_SPACE_UPDATED = enum.auto()
    """The disk space information on the HyperDeck has updated"""


class HyperdeckClient:
    def __init__(self, settings: HyperdeckClientSettings):
        self._settings = settings
        self._clips: Dict[int, Clip] = {}
        """Dictionary mapping clip IDs to Clip objects"""
        self._timeline: Dict[int, TimelineClip] = {}
        """Dictionary mapping clip IDs to their timeline representation"""
        self._connected = False
        """Whether the client is currently connected to the HyperDeck"""

        self.playback_state = PLACEHOLDER_PLAYBACK_STATE
        """Current playback state"""
        self.transport_mode = TransportMode.InputPreview
        """Current transport mode"""
        self.workingset: MediaWorkingSet = MediaWorkingSet(size=0, workingset=[])
        """Current storage information"""

        self._subscribers: Dict[
            HyperdeckNotifier, List[Callable[[], Awaitable[None]]]
        ] = {notifier: [] for notifier in HyperdeckNotifier}
        """Subscribers for various arena state changes"""

    def subscribe(
        self, notifier: HyperdeckNotifier, callback: Callable[[], Awaitable[None]]
    ):
        """Subscribe to a specific HyperDeck state change."""
        self._subscribers[notifier].append(callback)

    @property
    def connected(self) -> bool:
        """True if the client is connected to the HyperDeck, False otherwise"""
        return self._connected

    @property
    def recording(self) -> bool:
        """True if a recording is currently in progress, False otherwise"""
        return self.transport_mode == TransportMode.InputRecord

    def has_playable_clip(self, clip_id: int) -> bool:
        """Check if a clip with the given ID exists in the HyperDeck and is available for playback."""
        return clip_id in self._clips and clip_id in self._timeline

    def get_clip(self, clip_id: int) -> Clip | None:
        """Get a Clip object by its ID."""
        return self._clips.get(clip_id)

    async def run(self) -> None:
        """Run the Hyperdeck client."""
        async with httpx.AsyncClient(
            base_url=f"http://{self._settings.address}/control/api/v1"
        ) as client:
            logger.info("Starting Hyperdeck client")
            self._client = client

            while True:
                try:
                    await self._run_internal(client)
                except ExitServer:
                    raise
                except httpx.RequestError as e:
                    logger.exception(f"HTTP request error: {e}")
                except Exception as e:
                    logger.exception(f"Internal Hyperdeck client error: {e}")
                logger.info("Reconnecting in 3 seconds...")
                await asyncio.sleep(3)

    async def _run_internal(self, client: httpx.AsyncClient) -> None:
        async with websockets.connect(
            f"ws://{self._settings.address}/control/api/v1/event/websocket"
        ) as websocket:
            logger.info("HyperDeck connection established")
            self._connected = True
            await self._notify(HyperdeckNotifier.CONNECTION_STATE_UPDATED)

            try:
                await self._get_full_clip_list(client)

                subscribe_msg = RequestMessage(
                    data=SubscribeRequest(
                        properties=[
                            "/transports/0/playback",
                            "/transports/0",
                            "/timelines/0",
                            "/media/workingset",
                        ]
                    )
                )
                await websocket.send(subscribe_msg.model_dump_json(exclude_none=True))

                while True:
                    message_bytes = await websocket.recv(decode=False)
                    message = InboundWebsocketMessage.validate_json(message_bytes)

                    match message:
                        case ResponseMessage():
                            if isinstance(message.data, SubscribeResponse):
                                if message.data.success:
                                    logger.info(
                                        f"Subscribed to properties: {message.data.properties}"
                                    )
                                    for prop, value in message.data.values.items():
                                        await self._handle_property_change(prop, value)
                                else:
                                    raise RuntimeError("HyperDeck subscription failed")
                        case EventMessage():
                            match message.data:
                                case EventData():
                                    logger.debug(
                                        f"Received event: {message.data.property} = {message.data.value}"
                                    )
                                    await self._handle_property_change(
                                        message.data.property, message.data.value
                                    )
            finally:
                self._connected = False
                logger.info("HyperDeck connection closed")
                await self._notify(HyperdeckNotifier.CONNECTION_STATE_UPDATED)

    async def _handle_property_change(self, property: str, value: dict) -> None:
        """Handle property changes received from the HyperDeck WebSocket."""
        match property:
            case "/transports/0/playback":
                self.playback_state = PlaybackState.model_validate(value)
                await self._notify(HyperdeckNotifier.PLAYBACK_STATE_UPDATED)
            case "/transports/0":
                mode = TransportModeRequest.model_validate(value)
                self.transport_mode = mode.mode
                await self._notify(HyperdeckNotifier.TRANSPORT_MODE_UPDATED)
            case "/timelines/0":
                # Update our view of the timeline structure
                timeline = TimelineClipList.model_validate(value)
                old_timeline_keys = set(self._timeline.keys())
                self._timeline = {clip.clipUniqueId: clip for clip in timeline.clips}
                new_timeline_keys = set(self._timeline.keys())
                if old_timeline_keys != new_timeline_keys:
                    await self._notify(HyperdeckNotifier.CLIP_LIST_UPDATED)
            case "/media/workingset":
                self.workingset = MediaWorkingSet.model_validate(value)
                await self._notify(HyperdeckNotifier.DISK_SPACE_UPDATED)

    async def _get_full_clip_list(self, client: httpx.AsyncClient) -> None:
        """Fetch the full list of clips from the HyperDeck."""
        response = await client.get("/clips")
        response.raise_for_status()
        clip_list = ClipList.model_validate_json(response.text)
        logger.info(f"Retrieved {len(clip_list.clips)} clips from HyperDeck")

        old_clip_keys = set(self._clips.keys())
        self._clips = {clip.clipUniqueId: clip for clip in clip_list.clips}
        new_clip_keys = set(self._clips.keys())

        if old_clip_keys != new_clip_keys:
            await self._notify(HyperdeckNotifier.CLIP_LIST_UPDATED)

    async def start_recording(self, clip_name: str | None = None) -> None:
        """Start recording a new clip.

        The HyperDeck does not report the ID of the new clip until the recording has been
        stopped and the clip has been finalized, so no ID is returned here.
        """
        request = RecordRequest(clipName=clip_name)
        response = await self._client.post(
            "/transports/0/record",
            content=request.model_dump_json(exclude_none=True),
        )
        response.raise_for_status()

        logger.info(f"Started recording clip: {clip_name}")

    async def discard_recording(self) -> None:
        """Stop the current recording without waiting for its clip to be finalized.

        Used for recordings whose contents are not needed, such as pre-roll segments which
        are restarted while waiting for a match to start.
        """
        response = await self._client.post("/transports/0/stop")
        response.raise_for_status()
        logger.debug("Stopped recording without waiting for finalization")

    async def stop_recording(self) -> int:
        """Stop the current recording and return the ID of the finalized clip."""
        response = await self._client.post("/transports/0/stop")
        response.raise_for_status()
        logger.info("Stopped recording")

        # Poll the clip endpoint until the HyperDeck finalizes the recording
        # and populates clipUniqueId and frameCount fields
        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= self._settings.clip_finalize_timeout:
                raise TimeoutError(
                    f"Timed out after {self._settings.clip_finalize_timeout}s waiting for clip to finalize"
                )

            # Refresh the clip's metadata
            response = await self._client.get("/transports/0/clip")
            response.raise_for_status()

            try:
                clip_data = ClipResponse.model_validate_json(response.text)
            except ValidationError:
                # Validation error - clip not yet finalized, continue polling
                logger.debug(
                    f"Clip not yet finalized after {elapsed:.2f}s, retrying..."
                )
            else:
                # Check if the clip has been finalized
                if clip_data.clip is not None:
                    clip_id = clip_data.clip.clipUniqueId
                    frame_count = clip_data.clip.frameCount
                    logger.info(
                        f"Stopped recording clip, ID is {clip_id} with {frame_count} frames"
                    )
                    self._clips[clip_id] = clip_data.clip
                    await self._notify(HyperdeckNotifier.CLIP_LIST_UPDATED)
                    return clip_id

            # Wait before polling again
            await asyncio.sleep(self._settings.clip_finalize_poll_interval)

    def _get_timeline_position(self, clip_id: int, time_frames: int) -> int:
        """Get the timeline position for a specific clip and time frame."""
        try:
            timeline_clip = self._timeline[clip_id]
        except KeyError:
            logger.error(
                f"Attempted to get timeline position for unknown clip ID {clip_id}. Warping to start of timeline"
            )
            return 0

        frame_in_clip = time_frames
        frame_in_clip = max(
            timeline_clip.clipIn, frame_in_clip
        )  # Ensure we don't go before the clip's start
        frame_in_clip = min(
            frame_in_clip, timeline_clip.clipIn + timeline_clip.frameCount - 1
        )  # Ensure we don't go past the clip's end

        return timeline_clip.timelineIn + frame_in_clip - timeline_clip.clipIn

    async def warp_to_clip(self, clip_id: int, time_sec: float) -> None:
        """Warp to a specific clip by its ID and timestamp within the clip."""
        try:
            clip = self._clips[clip_id]
        except KeyError:
            raise ValueError(f"Clip ID '{clip_id}' not found in HyperDeck") from None

        time_frames = int(time_sec * clip.videoFormat.frameRate)

        timeline_position = self._get_timeline_position(clip_id, time_frames)
        request = PlaybackState(
            type=PlaybackType.Jog,
            loop=False,
            singleClip=True,
            speed=0.0,
            position=timeline_position,
        )
        response = await self._client.put(
            "/transports/0/playback", content=request.model_dump_json()
        )
        response.raise_for_status()
        # Do it again after the clip loads to actually set the time?
        response = await self._client.put(
            "/transports/0/playback", content=request.model_dump_json()
        )
        response.raise_for_status()

    async def show_live_view(self) -> None:
        """Show the live view from the HyperDeck."""
        request = TransportModeRequest(mode=TransportMode.InputPreview)
        response = await self._client.put(
            "/transports/0", content=request.model_dump_json()
        )
        response.raise_for_status()

    async def _notify(self, notifier: HyperdeckNotifier):
        """Notify subscribers of a state change."""
        for callback in self._subscribers[notifier]:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Error notifying subscriber for {notifier.name}: {e}")

    def get_current_time_within_clip(self, clip_id: int) -> float:
        """Get the current time within a specific clip."""
        if clip_id not in self._timeline or clip_id not in self._clips:
            return 0.0

        clip = self._clips[clip_id]
        timeline_entry = self._timeline[clip_id]
        clip_start_frame = timeline_entry.timelineIn
        clip_frame_count = timeline_entry.frameCount

        current_frame = self.playback_state.position - clip_start_frame
        current_frame = max(0, current_frame)  # Ensure we don't go negative
        current_frame = min(
            current_frame, clip_frame_count - 1
        )  # Ensure we don't exceed the clip length

        return (timeline_entry.clipIn + current_frame) / clip.videoFormat.frameRate

    def get_active_working_set(self) -> MediaWorkingSetEntry:
        """Get the currently active working set entry, if any."""
        for entry in self.workingset.workingset:
            if entry and entry.activeDisk:
                return entry
        return MediaWorkingSetEntry(
            index=0,
            activeDisk=True,
            volume="",
            deviceName="",
            remainingRecordTime=0,
            totalSpace=1,
            remainingSpace=0,
            clipCount=0,
        )
