"""
FastAPI server for FRC Video Referee application.
"""

from copy import copy
from pathlib import Path
import logging
from typing import Awaitable, Callable, Dict, Generic, NamedTuple, Set, TypeVar

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import ValidationError

from frc_video_referee.settings import SettingsModel
from frc_video_referee.web.model import (
    InboundWebsocketMessage,
    WebsocketCommand,
    WebsocketEvent,
    WebsocketPing,
    WebsocketPong,
    WebsocketSubscribeRequest,
    WebsocketSubscribeResponse,
    WebsocketUnsubscribeRequest,
    WebsocketUnsubscribeResponse,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class MatchRankingPointSettings(SettingsModel):
    """Ranking points awarded for the outcome of a match.

    Off-season events frequently deviate from the official values, so these are
    configurable rather than baked in to the panel.
    """

    win: int = 3
    """Ranking points awarded to an alliance which wins the match"""

    tie: int = 1
    """Ranking points awarded to each alliance when the match is tied"""

    loss: int = 0
    """Ranking points awarded to an alliance which loses the match"""


class BonusRankingPointSettings(SettingsModel):
    """Display and scoring configuration for one bonus ranking point.

    Each bonus has its own subclass so that overriding one field in a config file
    leaves the remaining defaults for that bonus intact.
    """

    enabled: bool = True
    """Whether this ranking point is in use at this event. Disabled RPs are hidden from the panel"""

    label: str = ""
    """Name shown for this ranking point in the panel"""

    threshold: int = 0
    """Value which must be reached to earn this ranking point, used for the panel's progress display"""

    value: int = 1
    """Ranking points awarded for earning this bonus"""


class EnergizedRankingPointSettings(BonusRankingPointSettings):
    """Configuration for the first Fuel bonus ranking point"""

    label: str = "Energized"
    """Name shown for this ranking point in the panel"""

    threshold: int = 100
    """Fuel count needed for the bonus, matching Cheesy Arena's Energized bonus threshold"""


class SuperchargedRankingPointSettings(BonusRankingPointSettings):
    """Configuration for the second Fuel bonus ranking point"""

    label: str = "Supercharged"
    """Name shown for this ranking point in the panel"""

    threshold: int = 360
    """Fuel count needed for the bonus, matching Cheesy Arena's Supercharged bonus threshold"""


class TraversalRankingPointSettings(BonusRankingPointSettings):
    """Configuration for the Tower bonus ranking point"""

    label: str = "Traversal"
    """Name shown for this ranking point in the panel"""

    threshold: int = 50
    """Tower points needed for the bonus, matching Cheesy Arena's Traversal bonus threshold"""


class UISettings(SettingsModel):
    """Settings for the user-facing control and status panels"""

    swap_red_blue: bool = False
    """Swap the position of the red and blue score panels. The default matches the view from the scoring table"""

    match_rp: MatchRankingPointSettings = MatchRankingPointSettings()
    """Ranking points awarded for winning, tying, or losing a match"""

    energized_rp: EnergizedRankingPointSettings = EnergizedRankingPointSettings()
    """First Fuel bonus ranking point"""

    supercharged_rp: SuperchargedRankingPointSettings = (
        SuperchargedRankingPointSettings()
    )
    """Second Fuel bonus ranking point"""

    traversal_rp: TraversalRankingPointSettings = TraversalRankingPointSettings()
    """Tower bonus ranking point"""


class WebsocketManager:
    class Notifier(NamedTuple):
        event_type: str
        emitter: Callable[[], Dict]
        subscribers: Set[WebSocket] = set()

    class CommandHandler(NamedTuple, Generic[T]):
        command_name: str
        data_type: type[T]
        handler: Callable[[T], Awaitable[None]]

    def __init__(self, ui_settings: UISettings):
        self._ui_settings = ui_settings
        self._notifiers: Dict[str, WebsocketManager.Notifier] = {}
        self._commands: Dict[str, WebsocketManager.CommandHandler] = {}
        self._clients: Set[WebSocket] = set()
        self.add_event_type(
            "ui_settings", lambda: self._ui_settings.model_dump(exclude_none=True)
        )

    async def set_ui_settings(self, ui_settings: UISettings):
        self._ui_settings = ui_settings
        await self.notify("ui_settings")

    def add_event_type(self, event_type: str, emitter: Callable[[], Dict]):
        """Add a notification type to the manager."""
        assert event_type not in self._notifiers, (
            f"Event type '{event_type}' already exists."
        )
        self._notifiers[event_type] = WebsocketManager.Notifier(
            event_type=event_type, emitter=emitter
        )
        logger.debug(f"Registering event type: {event_type}")

    def add_command_handler(
        self,
        command_name: str,
        data_type: type[T],
        handler: Callable[[T], Awaitable[None]],
    ):
        """Add a command handler for a specific command type."""
        if command_name in self._notifiers:
            raise ValueError(f"Command handler for '{command_name}' already exists.")
        self._commands[command_name] = WebsocketManager.CommandHandler(
            command_name=command_name, data_type=data_type, handler=handler
        )
        logger.debug(f"Registered command handler for: {command_name}")

    async def notify(self, event_type: str, data: Dict | None = None):
        """Notify all subscribers of a specific event type."""
        try:
            notifier = self._notifiers[event_type]
        except KeyError:
            logger.warning(f"Event type '{event_type}' not found.")
            return

        if data is None:
            # Get the current state from the emitter function
            data = notifier.emitter()

        subscribers = copy(notifier.subscribers)
        logger.debug(f"Notifying {len(subscribers)} subscribers of {event_type}")

        event = WebsocketEvent(
            event_type=event_type,
            data=data,
        )
        event_text = event.model_dump_json(exclude_none=True)
        for subscriber in subscribers:
            try:
                await subscriber.send_text(event_text)
            except WebSocketDisconnect:
                notifier.subscribers.discard(subscriber)

    async def reload_clients(self):
        """Notify all clients to reload the page."""
        logger.info("Requesting reload on all panels")
        for client in self._clients:
            try:
                await client.send_json({"type": "reload"})
            except WebSocketDisconnect:
                self._clients.discard(client)

    async def serve_client(self, websocket: WebSocket):
        """Serve a WebSocket client connection."""
        await websocket.accept()
        logger.info(f"WebSocket client 0x{id(websocket):x} connected")
        subscriptions = set()
        self._clients.add(websocket)
        try:
            async for message in websocket.iter_text():
                try:
                    msg = InboundWebsocketMessage.validate_json(message)
                    logger.debug(f"Received message: {msg}")
                except ValidationError as e:
                    logger.error(f"Invalid WebSocket message: {e}")
                    continue

                match msg:
                    case WebsocketSubscribeRequest():
                        # Request to subscribe to one or more event types
                        event_types = msg.event_types
                        logger.debug(
                            f"Processing subscription request for: {event_types}"
                        )

                        initial_data = {}
                        for event_type in event_types:
                            try:
                                notifier = self._notifiers[event_type]
                            except KeyError:
                                logger.warning(
                                    f"Unknown event type '{event_type}' in subscription request"
                                )
                                continue
                            initial_data[event_type] = notifier.emitter()
                            notifier.subscribers.add(websocket)
                            subscriptions.add(event_type)

                        logger.debug(
                            f"Responding to subscription request for: {event_types} with values for {list(initial_data.keys())}"
                        )
                        response = WebsocketSubscribeResponse(
                            initial_data=initial_data,
                            request_id=msg.request_id,
                        )
                        await websocket.send_text(
                            response.model_dump_json(exclude_none=True)
                        )

                    case WebsocketUnsubscribeRequest():
                        # Request to drop one or more subscriptions
                        event_types = msg.event_types
                        for event_type in event_types:
                            if event_type in subscriptions:
                                subscriptions.remove(event_type)
                                self._notifiers[event_type].subscribers.discard(
                                    websocket
                                )
                        response = WebsocketUnsubscribeResponse(
                            unsubscribed_event_types=list(subscriptions),
                            request_id=msg.request_id,
                        )
                        await websocket.send_text(
                            response.model_dump_json(exclude_none=True)
                        )
                    case WebsocketCommand():
                        # Handle a custom command
                        command_name = msg.command
                        if command_name not in self._commands:
                            logger.error(f"Unknown command '{command_name}'")
                            continue
                        command_handler = self._commands[command_name]
                        try:
                            command_data = command_handler.data_type.model_validate(
                                msg.data
                            )
                        except ValidationError as e:
                            logger.error(
                                f"Invalid data for a {command_name} command: {e}"
                            )
                            continue
                        try:
                            await command_handler.handler(command_data)
                        except Exception as e:
                            logger.exception(
                                f"Error handling command '{command_name}': {e}"
                            )
                            continue
                    case WebsocketPing():
                        # Respond to keepalive ping with pong
                        logger.debug("Received ping, responding with pong")
                        pong = WebsocketPong(timestamp=msg.timestamp)
                        await websocket.send_text(
                            pong.model_dump_json(exclude_none=True)
                        )
        finally:
            logger.info(f"WebSocket client 0x{id(websocket):x} disconnected")
            self._clients.discard(websocket)
            for event_type in subscriptions:
                self._notifiers[event_type].subscribers.discard(websocket)


WEBSOCKET_MANAGER = WebsocketManager(UISettings())
CONTROLLER = None


def register_controller_to_web(controller) -> None:
    global CONTROLLER
    CONTROLLER = controller


# Simple password-based authentication
security = HTTPBasic()
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password"  # TODO: Move to environment variable


class ServerSettings(SettingsModel):
    """Settings for the web server."""

    host: str = "0.0.0.0"
    """Address to bind the web server to"""

    port: int = 8000
    """Port to serve the VAR panel and its API on"""


def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    """Simple password-based authentication."""
    if credentials.username != ADMIN_USERNAME or credentials.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def get_static_directory() -> Path:
    """Get the static directory for serving assets."""
    # For development, serve from workspace static folder
    dev_static = Path(__file__).parent.parent.parent.parent / "frontend/dist"
    if dev_static.exists():
        return dev_static

    # For installed package, serve from package static folder
    package_static = Path(__file__).parent / "static"
    if package_static.exists():
        return package_static

    # If neither exists, raise an error
    raise RuntimeError(
        "Static assets directory not found. "
        "For development, ensure 'bun run build' has been run from the frontend directory. "
        "For installed package, static assets should be embedded."
    )


# Create FastAPI app
app = FastAPI(
    title="FRC Video Referee",
    description="Video analysis and referee assistance for FRC competitions",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up static files. The lookup is deferred until the server actually runs so that
# the module can be imported without a frontend build present.
_static_dir: Path | None = None


def _get_static_dir() -> Path:
    global _static_dir
    if _static_dir is None:
        _static_dir = get_static_directory()
    return _static_dir


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main application page."""
    index_file = _get_static_dir() / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


@app.get("/api/status")
async def get_status(current_user: str = Depends(get_current_user)):
    """Get application status (requires authentication)."""
    return {"status": "running", "user": current_user}


@app.post("/api/reload_clients")
async def reload_clients():
    """Request all clients to reload their pages"""
    await WEBSOCKET_MANAGER.reload_clients()
    return {"status": "reload requested"}


@app.post("/api/add_review")
async def add_review():
    """Simulate a press of the VAR add review button"""
    assert CONTROLLER is not None
    await CONTROLLER.external_add_var_review()
    return {"status": "Review added"}


@app.websocket("/api/websocket")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await WEBSOCKET_MANAGER.serve_client(websocket)


async def run(settings: ServerSettings) -> None:
    """Run the FastAPI server."""
    static_dir = _get_static_dir()
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    config = uvicorn.Config(
        "frc_video_referee.web:app",
        host=settings.host,
        port=settings.port,
    )
    server = uvicorn.Server(config)
    await server.serve()
