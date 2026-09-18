import type { MatchTiming } from './model';

export function formatMatchTime(time: number, timing: MatchTiming): string {
    // Negative times are footage recorded before the match started
    if (time <= 0) {
        return 'Pre-Match';
    }

    let phaseName = '';
    let phaseStart = 0;
    let phaseDuration = 0;

    const autoStart = timing.warmup_duration_sec;
    const pauseStart = autoStart + timing.auto_duration_sec;
    const teleopStart = pauseStart + timing.pause_duration_sec;
    const endTime = teleopStart + timing.teleop_duration_sec;

    if (time < autoStart) {
        phaseName = 'Warmup';
        phaseStart = 0;
        phaseDuration = timing.warmup_duration_sec;
    } else if (time < pauseStart) {
        phaseName = 'Auto';
        phaseStart = autoStart;
        phaseDuration = timing.auto_duration_sec;
    } else if (time < teleopStart) {
        phaseName = 'Pause';
        phaseStart = pauseStart;
        phaseDuration = timing.pause_duration_sec;
    } else if (time < endTime) {
        phaseName = 'Teleop';
        phaseStart = teleopStart;
        phaseDuration = timing.teleop_duration_sec;
    } else {
        return 'Match Over';
    }

    const remainingTime = phaseStart + phaseDuration - time;
    const remainingSec = Math.floor(remainingTime % 60);
    const remainingMin = Math.floor(remainingTime / 60);

    return `${phaseName} ${remainingMin}:${remainingSec.toString().padStart(2, '0')}`;
}