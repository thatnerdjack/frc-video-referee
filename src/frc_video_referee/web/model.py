from typing import Dict, List, Literal
from pydantic import BaseModel, TypeAdapter

from frc_video_referee.cheesy_arena.model import MatchWithResultAndSummary
from frc_video_referee.db.model import RecordedMatch
from frc_video_referee.hyperdeck.model import TransportMode


class ControllerStatus(BaseModel):
    selected_match_id: str | None
    recording: bool
    """Indicates if the controller is currently recording a match"""
    realtime_data: bool
    """Indicates if the current match is using real-time data"""


class MatchListEntry(BaseModel):
    var_data: RecordedMatch
    """VAR server data for the match"""

    arena_data: MatchWithResultAndSummary | None = None
    """Arena data associated with the match, if available"""

    clip_available: bool = False
    """Indicates if the match clip is available for playback"""


class HyperdeckStatus(BaseModel):
    transport_mode: TransportMode
    """Status of the hyperdeck's output"""
    playing: bool
    """Indicates if the hyperdeck is currently playing a clip"""
    clip_time: float
    """Current time position in the clip, in seconds"""
    remaining_record_time: int
    """Remaining record time on the HyperDeck in seconds"""
    total_space: int
    """Total disk space on the HyperDeck in bytes"""
    remaining_space: int
    """Remaining disk space on the HyperDeck in bytes"""


class WebsocketEvent(BaseModel):
    """Base class for WebSocket events"""

    type: Literal["event"] = "event"
    """Type of the message, always 'event' for WebSocket events"""
    event_type: str
    """Type of the event, e.g. 'match_update', 'arena_state'"""
    data: dict
    """Data associated with the event, serialized as a dictionary"""


class WebsocketSubscribeRequest(BaseModel):
    """Request model for subscribing to WebSocket events"""

    type: Literal["subscribe"] = "subscribe"
    """Type of the message, always 'subscribe' for subscription requests"""
    event_types: List[str]
    """Type of the event to subscribe to, e.g. 'match_update', 'arena_state'"""
    request_id: int | None = None
    """Optional request ID for tracking the subscription request"""


class WebsocketUnsubscribeRequest(BaseModel):
    """Request model for unsubscribing from WebSocket events"""

    type: Literal["unsubscribe"] = "unsubscribe"
    """Type of the message, always 'unsubscribe' for unsubscription requests"""
    event_types: List[str]
    """Type of the event to unsubscribe from, e.g. 'match_update', 'arena_state'"""
    request_id: int | None = None
    """Optional request ID for tracking the unsubscription request"""


class WebsocketSubscribeResponse(BaseModel):
    """Response model for a subscription request"""

    type: Literal["subscribe"] = "subscribe"
    """Type of the message, always 'subscribe' for subscription responses"""
    initial_data: Dict[str, dict]
    """Data associated with the subscription, including current values for subscribed events"""
    request_id: int | None = None
    """Optional request ID for tracking the subscription response"""


class WebsocketUnsubscribeResponse(BaseModel):
    """Response model for an unsubscription request"""

    type: Literal["unsubscribe"] = "unsubscribe"
    """Type of the message, always 'unsubscribe' for unsubscription responses"""
    unsubscribed_event_types: List[str]
    """List of event types that were successfully unsubscribed from"""
    request_id: int | None = None
    """Optional request ID for tracking the unsubscription response"""


class WebsocketCommand(BaseModel):
    """Websocket command wrapper"""

    type: Literal["command"] = "command"
    """Type of the message, always 'command' for command requests"""
    command: str
    """Name of the command being requested"""
    data: dict
    """Data associated with the command request, serialized as a dictionary"""


class WebsocketPing(BaseModel):
    """Request model for keepalive ping"""

    type: Literal["ping"] = "ping"
    """Type of the message, always 'ping' for ping requests"""
    timestamp: float | None = None
    """Optional timestamp for tracking round-trip time"""


class WebsocketPong(BaseModel):
    """Response model for keepalive pong"""

    type: Literal["pong"] = "pong"
    """Type of the message, always 'pong' for pong responses"""
    timestamp: float | None = None
    """Optional timestamp echoed from the ping request"""


InboundWebsocketMessage = TypeAdapter(
    WebsocketSubscribeRequest
    | WebsocketUnsubscribeRequest
    | WebsocketCommand
    | WebsocketPing
)
OutboundWebsocketMessage = TypeAdapter(
    WebsocketEvent
    | WebsocketSubscribeResponse
    | WebsocketUnsubscribeResponse
    | WebsocketPong
)
