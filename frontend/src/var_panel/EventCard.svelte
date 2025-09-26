<script lang="ts">
    import { getEventTypeString } from "../lib/events";
    import { formatMatchTime } from "../lib/match_time";
    import type { MatchEvent, MatchTiming } from "../lib/model";
    import FieldMap from "./FieldMap.svelte";
    let editing = $state(false);
    // import { $inspect } from 'svelte/compiler';

    interface Props {
        reasons: string[];
        redTeams: number[];
        blueTeams: number[];
        selectedTeam?: number;
        eventIdx?: number;
        event?: MatchEvent;
        match_timing?: MatchTiming;
        onUpdateEvent?: (updates: Partial<MatchEvent>) => void;
    }
    let { reasons, redTeams, blueTeams, selectedTeam, eventIdx, event, match_timing, onUpdateEvent }: Props = $props();
</script>

<div class="event-card" class:editing>
    <div class="button-container">
        <button class="edit" onclick={() => (editing = !editing)}>Edit</button>
        <button class="delete">Delete</button>
    </div>
    <FieldMap />
    <div class="event-data-container">
        <div class="event-header">
            <div class="event-idx">{eventIdx}</div>
            <div class="event-type">{event?.event_type ? getEventTypeString(event.event_type) : ''}</div>
            <div class="event-time">{event && match_timing ? formatMatchTime(event.time, match_timing) : ''}</div>
        </div>
        <div class="event-sections">
            <div class="event-section">
                <div class="section-name">Reason</div>
                <div class="section-content event-reason">
                    {#if editing && event}
                        <select value={event.reason} onchange={(e) => onUpdateEvent?.({ reason: e.currentTarget.value })}>
                            {#each reasons as reason}
                                <option value={reason}>{reason}</option>
                            {/each}
                        </select>
                    {:else}
                        {event?.reason || ''}
                    {/if}
                </div>
            </div>
            <div class="event-section">
                <div class="section-name">Team</div>
                <div class="section-content team-lists">
                    <ol class="team-list blue">
                        {#each blueTeams as team}
                            <li class:selected={event?.team === team}>
                                <button
                                    onclick={editing ? () => onUpdateEvent?.({ team, alliance: "blue" }) : undefined}
                                    style="all: unset; cursor: pointer;"
                                >
                                    {team}
                                </button>
                            </li>
                        {/each}
                    </ol>

                    <ol class="team-list red">
                        {#each redTeams as team}
                            <li class:selected={event?.team === team}>
                                <button
                                    onclick={editing ? () => onUpdateEvent?.({ team, alliance: "red" }) : undefined}
                                    style="all: unset; cursor: pointer;"
                                >
                                    {team}
                                </button>
                            </li>
                        {/each}
                    </ol>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
    .event-card {
        box-sizing: border-box;

        background-color: var(--gray-700);
        border: 4px solid var(--gray-600);
        border-radius: 20px;
        box-shadow: 0 0 10px black;
        overflow: clip;

        display: flex;
        flex-direction: row;
    }
    .button-container {
        display: flex;
        flex-direction: column;
        width: 50px;

        & button {
            flex: 1 1 0%;
        }

        & .edit {
            font-size: 0;
            background: url("../assets/edit.svg") #726718 no-repeat center;
        }
        & .delete {
            font-size: 0;
            background: url("../assets/delete_forever.svg") var(--red-600)
                no-repeat center;
        }
        .editing & .edit {
            background: url("../assets/save.svg") var(--green-action) no-repeat
                center;
        }
    }

    .event-data-container {
        display: flex;
        flex-direction: column;

        & .event-header {
            display: flex;
            flex-direction: row;
            font-weight: bold;
            padding-bottom: 4px;
            background-color: var(--gray-600);

            & div {
                flex: 1 1 0%;
            }

            & .event-type {
                color: var(--text-active-dark);
                background-color: var(--green-200);
                border-radius: 16px;
                padding: 0 0.5em;
                min-width: 7em;
            }

            & .event-time {
                color: var(--text-active);
                min-width: 8em;
            }
        }
    }

    .event-sections {
        flex: 1 1 0%;
        padding: 10px;
        display: flex;
        flex-direction: column;
        justify-content: space-evenly;
        gap: 10px;
    }
    .event-section {
        background-color: var(--gray-600);
        border-radius: 8px;
        box-shadow: 0 0 6px black;
        width: 100%;

        display: flex;
        flex-direction: row;
        align-items: center;

        & .section-name {
            font-weight: bold;
            display: inline-block;
            width: 5.5em;
        }
        & .section-content {
            flex: 1 1 0%;
            position: relative;
        }
    }

    .event-reason {
        min-height: 3em;
        display: flex;
        justify-content: center;
        align-items: center;
    }

    .team-lists {
        display: flex;
        flex-direction: column;
        margin: 5px;
        gap: 5px;

        & .team-list {
            padding: 0;
            margin: 0;

            border-radius: 8px;
            background-color: var(--alliance-background);
            box-shadow: 0 0 4px black;

            display: flex;
            flex-direction: row;
            justify-content: space-evenly;

            & li {
                list-style: none;
                border-radius: 8px;
                padding: 5px 5px;
                width: 3em;

                &.selected {
                    background-color: var(--alliance-overlay-background);
                }

                &:not(:first-child):not(:last-child) {
                    margin: 0 5px;
                }
            }
        }
    }
</style>
