<script lang="ts">
    import { getEventTypeColor, getEventTypeString } from "../lib/events";
    import { formatMatchTime } from "../lib/match_time";
    import type { MatchEvent, MatchTiming, TeamTable } from "../lib/model";

    interface Props {
        event_idx: number;
        event: MatchEvent;
        /** Teams for the match this event belongs to, keyed by alliance */
        teams: TeamTable;
        match_timing: MatchTiming;
        selected?: boolean;
        onclick?: (event: MatchEvent) => void;
    }
    let { event_idx, event, teams, match_timing, selected = false, onclick }: Props =
        $props();

    let team_number = $derived.by(() => {
        if (event.alliance === undefined || event.team_idx === undefined) {
            return null;
        }
        return teams[event.alliance]?.[event.team_idx] ?? null;
    });
</script>

<button
    class="event-list-entry"
    class:selected
    type="button"
    onclick={() => onclick?.(event)}
>
    <div class="card-header">
        <span class="event-idx">{event_idx}</span>
        <span
            class="event-label"
            style="background-color: {getEventTypeColor(event.event_type)}"
            >{getEventTypeString(event.event_type)}</span
        >
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
                {#if team_number !== null}
                    Team {team_number}
                {:else}
                    <span class="alliance-name">{event.alliance}</span> Alliance
                {/if}
            </div>
        {/if}
    </div>
</button>

<style>
    .event-list-entry {
        box-sizing: border-box;
        flex: 0 0 auto;
        border: 4px solid var(--gray-600);
        border-radius: 10px;
        overflow: clip;
        background-color: var(--gray-700);
        color: var(--text-active);
        display: flex;
        flex-direction: column;
        width: 160px;
        box-shadow: 0 0 8px black;
        margin: 0 10px;
        cursor: pointer;
    }

    .event-list-entry.selected {
        border-color: var(--green-action);
    }

    .card-header {
        background-color: var(--gray-600);
        font-weight: bold;
        padding: 2px 0.5em 4px 0.5em;
        box-shadow: 0 0px 8px black;

        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 0.5em;

        & .event-label {
            flex: 1 1 0%;
            min-width: 0;
            color: var(--text-active-dark);
            border-radius: 16px;
            padding: 0 0.5em;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
    }

    .event-details {
        display: flex;
        flex-direction: column;
        gap: 5px;
        padding: 5px 0;
        align-items: center;
    }

    .event-section {
        box-sizing: border-box;
        background-color: var(--gray-600);
        border-radius: 4px;
        width: 90%;
        padding: 0.2em;
        box-shadow: 0 0 8px black;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .event-section.alliance {
        background-color: var(--alliance-overlay-background);
    }

    .alliance-name {
        text-transform: capitalize;
    }
</style>
