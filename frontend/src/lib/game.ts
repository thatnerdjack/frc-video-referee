/**
 * Helpers for the 2026 game: Fuel scored into the Hub across shifts, and robots
 * climbing the Tower during auto and endgame.
 */

import {
    Shift,
    TELEOP_SHIFTS,
    TowerStatus,
    type BonusRankingPointSettings,
    type Hub,
    type MatchRankingPointSettings,
    type ScoreSummary,
    type UISettings,
} from './model';

/** Whether an alliance's Hub scores points during the given shift */
export function isShiftActive(hub: Hub, shift: Shift): boolean {
    switch (shift) {
        case Shift.AUTO:
        case Shift.TRANSITION:
        case Shift.ENDGAME:
        case Shift.POST_MATCH:
            return true;
        case Shift.SHIFT_1:
        case Shift.SHIFT_3:
            return !hub.won_auto;
        case Shift.SHIFT_2:
        case Shift.SHIFT_4:
            return hub.won_auto;
        default:
            return false;
    }
}

/** Fuel scored during a shift. Inactive shifts count as zero unless `activeOnly` is false */
export function shiftFuel(hub: Hub, shift: Shift, activeOnly: boolean = true): number {
    if (activeOnly && !isShiftActive(hub, shift)) {
        return 0;
    }
    return hub.shift_counts[shift] ?? 0;
}

/** Fuel scored during the autonomous period */
export function autoFuel(hub: Hub): number {
    return shiftFuel(hub, Shift.AUTO);
}

/** Fuel scored during teleop while the Hub was active, excluding the post-match grace period */
export function teleopFuel(hub: Hub): number {
    return TELEOP_SHIFTS.reduce((total, shift) => total + shiftFuel(hub, shift), 0);
}

/** Fuel scored during the grace period after the match */
export function postMatchFuel(hub: Hub): number {
    return shiftFuel(hub, Shift.POST_MATCH);
}

/** Total Fuel counted towards the alliance's score */
export function totalFuel(hub: Hub): number {
    return autoFuel(hub) + teleopFuel(hub) + postMatchFuel(hub);
}

/** Short label for a shift, sized for the compact shift strip */
export function shiftLabel(shift: Shift): string {
    switch (shift) {
        case Shift.AUTO:
            return 'A';
        case Shift.TRANSITION:
            return 'T';
        case Shift.SHIFT_1:
            return '1';
        case Shift.SHIFT_2:
            return '2';
        case Shift.SHIFT_3:
            return '3';
        case Shift.SHIFT_4:
            return '4';
        case Shift.ENDGAME:
            return 'E';
        case Shift.POST_MATCH:
            return 'P';
        default:
            return '?';
    }
}

/** Full name for a shift */
export function shiftName(shift: Shift): string {
    switch (shift) {
        case Shift.AUTO:
            return 'Auto';
        case Shift.TRANSITION:
            return 'Transition';
        case Shift.SHIFT_1:
            return 'Shift 1';
        case Shift.SHIFT_2:
            return 'Shift 2';
        case Shift.SHIFT_3:
            return 'Shift 3';
        case Shift.SHIFT_4:
            return 'Shift 4';
        case Shift.ENDGAME:
            return 'Endgame';
        case Shift.POST_MATCH:
            return 'Post-Match';
        default:
            return 'Unknown';
    }
}

/** Label for a robot's climb status on the Tower */
export function towerStatusLabel(status: TowerStatus): string {
    switch (status) {
        case TowerStatus.LEVEL_1:
            return 'Level 1';
        case TowerStatus.LEVEL_2:
            return 'Level 2';
        case TowerStatus.LEVEL_3:
            return 'Level 3';
        case TowerStatus.NONE:
            return 'None';
        default:
            return '';
    }
}

/** Points scored on the Tower across both auto and endgame */
export function towerPoints(summary: ScoreSummary): number {
    return summary.auto_tower_points + summary.teleop_tower_points;
}

/** One bonus ranking point, resolved against the event's configuration */
export interface RankingPointStatus {
    key: string;
    label: string;
    /** Progress towards the threshold */
    current: number;
    /** Configured threshold for earning the RP */
    goal: number;
    /** Whether the arena says the alliance earned the RP */
    achieved: boolean;
    /** Ranking points this bonus is worth at this event */
    value: number;
}

function bonusStatus(
    key: string,
    settings: BonusRankingPointSettings,
    current: number,
    achieved: boolean,
): RankingPointStatus {
    return {
        key,
        label: settings.label || key,
        current,
        goal: settings.threshold,
        achieved,
        value: settings.value,
    };
}

/**
 * Build the list of bonus ranking points to display.
 *
 * Whether an RP was earned always comes from the arena, which is authoritative.
 * The thresholds come from the panel's configuration, so a mismatch between the two
 * is visible rather than hidden.
 */
export function bonusRankingPoints(
    summary: ScoreSummary,
    settings: UISettings,
): RankingPointStatus[] {
    const rows: RankingPointStatus[] = [];
    if (settings.energized_rp.enabled) {
        rows.push(
            bonusStatus(
                'energized',
                settings.energized_rp,
                summary.num_fuel,
                summary.energized_bonus_ranking_point,
            ),
        );
    }
    if (settings.supercharged_rp.enabled) {
        rows.push(
            bonusStatus(
                'supercharged',
                settings.supercharged_rp,
                summary.num_fuel,
                summary.supercharged_bonus_ranking_point,
            ),
        );
    }
    if (settings.traversal_rp.enabled) {
        rows.push(
            bonusStatus(
                'traversal',
                settings.traversal_rp,
                towerPoints(summary),
                summary.traversal_bonus_ranking_point,
            ),
        );
    }
    return rows;
}

export type MatchOutcome = 'win' | 'loss' | 'tie';

/** Outcome of the match for the alliance whose summary is given first */
export function matchOutcome(
    summary: ScoreSummary,
    opponentSummary: ScoreSummary,
): MatchOutcome {
    if (summary.playoff_dq !== opponentSummary.playoff_dq) {
        return summary.playoff_dq ? 'loss' : 'win';
    }
    if (summary.score > opponentSummary.score) {
        return 'win';
    }
    if (summary.score < opponentSummary.score) {
        return 'loss';
    }
    return 'tie';
}

/** Ranking points awarded for a match outcome under this event's configuration */
export function outcomeRankingPoints(
    outcome: MatchOutcome,
    settings: MatchRankingPointSettings,
): number {
    switch (outcome) {
        case 'win':
            return settings.win;
        case 'tie':
            return settings.tie;
        default:
            return settings.loss;
    }
}

/**
 * Total ranking points an alliance would earn if the match ended now, using this
 * event's configured RP values rather than the arena's built-in ones.
 */
export function projectedRankingPoints(
    summary: ScoreSummary,
    opponentSummary: ScoreSummary,
    settings: UISettings,
): { outcome: MatchOutcome; outcomePoints: number; bonusPoints: number; total: number } {
    const outcome = matchOutcome(summary, opponentSummary);
    const outcomePoints = outcomeRankingPoints(outcome, settings.match_rp);
    const bonusPoints = bonusRankingPoints(summary, settings)
        .filter((rp) => rp.achieved)
        .reduce((total, rp) => total + rp.value, 0);
    return {
        outcome,
        outcomePoints,
        bonusPoints,
        total: outcomePoints + bonusPoints,
    };
}
