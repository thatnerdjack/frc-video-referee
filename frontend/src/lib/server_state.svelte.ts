import { DEFAULT_MATCH_TIMING, DEFAULT_UI_SETTINGS, HyperdeckTransportMode, MatchState, MatchStatus, MatchType, PLACEHOLDER_REALTIME_SCORE, type ControllerStatus, type HyperdeckStatus, type Match, type MatchTime, type MatchTiming, type RealtimeScore, type UISettings, type VARMatchTable } from './model';

export interface ServerState {
    ui_settings: UISettings;
    arena_connected: boolean;
    hyperdeck_connected: boolean;
    controller_status: ControllerStatus;

    matches: VARMatchTable;
    realtime_match: Match;
    realtime_score: RealtimeScore;
    match_timing: MatchTiming;
    match_time: MatchTime;
    hyperdeck_status: HyperdeckStatus;
}

/** All state reported by the server to websocket clients */
export const server_state: ServerState = $state({
    ui_settings: DEFAULT_UI_SETTINGS,
    arena_connected: false,
    hyperdeck_connected: false,
    controller_status: {
        selected_match_id: null,
        recording: false,
        realtime_data: true,
    },

    matches: {},
    realtime_match: {
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
    },
    realtime_score: PLACEHOLDER_REALTIME_SCORE,
    match_timing: DEFAULT_MATCH_TIMING,
    match_time: {
        match_state: MatchState.PRE_MATCH,
        match_time_sec: 0,
    },
    hyperdeck_status: {
        transport_mode: HyperdeckTransportMode.InputPreview,
        playing: false,
        clip_time: 0,
        remaining_record_time: 0,
        total_space: 1,
        remaining_space: 0,
    },
})