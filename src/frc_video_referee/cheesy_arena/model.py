"""
This module defines the data types for the Cheesy Arena APIs used in this application.

The game-specific portions of this module track the 2026 FRC game, where alliances
score Fuel into the Hub and climb the Tower.
"""

from enum import IntEnum
from pydantic import BaseModel, Field, TypeAdapter
from typing import Annotated, Any, List, Dict

###################################
# Baseline Data Types
###################################


class BaseArenaModel(BaseModel, validate_by_name=True):
    """Base model for all arena data.

    Unknown fields are ignored so that a Cheesy Arena release which adds new data
    does not break the VAR server, and every field carries a default so that a
    message which omits data still validates.
    """

    pass


class MatchType(IntEnum):
    """Types of matches in the arena"""

    TEST = 0
    PRACTICE = 1
    QUALIFICATION = 2
    PLAYOFF = 3


class MatchStatus(IntEnum):
    """Play status of a match"""

    SCHEDULED = 0
    """Match is scheduled but not played yet"""
    HIDDEN = 1
    """Match is hidden from the schedule, e.g. a skipped playoff match"""
    RED_WON = 2
    """Match was played and the Red alliance won"""
    BLUE_WON = 3
    """Match was played and the Blue alliance won"""
    TIE = 4
    """Match was played and ended in a tie"""


class Match(BaseArenaModel):
    """Schedule data for a match"""

    id: Annotated[int, Field(alias="Id")] = 0
    """Internal arena ID for the match"""
    match_type: Annotated[MatchType, Field(alias="Type")] = MatchType.TEST
    """Type of the match, e.g., qualification, playoff, etc."""
    type_order: Annotated[int, Field(alias="TypeOrder")] = 0
    """Order of the match within its type"""
    long_name: Annotated[str, Field(alias="LongName")] = ""
    """Full name of the match, e.g., "Qualification Match 1"."""
    short_name: Annotated[str, Field(alias="ShortName")] = ""
    """Abbreviated name of the match, e.g., "Q1"."""

    red1: Annotated[int, Field(alias="Red1")] = 0
    """Team number in the Red 1 station"""
    red2: Annotated[int, Field(alias="Red2")] = 0
    """Team number in the Red 2 station"""
    red3: Annotated[int, Field(alias="Red3")] = 0
    """Team number in the Red 3 station"""
    blue1: Annotated[int, Field(alias="Blue1")] = 0
    """Team number in the Blue 1 station"""
    blue2: Annotated[int, Field(alias="Blue2")] = 0
    """Team number in the Blue 2 station"""
    blue3: Annotated[int, Field(alias="Blue3")] = 0
    """Team number in the Blue 3 station"""

    status: Annotated[MatchStatus, Field(alias="Status")] = MatchStatus.SCHEDULED
    """Overall status of the match, whether it was played and which alliance won."""


class Team(BaseArenaModel):
    """Represents a team in the event."""

    team_num: Annotated[int, Field(alias="Id")] = 0
    """Team number"""


class MatchState(IntEnum):
    """State of a match play cycle.

    These values must stay in sync with the MatchState constants in Cheesy Arena's
    field package.
    """

    PRE_MATCH = 0
    """Match is loaded but not started yet"""
    START_MATCH = 1
    """Start match has been pressed, arena is transitioning to the match play state"""
    AUTO_PERIOD = 2
    """Autonomous period is in progress"""
    PAUSE_PERIOD = 3
    """Period between autonomous and teleop is in progress"""
    TELEOP_PERIOD = 4
    """Teleoperated period is in progress"""
    POST_MATCH = 5
    """Match is ended"""
    TIMEOUT_ACTIVE = 6
    """A timeout is in progress"""
    POST_TIMEOUT = 7
    """A timeout has completed but the next match has not been loaded yet"""


####################################
# Game-specific scoring data types
####################################


class Shift(IntEnum):
    """A distinct period during the match when Fuel is scored and tracked separately"""

    AUTO = 0
    """The autonomous period"""
    TRANSITION = 1
    """The first shift of teleop, active for both alliances"""
    SHIFT_1 = 2
    """First contested shift, active for the alliance that lost AUTO"""
    SHIFT_2 = 3
    """Second contested shift, active for the alliance that won AUTO"""
    SHIFT_3 = 4
    """Third contested shift, active for the alliance that lost AUTO"""
    SHIFT_4 = 5
    """Fourth contested shift, active for the alliance that won AUTO"""
    ENDGAME = 6
    """The endgame shift, active for both alliances"""
    POST_MATCH = 7
    """The scoring grace period after the match, active for both alliances"""


SHIFT_COUNT = len(Shift)
"""Number of distinct Fuel scoring shifts in a match"""

TELEOP_SHIFTS = [
    Shift.TRANSITION,
    Shift.SHIFT_1,
    Shift.SHIFT_2,
    Shift.SHIFT_3,
    Shift.SHIFT_4,
    Shift.ENDGAME,
    Shift.POST_MATCH,
]
"""Shifts which count towards the teleoperated Fuel total, in match order"""

ShiftCounts = Annotated[
    List[int], Field(min_length=SHIFT_COUNT, max_length=SHIFT_COUNT)
]
"""Fuel counts for each shift of a match"""


class Hub(BaseArenaModel):
    """Fuel scoring data for an alliance's Hub"""

    won_auto: Annotated[bool, Field(alias="WonAuto")] = False
    """Whether this alliance won the autonomous period, which decides the shifts where its Hub is active"""
    shift_counts: Annotated[ShiftCounts, Field(alias="ShiftCounts")] = [0] * SHIFT_COUNT
    """Number of Fuel scored during each shift, whether or not the Hub was active"""

    def is_shift_active(self, shift: Shift) -> bool:
        """Whether this alliance's Hub scores points during the given shift"""
        match shift:
            case Shift.AUTO | Shift.TRANSITION | Shift.ENDGAME | Shift.POST_MATCH:
                return True
            case Shift.SHIFT_1 | Shift.SHIFT_3:
                return not self.won_auto
            case Shift.SHIFT_2 | Shift.SHIFT_4:
                return self.won_auto
            case _:
                return False

    def shift_count(self, shift: Shift, active_only: bool = True) -> int:
        """Fuel scored during a shift, or zero if the Hub was inactive for it"""
        if active_only and not self.is_shift_active(shift):
            return 0
        try:
            return self.shift_counts[shift]
        except IndexError:
            return 0


PLACEHOLDER_HUB = Hub()


class TowerStatus(IntEnum):
    """Climb status of a robot on the Tower"""

    NONE = 0
    """Not on the tower"""
    LEVEL_1 = 1
    """Climbed to the first level of the tower"""
    LEVEL_2 = 2
    """Climbed to the second level of the tower"""
    LEVEL_3 = 3
    """Climbed to the third level of the tower"""


TowerStatuses = Annotated[List[TowerStatus], Field(min_length=3, max_length=3)]
"""Tower climb status for each robot on an alliance"""


class Foul(BaseArenaModel):
    is_major: Annotated[bool, Field(alias="IsMajor")] = False
    """Whether this is a major or minor foul"""
    team_id: Annotated[int, Field(alias="TeamId")] = 0
    """The team that committed the foul"""
    rule_id: Annotated[int, Field(alias="RuleId")] = 0
    """The rule that was violated"""
    foul_id: Annotated[int | None, Field(alias="FoulId")] = None
    """A unique identifier for the occurrence of a foul"""


class Score(BaseArenaModel):
    """Represents an alliance's score components in a match."""

    auto_tower_statuses: Annotated[TowerStatuses, Field(alias="AutoTowerStatuses")] = [
        TowerStatus.NONE
    ] * 3
    """Tower status for each robot at the end of the autonomous period"""
    hub: Annotated[Hub, Field(alias="Hub")] = PLACEHOLDER_HUB
    """Fuel scoring data for the alliance's Hub"""
    endgame_tower_statuses: Annotated[
        TowerStatuses, Field(alias="EndgameTowerStatuses")
    ] = [TowerStatus.NONE] * 3
    """Tower status for each robot at the end of the match"""
    fouls: Annotated[List[Foul] | None, Field(alias="Fouls")] = None
    """List of fouls committed by the alliance, or None if no fouls were committed"""
    playoff_dq: Annotated[bool, Field(alias="PlayoffDq")] = False
    """Whether the alliance was disqualified from a playoff match"""


PLACEHOLDER_SCORE = Score()


class ScoreSummary(BaseArenaModel):
    """Final score tallies for an alliance in a match."""

    score: Annotated[int, Field(alias="Score")] = 0
    """Total score for the alliance, including all fouls and adjustments"""

    match_points: Annotated[int, Field(alias="MatchPoints")] = 0
    """Total points scored by the alliance in the match, excluding fouls"""

    auto_fuel_points: Annotated[int, Field(alias="AutoFuelPoints")] = 0
    """Points scored from Fuel during the autonomous period"""

    auto_tower_points: Annotated[int, Field(alias="AutoTowerPoints")] = 0
    """Points scored on the Tower during the autonomous period"""

    teleop_fuel_points: Annotated[int, Field(alias="TeleopFuelPoints")] = 0
    """Points scored from Fuel during the teleoperated period"""

    teleop_tower_points: Annotated[int, Field(alias="TeleopTowerPoints")] = 0
    """Points scored on the Tower at the end of the match"""

    num_fuel: Annotated[int, Field(alias="NumFuel")] = 0
    """Total Fuel scored while the alliance's Hub was active"""

    num_fuel_post_match: Annotated[int, Field(alias="NumFuelPostMatch")] = 0
    """Fuel scored during the grace period after the match"""

    num_fuel_goal: Annotated[int, Field(alias="NumFuelGoal")] = 0
    """Fuel total needed for the alliance's next Fuel ranking point"""

    post_match_points: Annotated[int, Field(alias="PostMatchPoints")] = 0
    """Points which are only determined once the match has ended"""

    foul_points: Annotated[int, Field(alias="FoulPoints")] = 0
    """Points awarded to this alliance from fouls committed by its opponent"""

    num_opponent_major_fouls: Annotated[int, Field(alias="NumOpponentMajorFouls")] = 0
    """Number of major fouls committed by the opposing alliance"""

    playoff_dq: Annotated[bool, Field(alias="PlayoffDq")] = False
    """Whether the alliance was disqualified from a playoff match"""

    energized_bonus_ranking_point: Annotated[
        bool, Field(alias="EnergizedBonusRankingPoint")
    ] = False
    """Whether the alliance earned the Energized (first Fuel threshold) ranking point"""

    supercharged_bonus_ranking_point: Annotated[
        bool, Field(alias="SuperchargedBonusRankingPoint")
    ] = False
    """Whether the alliance earned the Supercharged (second Fuel threshold) ranking point"""

    traversal_bonus_ranking_point: Annotated[
        bool, Field(alias="TraversalBonusRankingPoint")
    ] = False
    """Whether the alliance earned the Traversal (Tower points) ranking point"""

    bonus_ranking_points: Annotated[int, Field(alias="BonusRankingPoints")] = 0
    """Number of bonus ranking points earned by the alliance, as counted by the arena"""

    @property
    def tower_points(self) -> int:
        """Total Tower points scored across auto and endgame"""
        return self.auto_tower_points + self.teleop_tower_points


PLACEHOLDER_SCORE_SUMMARY = ScoreSummary()


#############################################
# Match results HTTP endpoint response types
#############################################


class MatchResult(BaseArenaModel):
    """The baseline results of a match which are stored in the arena database."""

    match_id: Annotated[int, Field(alias="MatchId")] = 0
    """Internal arena ID for the match"""
    play_number: Annotated[int, Field(alias="PlayNumber")] = 0
    """How many times this match has been played, 1 for the first play, 2 for a replay, etc."""
    match_type: Annotated[MatchType, Field(alias="MatchType")] = MatchType.TEST
    """Type of the match, e.g., qualification, playoff, etc."""
    red_score: Annotated[Score, Field(alias="RedScore")] = PLACEHOLDER_SCORE
    """Score data for the Red alliance"""
    blue_score: Annotated[Score, Field(alias="BlueScore")] = PLACEHOLDER_SCORE
    """Score data for the Blue alliance"""
    red_cards: Annotated[Dict[int, str], Field(alias="RedCards")] = {}
    """Red alliance cards issued during the match, keyed by team number"""
    blue_cards: Annotated[Dict[int, str], Field(alias="BlueCards")] = {}
    """Blue alliance cards issued during the match, keyed by team number"""


class MatchResultWithSummary(MatchResult):
    """Match results with final scores computed"""

    red_summary: Annotated[ScoreSummary, Field(alias="RedSummary")] = (
        PLACEHOLDER_SCORE_SUMMARY
    )
    """Final score summary for the Red alliance"""
    blue_summary: Annotated[ScoreSummary, Field(alias="BlueSummary")] = (
        PLACEHOLDER_SCORE_SUMMARY
    )
    """Final score summary for the Blue alliance"""


class MatchWithResultAndSummary(Match):
    """Match schedule information with its results"""

    result: Annotated[MatchResultWithSummary | None, Field(alias="Result")] = None
    """Results of the match, including final scores"""


MatchResultList = TypeAdapter(List[MatchWithResultAndSummary])
"""List of match results"""


###########################
# Websocket message types #
###########################


class MatchLoadMessage(BaseArenaModel):
    """Contents of a matchLoad message"""

    match_info: Annotated[Match, Field(alias="Match")] = Match()
    """Information about the match being loaded"""
    is_replay: Annotated[bool, Field(alias="IsReplay")] = False
    """Whether this is a replay of a match"""
    teams: Annotated[Dict[str, Team | None], Field(alias="Teams")] = {}
    """Teams participating in the match, keyed by station ID as a string"""


PLACEHOLDER_MATCH_LOAD_MESSAGE = MatchLoadMessage(
    match_info=Match(long_name="Test Match", short_name="T")
)


class MatchTimingMessage(BaseArenaModel):
    """Contents of a matchTiming message.

    The 2026 teleoperated period is divided into a transition shift, four contested
    shifts of equal length, and an endgame shift.
    """

    auto_duration_sec: Annotated[int, Field(alias="AutoDurationSec")] = 20
    """Duration of the autonomous period in seconds"""
    pause_duration_sec: Annotated[int, Field(alias="PauseDurationSec")] = 3
    """Duration of the pause period between auto and teleop in seconds"""
    transition_shift_duration_sec: Annotated[
        int, Field(alias="TransitionShiftDurationSec")
    ] = 10
    """Duration of the transition shift at the start of teleop in seconds"""
    shift_duration_sec: Annotated[int, Field(alias="ShiftDurationSec")] = 25
    """Duration of each of the four contested shifts in seconds"""
    endgame_duration_sec: Annotated[int, Field(alias="EndgameDurationSec")] = 30
    """Duration of the endgame shift in seconds"""
    timeout_duration_sec: Annotated[int, Field(alias="TimeoutDurationSec")] = 0
    """Duration of the timeout period in seconds"""

    @property
    def teleop_duration_sec(self) -> int:
        """Total duration of the teleoperated period in seconds"""
        return (
            self.transition_shift_duration_sec
            + 4 * self.shift_duration_sec
            + self.endgame_duration_sec
        )

    @property
    def teleop_start_sec(self) -> int:
        """Match time at which the teleoperated period begins"""
        return self.auto_duration_sec + self.pause_duration_sec

    @property
    def match_duration_sec(self) -> int:
        """Match time at which the match ends"""
        return self.teleop_start_sec + self.teleop_duration_sec


DEFAULT_MATCH_TIMING_MESSAGE = MatchTimingMessage()


class MatchTimeMessage(BaseArenaModel):
    """Contents of a matchTime message"""

    match_state: Annotated[MatchState, Field(alias="MatchState")] = MatchState.PRE_MATCH
    """Current state of the match play cycle"""
    match_time_sec: Annotated[int, Field(alias="MatchTimeSec")] = 0
    """Current match time in seconds, 0 for pre- or post-match state"""


PLACEHOLDER_MATCH_TIME_MESSAGE = MatchTimeMessage()


class ScoreWithSummary(BaseArenaModel):
    """Represents an alliance's score with a summary."""

    score: Annotated[Score, Field(alias="Score")] = PLACEHOLDER_SCORE
    """Raw scoring data for the alliance"""
    score_summary: Annotated[ScoreSummary, Field(alias="ScoreSummary")] = (
        PLACEHOLDER_SCORE_SUMMARY
    )
    """Final score summary for the alliance"""
    active_remaining_sec: Annotated[int, Field(alias="ActiveRemainingSec")] = 0
    """Seconds remaining in the current shift if this alliance's Hub is active, otherwise zero"""
    active_duration_sec: Annotated[int, Field(alias="ActiveDurationSec")] = 0
    """Total duration of the current shift in seconds"""


PLACEHOLDER_SCORE_WITH_SUMMARY = ScoreWithSummary()


class RealtimeScoreMessage(BaseArenaModel):
    """Contents of a realtimeScore message"""

    red: Annotated[ScoreWithSummary, Field(alias="Red")] = (
        PLACEHOLDER_SCORE_WITH_SUMMARY
    )
    """Score data for the Red alliance"""
    blue: Annotated[ScoreWithSummary, Field(alias="Blue")] = (
        PLACEHOLDER_SCORE_WITH_SUMMARY
    )
    """Score data for the Blue alliance"""
    red_cards: Annotated[Dict[int, str], Field(alias="RedCards")] = {}
    """Red alliance cards issued during the match, keyed by team number"""
    blue_cards: Annotated[Dict[int, str], Field(alias="BlueCards")] = {}
    """Blue alliance cards issued during the match, keyed by team number"""
    match_state: Annotated[MatchState, Field(alias="MatchState")] = MatchState.PRE_MATCH
    """State of the match play cycle at the time the scores were reported"""


PLACEHOLDER_REALTIME_SCORE_MESSAGE = RealtimeScoreMessage()


class PositionStatus(BaseArenaModel):
    """Status for a referee and scorer position"""

    num_panels: Annotated[int, Field(alias="NumPanels")] = 0
    """How many panels are connected to the arena for this position"""
    num_panels_ready: Annotated[int, Field(alias="NumPanelsReady")] = 0
    """How many panels are signaling scores ready for this position"""
    ready: Annotated[bool, Field(alias="Ready")] = False
    """Whether this position has completed scoring"""


class ScoringStatusMessage(BaseArenaModel):
    """Contents of a scoringStatus message"""

    referee_score_ready: Annotated[bool, Field(alias="RefereeScoreReady")] = False
    """Whether the head referee has completed scoring"""
    position_statuses: Annotated[
        Dict[str, PositionStatus], Field(alias="PositionStatuses")
    ] = {}
    """Status of each scoring position, keyed by position name"""


class ArenaStatusMessage(BaseArenaModel):
    """Contents of an arenaStatus message"""

    can_start_match: Annotated[bool, Field(alias="CanStartMatch")] = False
    """Whether the arena is ready to start a match"""


PLACEHOLDER_ARENA_STATUS_MESSAGE = ArenaStatusMessage()


class WebsocketMessage(BaseArenaModel):
    """Base type for inbound websocket messages."""

    type: str
    data: Any = None
