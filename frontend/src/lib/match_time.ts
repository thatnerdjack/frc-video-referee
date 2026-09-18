/** Match phase and shift arithmetic for the 2026 match structure. */

import { Shift, type MatchTiming } from './model';
import { shiftName } from './game';

/** A named window of match time, in seconds from the start of the match */
export interface TimeWindow {
    start: number;
    end: number;
}

/** Total duration of the teleoperated period */
export function teleopDuration(timing: MatchTiming): number {
    return (
        timing.transition_shift_duration_sec +
        4 * timing.shift_duration_sec +
        timing.endgame_duration_sec
    );
}

/** Match time at which the teleoperated period begins */
export function teleopStart(timing: MatchTiming): number {
    return timing.auto_duration_sec + timing.pause_duration_sec;
}

/** Match time at which the match ends */
export function matchDuration(timing: MatchTiming): number {
    return teleopStart(timing) + teleopDuration(timing);
}

/** The auto, pause and teleop windows of a match */
export function matchPhases(timing: MatchTiming): {
    auto: TimeWindow;
    pause: TimeWindow;
    teleop: TimeWindow;
} {
    const autoEnd = timing.auto_duration_sec;
    const teleopBegin = teleopStart(timing);
    return {
        auto: { start: 0, end: autoEnd },
        pause: { start: autoEnd, end: teleopBegin },
        teleop: { start: teleopBegin, end: matchDuration(timing) },
    };
}

/** Time window for each Fuel scoring shift, in match order */
export function shiftWindows(timing: MatchTiming): (TimeWindow & { shift: Shift })[] {
    const windows: (TimeWindow & { shift: Shift })[] = [
        { shift: Shift.AUTO, start: 0, end: timing.auto_duration_sec },
    ];

    let cursor = teleopStart(timing);
    const durations: [Shift, number][] = [
        [Shift.TRANSITION, timing.transition_shift_duration_sec],
        [Shift.SHIFT_1, timing.shift_duration_sec],
        [Shift.SHIFT_2, timing.shift_duration_sec],
        [Shift.SHIFT_3, timing.shift_duration_sec],
        [Shift.SHIFT_4, timing.shift_duration_sec],
        [Shift.ENDGAME, timing.endgame_duration_sec],
    ];
    for (const [shift, duration] of durations) {
        windows.push({ shift, start: cursor, end: cursor + duration });
        cursor += duration;
    }
    return windows;
}

/** The Fuel scoring shift in progress at a given match time, if any */
export function shiftAtTime(time: number, timing: MatchTiming): Shift | null {
    for (const window of shiftWindows(timing)) {
        if (time >= window.start && time < window.end) {
            return window.shift;
        }
    }
    return time >= matchDuration(timing) ? Shift.POST_MATCH : null;
}

export interface MatchTimeInfo {
    /** Name of the phase in progress, e.g. "Auto" or "Teleop" */
    phase: string;
    /** Shift in progress, if the time falls within one */
    shift: Shift | null;
    /** Seconds remaining in the phase */
    remaining: number;
    /** Remaining time in the phase, formatted as m:ss */
    clock: string;
}

function formatClock(seconds: number): string {
    const clamped = Math.max(0, seconds);
    const mins = Math.floor(clamped / 60);
    const secs = Math.floor(clamped % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/** Break a match time down into the phase and shift it belongs to */
export function matchTimeInfo(time: number, timing: MatchTiming): MatchTimeInfo {
    const phases = matchPhases(timing);

    let phase: string;
    let phaseEnd: number;
    if (time <= 0) {
        return { phase: 'Pre-Match', shift: null, remaining: 0, clock: '' };
    } else if (time < phases.auto.end) {
        phase = 'Auto';
        phaseEnd = phases.auto.end;
    } else if (time < phases.pause.end) {
        phase = 'Pause';
        phaseEnd = phases.pause.end;
    } else if (time < phases.teleop.end) {
        phase = 'Teleop';
        phaseEnd = phases.teleop.end;
    } else {
        return { phase: 'Match Over', shift: Shift.POST_MATCH, remaining: 0, clock: '' };
    }

    const remaining = phaseEnd - time;
    return {
        phase,
        shift: shiftAtTime(time, timing),
        remaining,
        clock: formatClock(remaining),
    };
}

/** Match time as a short label, e.g. "Teleop 1:05" */
export function formatMatchTime(time: number, timing: MatchTiming): string {
    const info = matchTimeInfo(time, timing);
    return info.clock ? `${info.phase} ${info.clock}` : info.phase;
}

/** Match time including the shift in progress, e.g. "Teleop 1:05 · Shift 2" */
export function formatMatchTimeWithShift(time: number, timing: MatchTiming): string {
    const info = matchTimeInfo(time, timing);
    const base = info.clock ? `${info.phase} ${info.clock}` : info.phase;
    if (info.shift === null || info.phase !== 'Teleop') {
        return base;
    }
    return `${base} · ${shiftName(info.shift)}`;
}
