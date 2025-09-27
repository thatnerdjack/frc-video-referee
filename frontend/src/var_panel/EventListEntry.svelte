<script lang="ts">
    import { getEventTypeColor, getEventTypeString } from "../lib/events";
    import { formatMatchTime } from "../lib/match_time";
    import type { MatchEvent, MatchTiming, VARMatch } from "../lib/model";

    interface Props {
        event_idx: number;
        event: MatchEvent;
        match: VARMatch;
        match_timing: MatchTiming;
        onclick?: (event: MatchEvent) => void;
    }
    let { event_idx, event, match, match_timing, onclick }: Props = $props();
</script>

<button class="event-card" tabindex="0" onclick={() => onclick?.(event)}>
    <div class="card-header">
        <span class="event-idx">{event_idx}</span>
        <span
            class="event-label"
            style="background-color: {getEventTypeColor(event.event_type)}"
            >{getEventTypeString(event.event_type)}</span
        >
        <span class="event-spacer"></span>
    </div>
    <div class="event-details">
        <div class="event-section">
            {formatMatchTime(event.time, match_timing)}
        </div>
        {#if event.reason}
            <div class="event-section">{event.reason}</div>
        {/if}
        {#if event.alliance}
            <div class="event-section alliance {event.alliance}">
                {#if event.team_idx !== undefined}
                    Team {match.var_data.teams[event.alliance][event.team_idx]}
                {:else}
                    <span style="text-transform: capitalize"
                        >{event.alliance}</span
                    > Alliance
                {/if}
            </div>
        {/if}
    </div>
</button>

<style>
    .event-card {
        box-sizing: border-box;
        border: 4px solid var(--gray-600);
        border-radius: 10px;
        overflow: clip;
        background-color: var(--gray-700);
        display: flex;
        flex-direction: column;
        width: 160px;
        box-shadow: 0 0 8px black;
        margin: 0 10px;
    }
    .card-header {
        background-color: var(--gray-600);
        color: var(--text-active);
        font-weight: bold;
        padding: 2px 0.5em 4px 0.5em;
        box-shadow: 0 0px 8px black;

        display: flex;
        flex-direction: row;
        justify-content: space-between;

        & .event-label {
            color: var(--text-active-dark);
            border-radius: 16px;
            padding: 0 0.5em;
            min-width: 6em;
        }
    }

    .event-details {
        color: var(--text-active);
        display: flex;
        flex-direction: column;
        gap: 5px;
        padding: 5px 0;
        align-items: center;
    }

    .event-section {
        background-color: var(--gray-600);
        border-radius: 4px;
        width: 90%;
        padding: 0.2em;
        box-shadow: 0 0 8px black;
    }
    .event-section.alliance {
        background-color: var(--alliance-overlay-background);
    }
</style>
