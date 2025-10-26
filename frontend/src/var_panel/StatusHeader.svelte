<script lang="ts">
    import { formatMatchTime } from "../lib/match_time";
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
                if (hyperdeck_status.playing) {
                    return play_icon;
                } else {
                    return pause_icon;
                }
        }
    });

    function formatDuration(seconds: number): string {
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        const mm = mins.toString().padStart(2, '0');
        const ss = secs.toString().padStart(2, '0');

        if (hrs > 0) {
            const hh = hrs.toString();
            return `${hh}:${mm}:${ss}`;
        } else {
            return `${mm}:${ss}`;
        }
    }

    function formatPercentage(numerator: number, denominator: number): string {
        if (denominator === 0) return "0%";
        const percent = (numerator / denominator) * 100;
        return `${percent.toFixed(1)}%`;
    }
</script>

{#snippet status(ok: boolean)}
    {#if ok}
        <span class="status-check status-ok">✓</span>
    {:else}
        <span class="status-check status-err">✗</span>
    {/if}
{/snippet}

<header>
    <div class="banner_data">
        Server: {@render status(server_connected)}
        Arena: {@render status(arena_connected)}
        Hyperdeck: {@render status(hyperdeck_connected)}
    </div>
    <div class="banner_title">{match_name}</div>
    <div class="banner_data">
        {formatMatchTime(match_time_sec, match_timing)}
        <img
            class="player-status-icon"
            alt="hyperdeck status icon"
            src={recorder_icon}
        />
        {formatDuration(hyperdeck_status.remaining_record_time)} Left ({formatPercentage(
            hyperdeck_status.remaining_space,
            hyperdeck_status.total_space
        )})
    </div>
</header>

<style>
    header {
        width: 100%;
        color: var(--text-active-dark);
        background-color: var(--neutral-banner);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 18pt;

        --banner-title-angle: 30deg;
    }

    .status-check {
        font-weight: bold;
        display: inline-block;
        inline-size: 1em;
    }

    .status-ok {
        color: green;
    }

    .status-err {
        color: red;
    }

    .banner_data {
        flex: 1 1 0%;
    }

    .banner_title {
        contain: layout;
        background-color: black;
        width: fit-content;
        color: var(--text-active);
        white-space: nowrap;
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

    .player-status-icon {
        height: 1.3em;
        vertical-align: bottom;
        margin-left: 0.5em;
    }
</style>
