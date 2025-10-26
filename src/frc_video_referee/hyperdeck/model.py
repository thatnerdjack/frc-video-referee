from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, TypeAdapter


class TransportMode(Enum):
    """The overall mode of the HyperDeck"""

    InputPreview = "InputPreview"
    """Displaying the live input feed"""
    InputRecord = "InputRecord"
    """Recording the live input feed"""
    Output = "Output"
    """Displaying a recorded clip"""


class TransportModeRequest(BaseModel):
    """PUT /transports/0 request body to set the transport mode"""

    mode: TransportMode
    """The transport mode to set"""


class RecordRequest(BaseModel):
    """PUT /transports/0/record request body to start or stop recording"""

    clipName: str | None = None
    """Optional name for the clip being recorded. If not provided, a default name will be used."""


class PlaybackType(Enum):
    """The current mode of the playback interface"""

    Play = "Play"
    """Playing a clip"""
    Jog = "Jog"
    """Moving through a clip frame by frame"""
    Shuttle = "Shuttle"
    """Moving through a clip at variable speed"""
    Var = "Var"


class PlaybackState(BaseModel):
    """PUT /transports/0/playback request and websocket message body for playback state"""

    type: PlaybackType
    """The playback mode"""
    loop: bool
    """Whether to loop the playback"""
    singleClip: bool
    """Whether to play a single clip or all clips"""
    speed: float
    """Playback speed, where 1.0 is normal speed"""
    position: int
    """Playback position on the timeline in units of frames. 0 is the first frame of the timeline"""


PLACEHOLDER_PLAYBACK_STATE = PlaybackState(
    type=PlaybackType.Jog,
    loop=False,
    singleClip=True,
    speed=1.0,
    position=0,
)


class CodecFormat(BaseModel):
    """Codec format for a recorded clip"""

    codec: str
    """Codec used for the clip, e.g. "H.264", "ProRes"."""
    container: str
    """Container format used for the clip, e.g. "MOV", "MP4"."""


class VideoFormat(BaseModel):
    """Video format for a recorded clip"""

    name: str
    """Name of the video format, e.g. "1920x1090p29.97"."""
    frameRate: float
    """Frame rate of the video format, e.g. "29.97"."""
    height: int
    """Height of the video in pixels"""
    width: int
    """Width of the video in pixels"""
    interlaced: bool
    """Whether the video is interlaced or progressive"""


class Clip(BaseModel):
    """Information about a recorded clip"""

    clipUniqueId: int
    """Unique ID to identify the clip"""
    filePath: str
    """File path to the clip on the HyperDeck"""
    fileSize: int
    """Size of the clip file in bytes"""
    codecFormat: CodecFormat
    """Codec and container format used for the clip"""
    videoFormat: VideoFormat
    """Video format of the clip"""
    startTimecode: str | None = None
    """Start timecode of the clip in HH:MM:SS:FF format"""
    durationTimecode: str
    """Duration of the clip in HH:MM:SS:FF format"""
    frameCount: int
    """Total number of frames in the clip"""


class ClipResponse(BaseModel):
    """Response for a single clip request"""

    clip: Clip | None
    """Information about the current clip, if one exists"""


class ClipList(BaseModel):
    """List of clips recorded on the HyperDeck"""

    clips: List[Clip]
    """List of clips recorded on the HyperDeck"""


class RecordingState(BaseModel):
    """Indicator for whether a recording is in progress"""

    recording: bool
    """True if a recording is currently in progress, False otherwise"""


class ClipIndex(BaseModel):
    """Current clip index on the timeline"""

    clipIndex: int
    """Index of the currently selected clip on the timeline. 0 is the first clip."""


class TimelineClip(BaseModel):
    """Representation of a clip on the timeline"""

    clipUniqueId: int
    """Unique ID of the clip"""
    frameCount: int
    """Number of frames in in the portion of the clip on the timeline"""
    durationTimecode: str
    """Duration of the clip on the timeline in HH:MM:SS:FF format"""
    clipIn: int
    """First frame of the clip on the timeline"""
    inTimecode: str
    """First frame of the clip on the timeline in HH:MM:SS:FF format"""
    timelineIn: int
    """First frame of the clip on the timeline, relative to the start of the timeline"""
    timelineInTimecode: str
    """First frame of the clip on the timeline, relative to the start of the timeline, in HH:MM:SS:FF format"""


class TimelineClipList(BaseModel):
    """List of clips on the timeline"""

    clips: List[TimelineClip]
    """List of clips on the timeline"""

class MediaWorkingSetEntry(BaseModel):
    """Data about a media storage device on the HyperDeck"""

    index: int
    """Index of the media device"""
    activeDisk: bool
    """Whether this media is the active disk"""
    volume: str
    """Volume name of the media"""
    deviceName: str
    """Device name of the media"""
    remainingRecordTime: int
    """Remaining record time on the media in seconds"""
    totalSpace: int
    """Total space in bytes on the media"""
    remainingSpace: int
    """Remaining space in bytes on the media"""
    clipCount: int
    """Number of clips stored on the media"""

class MediaWorkingSet(BaseModel):
    """Information about the working set of media on the HyperDeck"""

    size: int
    """Number of media devices in the working set"""
    workingset: List[MediaWorkingSetEntry | None]
    """List of media devices in the working set"""

################################
# HyperDeck WebSocket Messages #
################################


class SubscribeRequest(BaseModel):
    """Request data for subscribing to websocket events"""

    action: Literal["subscribe"] = "subscribe"
    properties: List[str]
    """List of properties to subscribe to for updates"""


class UnsubscribeRequest(BaseModel):
    """Request data for unsubscribing from websocket events"""

    action: Literal["unsubscribe"] = "unsubscribe"
    properties: List[str]
    """List of properties to unsubscribe from"""


class SubscribeResponse(BaseModel):
    """Response data for a subscription request"""

    action: Literal["subscribe"]
    properties: List[str]
    """List of properties from the subscribe request"""
    success: bool
    """Whether the subscription was successful"""
    values: Dict[str, Any] = {}
    """Current values for the subscribed properties if the subscription was successful"""


class UnsubscribeResponse(BaseModel):
    """Response data for a unsubscribe request"""

    action: Literal["unsubscribe"]
    properties: List[str]
    """List of properties from the unsubscribe request"""
    success: bool
    """Whether the unsubscribe was successful"""


class RequestMessage(BaseModel):
    type: Literal["request"] = "request"
    data: Annotated[
        SubscribeRequest | UnsubscribeRequest, Field(discriminator="action")
    ]
    id: Optional[int] = None
    """Optional request ID for tracking the request"""


class ResponseMessage(BaseModel):
    type: Literal["response"]
    data: Annotated[
        SubscribeResponse | UnsubscribeResponse, Field(discriminator="action")
    ]
    id: Optional[int] = None
    """Optional request ID to match the response to the original request"""


class EventData(BaseModel):
    action: Literal["propertyValueChanged"]
    property: str
    """Name of the property that changed"""
    value: Any
    """New value of the property"""


class WebsocketConnectedMessage(BaseModel):
    action: Literal["websocketOpened"]
    """Indicates that the websocket connection was established successfully"""


class EventMessage(BaseModel):
    type: Literal["event"]
    data: EventData | WebsocketConnectedMessage
    """Event data containing the property name and its new value"""


InboundWebsocketMessage = TypeAdapter(
    Annotated[ResponseMessage | EventMessage, Field(discriminator="type")]
)

OutboundWebsocketMessage = TypeAdapter(
    Annotated[RequestMessage, Field(discriminator="type")]
)
