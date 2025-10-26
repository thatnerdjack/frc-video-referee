/* Global settings for the frontend panels */

export interface UISettings {
    swap_red_blue: boolean;
    reef_level_rp_threshold: number;
    barge_rp_threshold: number;
}
export const DEFAULT_UI_SETTINGS: UISettings = {
    swap_red_blue: false,
    reef_level_rp_threshold: 5,
    barge_rp_threshold: 14,
}

/* Game-specific score model */

export type ReefRow = [boolean, boolean, boolean, boolean, boolean, boolean, boolean, boolean, boolean, boolean, boolean, boolean];
export type ReefBranches = [ReefRow, ReefRow, ReefRow]

export interface Reef {
    auto_branches: ReefBranches;
    branches: ReefBranches;
    auto_trough_near: number;
    auto_trough_far: number;
    trough_near: number;
    trough_far: number;
}

export const PLACEHOLDER_REEF: Reef = {
    auto_branches: [
        [false, false, false, false, false, false, false, false, false, false, false, false],
        [false, false, false, false, false, false, false, false, false, false, false, false],
        [false, false, false, false, false, false, false, false, false, false, false, false],
    ],
    branches: [
        [false, false, false, false, false, false, false, false, false, false, false, false],
        [false, false, false, false, false, false, false, false, false, false, false, false],
        [false, false, false, false, false, false, false, false, false, false, false, false],
    ],
    auto_trough_near: 0,
    auto_trough_far: 0,
    trough_near: 0,
    trough_far: 0,
}

export interface Foul {
    is_major: boolean;
    team_id: number;
    rule_id: number;
}

export enum EndgameStatus {
    NONE = 0,
    PARKED = 1,
    SHALLOW_CAGE = 2,
    DEEP_CAGE = 3,
}

export interface Score {
    leave_statuses: [boolean, boolean, boolean];
    reef: Reef;
    barge_algae: number;
    processor_algae: number;
    endgame_statuses: [EndgameStatus, EndgameStatus, EndgameStatus];
}

export const PLACEHOLDER_SCORE: Score = {
    leave_statuses: [false, false, false],
    reef: PLACEHOLDER_REEF,
    barge_algae: 0,
    processor_algae: 0,
    endgame_statuses: [EndgameStatus.NONE, EndgameStatus.NONE, EndgameStatus.NONE],
}

export interface ScoreSummary {
    score: number
    match_points: number
    barge_points: number
    num_coral_levels: number;
    num_coral_levels_goal: number;
    auto_bonus_ranking_point: boolean;
    coral_bonus_ranking_point: boolean;
    barge_bonus_ranking_point: boolean;
}

export const PLACEHOLDER_SCORE_SUMMARY = {
    score: 0,
    match_points: 0,
    barge_points: 0,
    num_coral_levels: 0,
    num_coral_levels_goal: 0,
    auto_bonus_ranking_point: false,
    coral_bonus_ranking_point: false,
    barge_bonus_ranking_point: false,
}

export interface ScoreWithSummary {
    score: Score;
    score_summary: ScoreSummary;
}

export const PLACEHOLDER_SCORE_WITH_SUMMARY: ScoreWithSummary = {
    score: PLACEHOLDER_SCORE,
    score_summary: PLACEHOLDER_SCORE_SUMMARY,
}

export interface Cards {
    [index: number]: string;
}

export interface RealtimeScore {
    red: ScoreWithSummary;
    blue: ScoreWithSummary;
    red_cards: Cards;
    blue_cards: Cards;
}

export const PLACEHOLDER_REALTIME_SCORE: RealtimeScore = {
    red: PLACEHOLDER_SCORE_WITH_SUMMARY,
    blue: PLACEHOLDER_SCORE_WITH_SUMMARY,
    red_cards: {},
    blue_cards: {},
}

/* Evergreen arena status */

export enum MatchState {
    PRE_MATCH = 0,
    START_MATCH = 1,
    WARMUP_PERIOD = 2,
    AUTO_PERIOD = 3,
    PAUSE_PERIOD = 4,
    TELEOP_PERIOD = 5,
    POST_MATCH = 6,
    TIMEOUT_ACTIVE = 7,
    POST_TIMEOUT = 8,
}

export interface MatchTiming {
    warmup_duration_sec: number;
    auto_duration_sec: number;
    pause_duration_sec: number;
    teleop_duration_sec: number;
    warning_remaining_duration_sec: number;
    timeout_duration_sec: number;
}

export const DEFAULT_MATCH_TIMING: MatchTiming = {
    warmup_duration_sec: 0,
    auto_duration_sec: 15,
    pause_duration_sec: 3,
    teleop_duration_sec: 135,
    warning_remaining_duration_sec: 20,
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
    selected_match_id: number | null;
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