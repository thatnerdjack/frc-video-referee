<script lang="ts">
    import { getEventTypeColor, getEventTypeString } from "../lib/events";
    import { formatMatchTimeWithShift } from "../lib/match_time";
    import {
        Alliance,
        type EventCoordinates,
        type MatchEvent,
        type MatchTiming,
    } from "../lib/model";
    import FieldMap from "./FieldMap.svelte";

    interface Props {
        reasons: string[];
        redTeams: number[];
        blueTeams: number[];
        eventIdx?: number;
        event?: MatchEvent;
        match_timing: MatchTiming;
        /** Draw the red alliance on the left, matching the VAR field view */
        swap?: boolean;
        onUpdateEvent?: (updates: Partial<MatchEvent>) => void;
        onDeleteEvent?: () => void;
    }
    let {
        reasons,
        redTeams,
        blueTeams,
        eventIdx,
        event,
        match_timing,
        swap = false,
        onUpdateEvent,
        onDeleteEvent,
    }: Props = $props();

    let editing = $state(false);
    let confirming_delete = $state(false);

    // Selecting a different event should never leave the card in edit or confirm mode,
    // where the next tap would act on the wrong event. The event object itself is
    // replaced on every server update, so compare ids rather than resetting on any
    // change, which would drop the operator out of edit mode mid-edit.
    let last_event_id: string | undefined = undefined;
    $effect(() => {
        const event_id = event?.event_id;
        if (event_id !== last_event_id) {
            last_event_id = event_id;
            editing = false;
            confirming_delete = false;
        }
    });

    let alliances = $derived(
        swap
            ? [
                  { alliance: Alliance.RED, teams: redTeams },
                  { alliance: Alliance.BLUE, teams: blueTeams },
              ]
            : [
                  { alliance: Alliance.BLUE, teams: blueTeams },
                  { alliance: Alliance.RED, teams: redTeams },
              ],
    );

    function selectTeam(alliance: Alliance, team_idx: number) {
        if (!editing) {
            return;
        }
        // Tapping the selected team again clears the assignment.
        if (event?.alliance === alliance && event?.team_idx === team_idx) {
            onUpdateEvent?.({ alliance: undefined, team_idx: undefined });
        } else {
            onUpdateEvent?.({ alliance, team_idx });
        }
    }

    function setCoordinates(coordinates: EventCoordinates) {
        onUpdateEvent?.({ coordinates });
    }

    function handleDelete() {
        if (confirming_delete) {
            confirming_delete = false;
            onDeleteEvent?.();
        } else {
            confirming_delete = true;
        }
    }
</script>

<div class="event-card" class:editing>
    <div class="button-container">
        <button
            class="edit"
            type="button"
            aria-label={editing ? "Save event" : "Edit event"}
            title={editing ? "Save" : "Edit"}
            disabled={!event}
            onclick={() => {
                editing = !editing;
                confirming_delete = false;
            }}
        ></button>
        <button
            class="delete"
            class:confirming={confirming_delete}
            type="button"
            aria-label={confirming_delete ? "Confirm delete" : "Delete event"}
            title={confirming_delete ? "Tap again to confirm" : "Delete"}
            disabled={!event}
            onclick={handleDelete}
        >
            {#if confirming_delete}
                <span class="confirm-label">Sure?</span>
            {/if}
        </button>
    </div>

    <div class="event-data-container">
        <div class="event-header">
            <div class="event-idx">{eventIdx ?? ""}</div>
            <div
                class="event-type"
                style="background-color: {event
                    ? getEventTypeColor(event.event_type)
                    : 'var(--gray-500)'}"
            >
                {event ? getEventTypeString(event.event_type) : ""}
            </div>
            <div class="event-time">
                {event ? formatMatchTimeWithShift(event.time, match_timing) : ""}
            </div>
        </div>

        <div class="event-sections">
            <div class="event-section">
                <div class="section-name">Reason</div>
                <div class="section-content event-reason">
                    {#if editing && event}
                        <select
                            value={event.reason ?? ""}
                            onchange={(e) =>
                                onUpdateEvent?.({
                                    reason: e.currentTarget.value || undefined,
                                })}
                        >
                            <option value="">None</option>
                            {#each reasons as reason (reason)}
                                <option value={reason}>{reason}</option>
                            {/each}
                        </select>
                    {:else}
                        {event?.reason || "—"}
                    {/if}
                </div>
            </div>

            <div class="event-section">
                <div class="section-name">Team</div>
                <div class="section-content team-lists">
                    {#each alliances as entry (entry.alliance)}
                        <ol class="team-list {entry.alliance}">
                            {#each entry.teams as team, index (index)}
                                <li>
                                    <button
                                        type="button"
                                        class="team-button"
                                        class:selected={event?.team_idx === index &&
                                            event?.alliance === entry.alliance}
                                        disabled={!editing}
                                        onclick={() =>
                                            selectTeam(entry.alliance, index)}
                                    >
                                        {team || "—"}
                                    </button>
                                </li>
                            {/each}
                        </ol>
                    {/each}
                </div>
            </div>
        </div>
    </div>

    <div class="field-container">
        <FieldMap
            coordinates={event?.coordinates}
            editable={editing}
            {swap}
            onSetCoordinates={setCoordinates}
        />
    </div>
</div>

<style>
    .event-card {
        box-sizing: border-box;
        width: 100%;

        background-color: var(--gray-700);
        border: 4px solid var(--gray-600);
        border-radius: 16px;
        box-shadow: 0 0 10px black;
        overflow: clip;

        display: flex;
        flex-direction: row;
        align-items: stretch;
    }

    .button-container {
        display: flex;
        flex-direction: column;
        width: 56px;
        flex: 0 0 auto;

        & button {
            flex: 1 1 0%;
            cursor: pointer;
            color: var(--text-active);
            font-weight: bold;
        }

        & button:disabled {
            opacity: 0.4;
            cursor: default;
        }

        & .edit {
            background: url("../assets/edit.svg") #726718 no-repeat center;
        }
        & .delete {
            background: url("../assets/delete_forever.svg") var(--red-600) no-repeat
                center;
        }
        & .delete.confirming {
            background: var(--red-400);
        }
        .editing & .edit {
            background: url("../assets/save.svg") var(--green-action) no-repeat center;
        }
    }

    .confirm-label {
        font-size: 0.8em;
    }

    .event-data-container {
        flex: 1 1 0%;
        min-width: 0;
        display: flex;
        flex-direction: column;
    }

    .event-header {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 6px;
        font-weight: bold;
        padding: 4px 8px;
        background-color: var(--gray-600);

        & .event-idx {
            flex: 0 0 auto;
            min-width: 1.5em;
        }

        & .event-type {
            flex: 0 0 auto;
            color: var(--text-active-dark);
            border-radius: 16px;
            padding: 0 0.7em;
            min-width: 6em;
        }

        & .event-time {
            flex: 1 1 0%;
            min-width: 0;
            color: var(--text-active);
            text-align: right;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            font-variant-numeric: tabular-nums;
        }
    }

    .event-sections {
        flex: 1 1 0%;
        padding: 8px;
        display: flex;
        flex-direction: column;
        justify-content: space-evenly;
        gap: 8px;
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
            width: 5em;
            flex: 0 0 auto;
            padding-left: 0.5em;
            text-align: left;
        }
        & .section-content {
            flex: 1 1 0%;
            min-width: 0;
        }
    }

    .event-reason {
        min-height: 2.8em;
        display: flex;
        justify-content: center;
        align-items: center;

        & select {
            width: 90%;
            padding: 0.3em;
            border-radius: 6px;
        }
    }

    .team-lists {
        display: flex;
        flex-direction: column;
        margin: 5px;
        gap: 5px;

        & .team-list {
            padding: 0;
            margin: 0;
            list-style: none;

            border-radius: 8px;
            background-color: var(--alliance-background);
            box-shadow: 0 0 4px black;

            display: flex;
            flex-direction: row;
            justify-content: space-evenly;
            gap: 4px;
            padding: 3px;

            & li {
                flex: 1 1 0%;
                min-width: 0;
            }
        }
    }

    .team-button {
        width: 100%;
        border-radius: 6px;
        padding: 0.4em 0;
        color: var(--text-active);
        background-color: transparent;
        font-variant-numeric: tabular-nums;
    }

    .team-button:enabled {
        cursor: pointer;
    }

    .team-button.selected {
        background-color: var(--alliance-action);
        font-weight: bold;
    }

    .field-container {
        flex: 0 1 420px;
        min-width: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 8px;
    }

    /* Put the field map below the details once the card gets narrow */
    @media (max-width: 1100px) {
        .event-card {
            flex-wrap: wrap;
        }
        .field-container {
            flex: 1 1 100%;
        }
    }

    @media (max-width: 700px) {
        .field-container {
            display: none;
        }
    }
</style>
