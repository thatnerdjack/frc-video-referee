import asyncio
import enum
from types import NoneType
from typing import Awaitable, Callable, Dict, Generic, List, NamedTuple, TypeVar
import httpx
import websockets
import logging
from pydantic import BaseModel, ValidationError

from frc_video_referee.db import DB
from frc_video_referee.db.model import ArenaClientState

from .model import (
    DEFAULT_MATCH_TIMING_MESSAGE,
    PLACEHOLDER_ARENA_STATUS_MESSAGE,
    MatchLoadMessage,
    MatchResultList,
    MatchState,
    MatchTimeMessage,
    MatchTimingMessage,
    MatchWithResultAndSummary,
    RealtimeScoreMessage,
    ScoringStatusMessage,
    ArenaStatusMessage,
    WebsocketMessage,
    PLACEHOLDER_REALTIME_SCORE_MESSAGE,
    PLACEHOLDER_MATCH_LOAD_MESSAGE,
    PLACEHOLDER_MATCH_TIME_MESSAGE,
)
from ..utils import ExitServer

logger = logging.getLogger(__name__)


T = TypeVar("T")


class ArenaClientSettings(BaseModel, use_attribute_docstrings=True):
    """Settings for the Cheesy Arena client."""

    address: str = "10.0.100.5:8080"
    """Cheesy Arena server address"""
    password: str | None = None
    """Password for arena APIs requiring authentication"""
    has_var_enhancements: bool = False
    """Whether Cheesy Arena has advanced VAR features enabled"""


class UnexpectedStatusCode(Exception):
    """Exception to signal that an unexpected HTTP status code was received."""

    def __init__(self, status_code: int):
        super().__init__(f"Unexpected status code: {status_code}")
        self.status_code = status_code


class ArenaNotifier(enum.Enum):
    """Notifiers that can be subscribed by the rest of the system"""

    # Match lifecycle notifications to drive the video capture state machine
    ARENA_READY_TO_START = enum.auto()
    """Notification that the arena is ready to start the match"""
    ARENA_NOT_READY_TO_START = enum.auto()
    """Notification that the arena is no longer ready to start the match"""
    MATCH_STARTED = enum.auto()
    """Notification that a match has started"""
    AUTO_PERIOD_ENDED = enum.auto()
    """Notification that the auto period has ended"""
    TELEOP_PERIOD_STARTED = enum.auto()
    """Notification that the teleop period has started"""
    MATCH_ENDED = enum.auto()
    """Notification that the match has ended"""
    MATCH_COMMITTED_OR_DISCARDED = enum.auto()
    """Notification that the match's results have been committed or discarded"""

    # Property update notifications
    CONNECTION_STATE_UPDATED = enum.auto()
    """Notification that the connection state to the arena has changed"""
    HISTORICAL_SCORES_UPDATED = enum.auto()
    """Notification that the match scores have been updated"""
    REALTIME_SCORE_UPDATED = enum.auto()
    """Notification that the realtime scoring data has been updated"""
    MATCH_TIMING_UPDATED = enum.auto()
    """Notification that the match timing data has been updated"""
    MATCH_TIME_UPDATED = enum.auto()
    """Notification that the match time and state has been updated"""
    MATCH_DATA_UPDATED = enum.auto()
    """Notification that the data for the loaded match has been updated"""


MATCH_TYPES = ["test", "practice", "qualification", "playoff"]


class ArenaMessageHandler(NamedTuple, Generic[T]):
    """Handler for a specific type of arena message."""

    data_type: type[T]
    handler: Callable[[T], Awaitable[None]] | None


class CheesyArenaClient:
    """Client for interacting with Cheesy Arena."""

    def __init__(self, settings: ArenaClientSettings, db: DB):
        self._settings = settings
        """User-specified settings for the Cheesy Arena client"""
        self._db = db
        """Database instance for storing arena state"""
        self._persistent_state = (
            self._db.load_arena_client_state() or ArenaClientState()
        )
        self._connected = False
        """Whether or not the client is currently connected to Cheesy Arena"""

        # Current arena state, accessible to subscribers
        self.match_results: Dict[int, MatchWithResultAndSummary] = {}
        """Results for all matches, keyed by match type"""
        self.realtime_score = PLACEHOLDER_REALTIME_SCORE_MESSAGE
        """Current realtime scoring data"""
        self.match_data = PLACEHOLDER_MATCH_LOAD_MESSAGE
        """Data about the currently loaded match"""
        self.match_timing = DEFAULT_MATCH_TIMING_MESSAGE
        """Current match timing data"""
        self.match_time = PLACEHOLDER_MATCH_TIME_MESSAGE
        """Current match time and state"""
        self.arena_status = PLACEHOLDER_ARENA_STATUS_MESSAGE
        """Current arena status"""

        self._arena_message_handlers: Dict[str, ArenaMessageHandler] = {
            "matchLoad": ArenaMessageHandler(
                data_type=MatchLoadMessage,
                handler=self._handle_match_load,
            ),
            "matchTiming": ArenaMessageHandler(
                data_type=MatchTimingMessage,
                handler=self._handle_match_timing,
            ),
            "matchTime": ArenaMessageHandler(
                data_type=MatchTimeMessage,
                handler=self._handle_match_time,
            ),
            "realtimeScore": ArenaMessageHandler(
                data_type=RealtimeScoreMessage,
                handler=self._handle_realtime_score,
            ),
            "arenaStatus": ArenaMessageHandler(
                data_type=ArenaStatusMessage,
                handler=self._handle_arena_status,
            ),
            "scoringStatus": ArenaMessageHandler(
                data_type=ScoringStatusMessage,
                handler=None,
            ),
            "ping": ArenaMessageHandler(
                data_type=NoneType,
                handler=None,
            ),
        }

        self._subscribers: Dict[ArenaNotifier, List[Callable[[], Awaitable[None]]]] = {
            notifier: [] for notifier in ArenaNotifier
        }
        """Subscribers for various arena state changes"""

    def subscribe(
        self, notifier: ArenaNotifier, callback: Callable[[], Awaitable[None]]
    ):
        """Subscribe to a specific arena state change."""
        self._subscribers[notifier].append(callback)

    @property
    def connected(self) -> bool:
        """Whether or not the client is currently connected to Cheesy Arena."""
        return self._connected

    async def run(self):
        """Main entrypoint for the cheesy arena client."""
        async with httpx.AsyncClient(
            base_url=f"http://{self._settings.address}"
        ) as client:
            logger.info("Starting Cheesy Arena client")
            self._client = client

            if self._persistent_state.session_token:
                client.cookies["session_token"] = self._persistent_state.session_token

            while True:
                try:
                    await self._run_internal(client)
                except ExitServer:
                    raise
                except httpx.RequestError as e:
                    logger.exception(f"HTTP request error: {e}")
                except Exception as e:
                    logger.exception(f"Internal Cheesy Arena client error: {e}")
                logger.info("Reconnecting in 3 seconds...")
                await asyncio.sleep(3)

    async def _run_internal(self, client: httpx.AsyncClient):
        """Run the client, exiting if a disconnect or an error occurs."""

        if await self._check_auth_required(client):
            if not self._settings.password:
                logger.error(
                    "Password authentication is enabled in Cheesy Arena. You must provide the password"
                )
                raise ExitServer
            await self._acquire_session(client)

        if self._persistent_state.session_token:
            additional_headers = {
                "Cookie": f"session_token={self._persistent_state.session_token}"
            }
        else:
            additional_headers = {}

        if self._settings.has_var_enhancements:
            # VAR-specific endpoint in the VAR branch of Cheesy Arena, adds additional
            # arena configuration and readiness reports
            websocket_endpoint = (
                f"ws://{self._settings.address}/video_referee/websocket"
            )
        else:
            # Baseline endpoint available in unmodified Cheesy Arena
            websocket_endpoint = (
                f"ws://{self._settings.address}/panels/referee/websocket"
            )

        async with websockets.connect(
            websocket_endpoint,
            additional_headers=additional_headers,
        ) as websocket:
            logger.info("Cheesy Arena connection established")
            self._connected = True
            await self._notify(ArenaNotifier.CONNECTION_STATE_UPDATED)

            await self._refresh_match_results()

            try:
                while True:
                    message = await websocket.recv(decode=False)
                    await self._handle_cheesy_message(message)
            finally:
                self._connected = False
                # Forget the last known readiness so that a fresh notification is
                # emitted once the arena reports its status again after reconnecting
                self.arena_status = PLACEHOLDER_ARENA_STATUS_MESSAGE
                logger.info("Cheesy Arena connection closed")
                await self._notify(ArenaNotifier.CONNECTION_STATE_UPDATED)

    async def _check_auth_required(self, client: httpx.AsyncClient) -> bool:
        """Check if authentication is required by making a request to a protected endpoint."""
        response = await client.get("/panels/referee")
        if response.status_code == 307:
            return True
        elif response.status_code == 200:
            return False
        else:
            raise UnexpectedStatusCode(response.status_code)

    async def _acquire_session(self, client: httpx.AsyncClient):
        """Acquire a session token by invoking the cheesy arena login endpoint."""
        formdata = {"username": "admin", "password": self._settings.password}
        response = await client.post("/login", data=formdata, follow_redirects=False)
        if response.status_code == 303:
            self._persistent_state.session_token = response.cookies["session_token"]
            client.cookies["session_token"] = self._persistent_state.session_token
            self._db.save_arena_client_state(self._persistent_state)
        elif response.status_code == 200:
            # Incorrect password
            logger.error(
                "Incorrect Cheesy Arena password. Please check your configuration."
            )
            raise ExitServer
        else:
            raise UnexpectedStatusCode(response.status_code)

    async def _refresh_match_results(self):
        """Refresh the local cache of match results."""

        async def fetch_matches_of_type(
            match_type: str,
        ) -> List[MatchWithResultAndSummary]:
            response = await self._client.get(f"/api/matches/{match_type}")
            response.raise_for_status()
            match_data = MatchResultList.validate_json(response.text)
            return match_data

        match_results_by_type = await asyncio.gather(
            *(fetch_matches_of_type(match_type) for match_type in MATCH_TYPES)
        )

        match_results: Dict[int, MatchWithResultAndSummary] = {}
        for matches_for_type in match_results_by_type:
            match_results.update({match.id: match for match in matches_for_type})

        self.match_results = match_results
        await self._notify(ArenaNotifier.HISTORICAL_SCORES_UPDATED)

    async def _notify(self, notifier: ArenaNotifier):
        """Notify subscribers about a state change."""

        logger.debug(f"Notification: {notifier.name}")
        for callback in self._subscribers[notifier]:
            try:
                await callback()
            except Exception as e:
                logger.exception(f"Error notifying subscriber for {notifier.name}: {e}")

    async def _handle_cheesy_message(self, raw_message: bytes):
        """Handle a message received from Cheesy Arena."""
        try:
            message = WebsocketMessage.model_validate_json(raw_message)
        except ValidationError as e:
            logger.exception(f"Malformed message from arena: {e}")
            return

        try:
            handler = self._arena_message_handlers[message.type]
        except KeyError:
            logger.warning(f"Received unknown message type: {message.type}")
            return

        if handler.handler is None:
            # No handler for this message type, skip
            return

        if handler.data_type is NoneType:
            if message.data is not None:
                logger.warning(
                    f"Unexpectedly received data for message type {message.type}: {message.data}"
                )
            # No data body expected, just call the handler
            await handler.handler(None)
        else:
            try:
                message_data = handler.data_type.model_validate(message.data)
            except ValidationError as e:
                logger.exception(f"Malformed {message.type} message from arena: {e}")
                return
            # Call the handler with the validated data
            await handler.handler(message_data)

    async def _handle_match_load(self, message: MatchLoadMessage):
        """Handle a matchLoad message."""
        logger.info(
            f"Match loaded: {message.match_info.short_name} - {message.match_info.long_name} (Replay: {message.is_replay})"
        )
        self.match_data = message
        await self._notify(ArenaNotifier.MATCH_DATA_UPDATED)

    async def _handle_match_timing(self, message: MatchTimingMessage):
        """Handle a matchTiming message."""
        self.match_timing = message
        await self._notify(ArenaNotifier.MATCH_TIMING_UPDATED)

    async def _handle_match_time(self, message: MatchTimeMessage):
        """Handle a matchTime message."""
        prev_match_state = self.match_time.match_state

        self.match_time = message
        await self._notify(ArenaNotifier.MATCH_TIME_UPDATED)

        # Process any match lifecycle transitions
        if prev_match_state != message.match_state:
            match message.match_state:
                case MatchState.AUTO_PERIOD:
                    logger.info("Match started")
                    await self._notify(ArenaNotifier.MATCH_STARTED)
                case MatchState.PAUSE_PERIOD:
                    logger.info("Auto ended")
                    await self._notify(ArenaNotifier.AUTO_PERIOD_ENDED)
                case MatchState.TELEOP_PERIOD:
                    logger.info("Teleop started")
                    await self._notify(ArenaNotifier.TELEOP_PERIOD_STARTED)
                case MatchState.POST_MATCH:
                    logger.info("Match ended")
                    await self._notify(ArenaNotifier.MATCH_ENDED)
                case MatchState.PRE_MATCH:
                    if prev_match_state == MatchState.POST_MATCH:
                        logger.info("Scores committed")
                        # Scorekeeper has committed or discarded the match
                        # Refresh the local match result cache before notifying that the match is committed
                        await self._refresh_match_results()
                        await self._notify(ArenaNotifier.MATCH_COMMITTED_OR_DISCARDED)

    async def _handle_realtime_score(self, message: RealtimeScoreMessage):
        """Handle a realtimeScore message."""
        self.realtime_score = message
        await self._notify(ArenaNotifier.REALTIME_SCORE_UPDATED)

    async def _handle_arena_status(self, message: ArenaStatusMessage):
        """Handle an arenaStatus message."""
        prev_arena_status = self.arena_status
        self.arena_status = message

        if self.arena_status.can_start_match != prev_arena_status.can_start_match:
            if self.arena_status.can_start_match:
                logger.info("Ready to start match")
                await self._notify(ArenaNotifier.ARENA_READY_TO_START)
            else:
                logger.info("No longer ready to start match")
                await self._notify(ArenaNotifier.ARENA_NOT_READY_TO_START)
