/* Global settings for the frontend panels */

/** Ranking points awarded for the outcome of a match */
export interface MatchRankingPointSettings {
    win: number;
    tie: number;
    loss: number;
}

/** Display and scoring configuration for one bonus ranking point */
export interface BonusRankingPointSettings {
    /** Whether this ranking point is in use at this event */
    enabled: boolean;
    /** Name shown for this ranking point in the panel */
    label: string;
    /** Value which must be reached to earn this ranking point */
    threshold: number;
    /** Ranking points awarded for earning this bonus */
    value: number;
}

export interface UISettings {
    swap_red_blue: boolean;
    match_rp: MatchRankingPointSettings;
    energized_rp: BonusRankingPointSettings;
    supercharged_rp: BonusRankingPointSettings;
    traversal_rp: BonusRankingPointSettings;
}

export const DEFAULT_UI_SETTINGS: UISettings = {
    swap_red_blue: false,
    match_rp: { win: 3, tie: 1, loss: 0 },
    energized_rp: { enabled: true, label: 'Energized', threshold: 100, value: 1 },
    supercharged_rp: { enabled: true, label: 'Supercharged', threshold: 360, value: 1 },
    traversal_rp: { enabled: true, label: 'Traversal', threshold: 50, value: 1 },
}

/* Game-specific score model */

/** A distinct period during the match when Fuel is scored and tracked separately */
export enum Shift {
    AUTO = 0,
    TRANSITION = 1,
    SHIFT_1 = 2,
    SHIFT_2 = 3,
    SHIFT_3 = 4,
    SHIFT_4 = 5,
    ENDGAME = 6,
    POST_MATCH = 7,
}

/** Number of distinct Fuel scoring shifts in a match */
export const SHIFT_COUNT = 8;

/** Shifts which make up the teleoperated period, in match order */
export const TELEOP_SHIFTS: Shift[] = [
    Shift.TRANSITION,
    Shift.SHIFT_1,
    Shift.SHIFT_2,
    Shift.SHIFT_3,
    Shift.SHIFT_4,
    Shift.ENDGAME,
];

/** Fuel scoring data for an alliance's Hub */
export interface Hub {
    /** Whether this alliance won auto, which decides the shifts where its Hub is active */
    won_auto: boolean;
    /** Fuel scored during each shift, whether or not the Hub was active */
    shift_counts: number[];
}

export const PLACEHOLDER_HUB: Hub = {
    won_auto: false,
    shift_counts: Array(SHIFT_COUNT).fill(0),
}

/** Climb status of a robot on the Tower */
export enum TowerStatus {
    NONE = 0,
    LEVEL_1 = 1,
    LEVEL_2 = 2,
    LEVEL_3 = 3,
}

export type TowerStatuses = [TowerStatus, TowerStatus, TowerStatus];

export interface Foul {
    is_major: boolean;
    team_id: number;
    rule_id: number;
    foul_id?: number | null;
}

export interface Score {
    /** Tower status for each robot at the end of the autonomous period */
    auto_tower_statuses: TowerStatuses;
    /** Fuel scoring data for the alliance's Hub */
    hub: Hub;
    /** Tower status for each robot at the end of the match */
    endgame_tower_statuses: TowerStatuses;
    /** Fouls committed by the alliance */
    fouls?: Foul[] | null;
    /** Whether the alliance was disqualified from a playoff match */
    playoff_dq: boolean;
}

export const PLACEHOLDER_SCORE: Score = {
    auto_tower_statuses: [TowerStatus.NONE, TowerStatus.NONE, TowerStatus.NONE],
    hub: PLACEHOLDER_HUB,
    endgame_tower_statuses: [TowerStatus.NONE, TowerStatus.NONE, TowerStatus.NONE],
    fouls: null,
    playoff_dq: false,
}

export interface ScoreSummary {
    /** Total score, including fouls awarded by the opponent */
    score: number;
    /** Points scored by the alliance itself, excluding fouls */
    match_points: number;
    /** Points scored from Fuel during the autonomous period */
    auto_fuel_points: number;
    /** Points scored on the Tower during the autonomous period */
    auto_tower_points: number;
    /** Points scored from Fuel during the teleoperated period */
    teleop_fuel_points: number;
    /** Points scored on the Tower at the end of the match */
    teleop_tower_points: number;
    /** Total Fuel scored while the alliance's Hub was active */
    num_fuel: number;
    /** Fuel scored during the grace period after the match */
    num_fuel_post_match: number;
    /** Fuel total needed for the alliance's next Fuel ranking point */
    num_fuel_goal: number;
    /** Points which are only determined once the match has ended */
    post_match_points: number;
    /** Points awarded to this alliance from fouls committed by its opponent */
    foul_points: number;
    /** Number of major fouls committed by the opposing alliance */
    num_opponent_major_fouls: number;
    /** Whether the alliance was disqualified from a playoff match */
    playoff_dq: boolean;
    energized_bonus_ranking_point: boolean;
    supercharged_bonus_ranking_point: boolean;
    traversal_bonus_ranking_point: boolean;
    /** Bonus ranking points earned, as counted by the arena */
    bonus_ranking_points: number;
}

export const PLACEHOLDER_SCORE_SUMMARY: ScoreSummary = {
    score: 0,
    match_points: 0,
    auto_fuel_points: 0,
    auto_tower_points: 0,
    teleop_fuel_points: 0,
    teleop_tower_points: 0,
    num_fuel: 0,
    num_fuel_post_match: 0,
    num_fuel_goal: 0,
    post_match_points: 0,
    foul_points: 0,
    num_opponent_major_fouls: 0,
    playoff_dq: false,
    energized_bonus_ranking_point: false,
    supercharged_bonus_ranking_point: false,
    traversal_bonus_ranking_point: false,
    bonus_ranking_points: 0,
}

export interface ScoreWithSummary {
    score: Score;
    score_summary: ScoreSummary;
    /** Seconds left in the current shift while this alliance's Hub is active, otherwise zero */
    active_remaining_sec: number;
    /** Total duration of the current shift in seconds */
    active_duration_sec: number;
}

export const PLACEHOLDER_SCORE_WITH_SUMMARY: ScoreWithSummary = {
    score: PLACEHOLDER_SCORE,
    score_summary: PLACEHOLDER_SCORE_SUMMARY,
    active_remaining_sec: 0,
    active_duration_sec: 0,
}

export interface Cards {
    [index: number]: string;
}

/* Evergreen arena status */

/** Must stay in sync with the MatchState constants in Cheesy Arena's field package */
export enum MatchState {
    PRE_MATCH = 0,
    START_MATCH = 1,
    AUTO_PERIOD = 2,
    PAUSE_PERIOD = 3,
    TELEOP_PERIOD = 4,
    POST_MATCH = 5,
    TIMEOUT_ACTIVE = 6,
    POST_TIMEOUT = 7,
}

export interface RealtimeScore {
    red: ScoreWithSummary;
    blue: ScoreWithSummary;
    red_cards: Cards;
    blue_cards: Cards;
    match_state: MatchState;
}

export const PLACEHOLDER_REALTIME_SCORE: RealtimeScore = {
    red: PLACEHOLDER_SCORE_WITH_SUMMARY,
    blue: PLACEHOLDER_SCORE_WITH_SUMMARY,
    red_cards: {},
    blue_cards: {},
    match_state: MatchState.PRE_MATCH,
}

export interface MatchTiming {
    auto_duration_sec: number;
    pause_duration_sec: number;
    /** Duration of the transition shift at the start of teleop */
    transition_shift_duration_sec: number;
    /** Duration of each of the four contested shifts */
    shift_duration_sec: number;
    /** Duration of the endgame shift */
    endgame_duration_sec: number;
    timeout_duration_sec: number;
}

export const DEFAULT_MATCH_TIMING: MatchTiming = {
    auto_duration_sec: 20,
    pause_duration_sec: 3,
    transition_shift_duration_sec: 10,
    shift_duration_sec: 25,
    endgame_duration_sec: 30,
    timeout_duration_sec: 0,
}

export interface MatchTime {
    match_state: MatchState;
    match_time_sec: number;
}

export enum MatchType {
    TEST = 0,
    PRACTICE = 1,
    QUALIFICATION = 2,
    PLAYOFF = 3,
}

/** Play status of a match */
export enum MatchStatus {
    /** Match is scheduled but not played yet*/
    SCHEDULED = 0,
    /** Match is hidden from the schedule, e.g. a skipped playoff match */
    HIDDEN = 1,
    /** Match was played and the Red alliance won */
    RED_WON = 2,
    /** Match was played and the Blue alliance won */
    BLUE_WON = 3,
    /** Match was played and ended in a tie */
    TIE = 4,
}

/** Schedule data for a match */
export interface Match {
    /** Internal arena ID for the match */
    id: number;
    /** Type of the match, eg qualification or playoff */
    match_type: MatchType;
    /** Order of the match within its type */
    type_order: number;
    /** Full name for the match */
    long_name: string;
    /** Abbreviated name for the match */
    short_name: string;
    /** Team number in the Red 1 station */
    red1: number;
    /** Team number in the Red 2 station */
    red2: number;
    /** Team number in the Red 3 station */
    red3: number;
    /** Team number in the Blue 1 station */
    blue1: number;
    /** Team number in the Blue 2 station */
    blue2: number;
    /** Team number in the Blue 3 station */
    blue3: number;
    /** Overall status of the match, whether it was played and which alliance won. */
    status: MatchStatus;
}

export const PLACEHOLDER_MATCH: Match = {
    id: 0,
    match_type: MatchType.TEST,
    type_order: 0,
    long_name: '',
    short_name: '',
    red1: 0,
    red2: 0,
    red3: 0,
    blue1: 0,
    blue2: 0,
    blue3: 0,
    status: MatchStatus.SCHEDULED,
}

export interface MatchResult {
    /** Internal arena ID for the match */
    match_id: number;
    /** How many times this match has been played, 1 for the first place, 2 for a replay, etc. */
    play_number: number;
    /** Type of the match */
    match_type: MatchType;
    /** Score data for the red alliance */
    red_score: Score;
    /** Score data for the blue alliance */
    blue_score: Score;
    /** Red alliance cards issued during the match */
    red_cards: Cards;
    /** Blue alliance cards issued during the match */
    blue_cards: Cards;
}

export interface MatchResultWithSummary extends MatchResult {
    /** Summary of the red match score */
    red_summary: ScoreSummary;
    /** Summary of the blue match score */
    blue_summary: ScoreSummary;
}

export interface MatchWithResultAndSummary extends Match {
    /** Results of the match, including final scores */
    result?: MatchResultWithSummary;
}

/* Hyperdeck status types */
export enum HyperdeckTransportMode {
    InputPreview = "InputPreview",
    InputRecord = "InputRecord",
    Output = "Output",
}

export enum MatchEventType {
    AUTO_SCORING = "auto_scoring",
    ENDGAME_SCORING = "endgame_scoring",
    VAR_REVIEW = "var_review",
    HR_REVIEW = "hr_review",
    ROBOT_DISCONNECT = "robot_disconnect",
    MINOR_FOUL = "minor_foul",
    MAJOR_FOUL = "major_foul",
}

export enum Alliance {
    RED = "red",
    BLUE = "blue",
}

export interface EventCoordinates {
    x: number;
    y: number;
}

export interface MatchEvent {
    event_id: string;
    event_type: MatchEventType;
    time: number;
    alliance?: Alliance;
    team_idx?: number; // 0, 1, or 2 for the position on the alliance
    reason?: string;
    coordinates?: EventCoordinates;
    arena_foul_id?: number;
}

export interface TeamTable {
    [index: string]: [number, number, number]; // team numbers for the alliance
}

export const PLACEHOLDER_TEAMS: TeamTable = {
    [Alliance.RED]: [0, 0, 0],
    [Alliance.BLUE]: [0, 0, 0],
}

export interface RecordedMatch {
    var_id: string;
    arena_id: number;
    clip_id?: number;
    clip_file_name: string;
    match_start_timestamp: string;
    recording_start_timestamp: string;
    teams: TeamTable;
    events: MatchEvent[];
}

export interface VARMatch {
    var_data: RecordedMatch;
    arena_data: MatchWithResultAndSummary | null;
    clip_available: boolean;
}

export interface VARMatchTable {
    [index: string]: VARMatch;
}

export interface ControllerStatus {
    selected_match_id: string | null;
    recording: boolean;
    realtime_data: boolean;
}

export interface HyperdeckStatus {
    transport_mode: HyperdeckTransportMode;
    playing: boolean;
    clip_time: number;
    remaining_record_time: number;
    total_space: number;
    remaining_space: number;
}

export enum WebsocketEventType {
    UISettings = "ui_settings",
    ControllerStatus = "controller_status",
    CurrentMatchData = "current_match_data",
    CurrentMatchTime = "current_match_time",
    MatchTiming = "match_timing",
    RealtimeScore = "realtime_score",
    MatchList = "match_list",
    ArenaConnection = "arena_connection",
    HyperdeckConnection = "hyperdeck_connection",
    HyperdeckStatus = "hyperdeck_status",
}

export interface WebsocketEvent {
    type: 'event';
    event_type: string;
    data: any;
}

export interface WebsocketSubscribeResponse {
    type: 'subscribe';
    initial_data: Partial<Record<string, any>>;
}
