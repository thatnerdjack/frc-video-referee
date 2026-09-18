<script lang="ts">
    import { getEventTypeColor } from "../lib/events";
    import { matchDuration, matchPhases, shiftWindows } from "../lib/match_time";
    import { shiftName } from "../lib/game";
    import { Shift, type MatchEvent, type MatchTiming } from "../lib/model";

    interface EventWithIdx {
        event_idx: number;
        event: MatchEvent;
    }

    interface Props {
        events: EventWithIdx[];
        warpToEvent?: (event: MatchEvent) => void;
        warpToTime?: (time: number) => void;
        currentTime: number;
        match_timing: MatchTiming;
        /** Extra recording time captured after the match ends */
        scoring_capture_sec?: number;
    }

    let {
        events,
        warpToEvent,
        warpToTime,
        currentTime,
        match_timing,
        scoring_capture_sec = 5,
    }: Props = $props();

    const NUM_TICKS = 10000;

    // All of these must track the match timing reported by the arena, which arrives
    // after the panel first renders and can change between matches.
    let total_duration = $derived(
        Math.max(1, matchDuration(match_timing) + scoring_capture_sec),
    );
    let ticks_per_second = $derived(NUM_TICKS / total_duration);
    let phases = $derived(matchPhases(match_timing));

    let periods = $derived([
        { name: "auto", start: phases.auto.start, end: phases.auto.end },
        { name: "teleop", start: phases.teleop.start, end: phases.teleop.end },
    ]);

    // Shift boundaries within teleop, so the operator can see which shift a moment
    // belongs to without doing the arithmetic.
    let shift_marks = $derived(
        shiftWindows(match_timing)
            .filter((window) => window.shift !== Shift.AUTO)
            .map((window) => ({
                shift: window.shift,
                name: shiftName(window.shift),
                start: window.start,
            })),
    );

    function toPercent(time: number): number {
        return (100 * Math.min(Math.max(time, 0), total_duration)) / total_duration;
    }

    /**
     * Slider position, tracked separately from the reported time so that dragging
     * stays smooth while the server catches up with the requested position.
     */
    let dragging = $state(false);
    let drag_pos = $state(0);
    let timeline_pos = $derived(
        dragging ? drag_pos : Math.round(currentTime * ticks_per_second),
    );

    function handlePointClick(mouseEvent: MouseEvent) {
        const target = mouseEvent.currentTarget as HTMLButtonElement;
        const event_idx = parseInt(target.dataset.eventIdx!, 10);
        const event = events.find((e) => e.event_idx === event_idx)?.event;
        if (event) {
            warpToEvent?.(event);
        }
    }

    function handleSliderInput(event: Event) {
        const target = event.target as HTMLInputElement;
        const timeInTicks = parseInt(target.value, 10);
        dragging = true;
        drag_pos = timeInTicks;
        warpToTime?.(timeInTicks / ticks_per_second);
    }

    function handleSliderRelease() {
        dragging = false;
    }
</script>

<div class="timeline">
    <div class="timeline-points">
        {#each events as event (event.event.event_id)}
            <button
                class="point-wrap"
                type="button"
                style="left: calc(10px + (100% - 20px) * {toPercent(
                    event.event.time,
                )} / 100);"
                onclick={handlePointClick}
                data-event-idx={event.event_idx}
                aria-label="Jump to event {event.event_idx}"
            >
                <div
                    class="point-label"
                    style="background-color: {getEventTypeColor(
                        event.event.event_type,
                    )};"
                >
                    {event.event_idx}
                </div>
            </button>
        {/each}
    </div>
    <div class="slider-container">
        {#each periods as period (period.name)}
            <div
                class="slider-period {period.name}"
                style="left: calc(10px + (100% - 20px) * {toPercent(
                    period.start,
                )} / 100); width: calc((100% - 20px) * {toPercent(period.end) -
                    toPercent(period.start)} / 100);"
            ></div>
        {/each}
        {#each shift_marks as mark (mark.shift)}
            <div
                class="shift-mark"
                title={mark.name}
                style="left: calc(10px + (100% - 20px) * {toPercent(
                    mark.start,
                )} / 100);"
            ></div>
        {/each}
        <input
            type="range"
            min="0"
            max={NUM_TICKS}
            class="slider"
            aria-label="Match timeline position"
            value={timeline_pos}
            oninput={handleSliderInput}
            onchange={handleSliderRelease}
            onpointerup={handleSliderRelease}
            onpointercancel={handleSliderRelease}
        />
    </div>
</div>

<style lang="scss">
    .timeline {
        box-sizing: border-box;
        --slider-height: 30px;
    }

    .timeline-points {
        height: 30px;
        width: 100%;
        position: relative;
    }

    .point-wrap {
        position: absolute;
        background: none;
        top: 0;
        transform: translateX(-50%);
        filter: drop-shadow(-1px 6px 3px rgba(0, 0, 0, 0.5));
        z-index: 2;
        cursor: pointer;
    }
    .point-label {
        box-sizing: border-box;
        color: var(--text-active-dark);
        background-color: var(--gray-500);
        font-weight: bold;
        height: 30px;
        width: 20px;
        clip-path: polygon(0% 0%, 100% 0%, 100% 80%, 50% 100%, 0% 80%);
    }

    .slider-container {
        position: relative;
        height: var(--slider-height);
        background: var(--gray-600);
        border-radius: 8px;
        overflow: clip;
        box-shadow: 0 0 10px black;

        & .slider-period {
            position: absolute;
            top: 0;
            bottom: 0;

            &.auto {
                background-color: var(--auto-inactive);
            }
            &.teleop {
                background-color: var(--green-200);
            }
        }

        & .shift-mark {
            position: absolute;
            top: 0;
            bottom: 0;
            width: 1px;
            background-color: #0006;
        }
    }

    @mixin thumb {
        box-sizing: border-box;
        height: var(--slider-height);
        width: 20px;
        border-radius: 3px;
        border: 2px solid var(--gray-500);
        background: #ffffff;
        cursor: pointer;
    }
    @mixin track {
        width: 100%;
        height: var(--slider-height);
        cursor: pointer;
        background: transparent;
    }

    input[type="range"] {
        -webkit-appearance: none;
        appearance: none;
        width: 100%;
        background: transparent;
        height: var(--slider-height);
        margin: 0;
        position: relative;
        z-index: 1;

        /* Special styling for WebKit/Blink */
        &::-webkit-slider-thumb {
            @include thumb;
            -webkit-appearance: none;
        }

        /* All the same stuff for Firefox */
        &::-moz-range-thumb {
            @include thumb;
        }

        &::-webkit-slider-runnable-track {
            @include track;
        }
        &::-moz-range-track {
            @include track;
        }
    }
</style>
