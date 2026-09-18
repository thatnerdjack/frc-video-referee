<script lang="ts">
    import { formatMatchTimeWithShift } from "../lib/match_time";
    import {
        HyperdeckTransportMode,
        type HyperdeckStatus,
        type MatchTiming,
    } from "../lib/model";
    import pause_icon from "../assets/pause.svg";
    import play_icon from "../assets/play.svg";
    import live_icon from "../assets/live.svg";
    import record_icon from "../assets/record.svg";

    interface Props {
        server_connected: boolean;
        arena_connected: boolean;
        hyperdeck_connected: boolean;
        match_name: string;
        match_time_sec: number;
        match_timing: MatchTiming;
        hyperdeck_status: HyperdeckStatus;
    }

    let {
        server_connected,
        arena_connected,
        hyperdeck_connected,
        match_name,
        match_time_sec,
        match_timing,
        hyperdeck_status,
    }: Props = $props();

    let recorder_icon = $derived.by(() => {
        switch (hyperdeck_status.transport_mode) {
            case HyperdeckTransportMode.InputPreview:
                return live_icon;
            case HyperdeckTransportMode.InputRecord:
                return record_icon;
            case HyperdeckTransportMode.Output:
                return hyperdeck_status.playing ? play_icon : pause_icon;
            default:
                return live_icon;
        }
    });

    let recorder_label = $derived.by(() => {
        switch (hyperdeck_status.transport_mode) {
            case HyperdeckTransportMode.InputPreview:
                return "Live view";
            case HyperdeckTransportMode.InputRecord:
                return "Recording";
            case HyperdeckTransportMode.Output:
                return hyperdeck_status.playing ? "Playing" : "Paused";
            default:
                return "Unknown";
        }
    });

    let space_used_fraction = $derived(
        hyperdeck_status.total_space > 0
            ? 1 - hyperdeck_status.remaining_space / hyperdeck_status.total_space
            : 0,
    );

    /** Warn the operator before the recorder actually runs out of room */
    let storage_low = $derived(
        hyperdeck_connected && hyperdeck_status.remaining_record_time < 15 * 60,
    );

    function formatDuration(seconds: number): string {
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        const mm = mins.toString().padStart(2, "0");
        const ss = secs.toString().padStart(2, "0");

        return hrs > 0 ? `${hrs}:${mm}:${ss}` : `${mm}:${ss}`;
    }

    function formatPercentage(fraction: number): string {
        return `${(fraction * 100).toFixed(0)}%`;
    }
</script>

{#snippet connection(name: string, ok: boolean)}
    <span class="connection" class:ok class:err={!ok}>
        <span class="connection-dot" aria-hidden="true"></span>
        <span class="connection-name">{name}</span>
        <span class="visually-hidden">{ok ? "connected" : "disconnected"}</span>
    </span>
{/snippet}

<header>
    <div class="banner-section connections">
        {@render connection("Server", server_connected)}
        {@render connection("Arena", arena_connected)}
        {@render connection("Deck", hyperdeck_connected)}
    </div>
    <div class="banner-title" title={match_name}>{match_name}</div>
    <div class="banner-section status">
        <span class="match-clock"
            >{formatMatchTimeWithShift(match_time_sec, match_timing)}</span
        >
        <span class="recorder">
            <img
                class="player-status-icon"
                alt={recorder_label}
                title={recorder_label}
                src={recorder_icon}
            />
            <span class="record-time" class:low={storage_low}>
                {formatDuration(hyperdeck_status.remaining_record_time)} left
            </span>
            <span class="record-space">
                ({formatPercentage(space_used_fraction)} used)
            </span>
        </span>
    </div>
</header>

<style>
    header {
        box-sizing: border-box;
        width: 100%;
        color: var(--text-active-dark);
        background-color: var(--neutral-banner);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 2px 10px;
        font-weight: bold;
        font-size: clamp(11pt, 1.6vw, 18pt);

        --banner-title-angle: 30deg;
    }

    .banner-section {
        flex: 1 1 0%;
        min-width: 0;
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 0.8em;
        white-space: nowrap;
    }

    .banner-section.status {
        justify-content: flex-end;
    }

    .connection {
        display: inline-flex;
        align-items: center;
        gap: 0.3em;
    }

    .connection-dot {
        width: 0.7em;
        height: 0.7em;
        border-radius: 50%;
        background-color: var(--gray-400);
        box-shadow: inset 0 0 2px #0008;
    }

    .connection.ok .connection-dot {
        background-color: var(--green-300);
    }

    .connection.err .connection-dot {
        background-color: var(--red-400);
    }

    .connection.err .connection-name {
        color: var(--red-500);
    }

    .banner-title {
        contain: layout;
        background-color: black;
        width: fit-content;
        max-width: 40%;
        color: var(--text-active);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-weight: normal;
        z-index: 0;
        padding: 0 0.5em;

        &::before,
        &::after {
            content: "";
            position: absolute;
            width: 100%;
            height: 100%;
            background-color: black;
            z-index: -1;
        }

        &::before {
            left: 0;
            transform: skewX(var(--banner-title-angle));
            transform-origin: left bottom;
        }
        &::after {
            right: 0;
            transform: skewX(calc(var(--banner-title-angle) * -1));
            transform-origin: right bottom;
        }
    }

    .match-clock {
        font-variant-numeric: tabular-nums;
    }

    .recorder {
        display: inline-flex;
        align-items: center;
        gap: 0.3em;
    }

    .record-time.low {
        color: var(--red-500);
    }

    .player-status-icon {
        height: 1.3em;
        vertical-align: bottom;
    }

    .visually-hidden {
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip-path: inset(50%);
        white-space: nowrap;
    }

    /* Drop the least important details before the header starts wrapping */
    @media (max-width: 900px) {
        .record-space {
            display: none;
        }
    }

    @media (max-width: 700px) {
        .connection-name {
            display: none;
        }
        .banner-title {
            max-width: 50%;
        }
    }
</style>
