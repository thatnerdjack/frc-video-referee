<script lang="ts">
    import { towerStatusLabel } from "../lib/game";
    import { TowerStatus } from "../lib/model";

    interface Props {
        /** Climb status for each robot on the alliance */
        statuses: TowerStatus[];
        /** Team numbers, in the same order as the statuses */
        teams: number[];
        /** Points scored on the tower for this phase of the match */
        points?: number;
    }
    let { statuses, teams, points }: Props = $props();

    let entries = $derived(
        teams.map((team, idx) => {
            const status = statuses[idx] ?? TowerStatus.NONE;
            return {
                team,
                status,
                label: towerStatusLabel(status),
                climbed: status !== TowerStatus.NONE,
            };
        }),
    );
</script>

<div class="tower-row">
    {#each entries as entry, idx (idx)}
        <div class="status-box" class:highlight={entry.climbed}>
            <div class="status-row1">{entry.team || "—"}</div>
            <div class="status-row2">{entry.label}</div>
        </div>
    {/each}
    {#if points !== undefined}
        <div class="tower-points">
            <span class="points-value">{points}</span>
            <span class="points-unit">pts</span>
        </div>
    {/if}
</div>

<style>
    /* Climbs are rare in match, so this stays a single compact row rather than a
       rung-by-rung diagram, leaving the vertical room for fuel and the timeline */
    .tower-row {
        display: flex;
        flex-direction: row;
        align-items: stretch;
        gap: 6px;
        width: 100%;
    }

    .status-box {
        flex: 1 1 0%;
        min-width: 0;
        border-radius: 6px;
        overflow: clip;
        font-size: 0.9em;

        & div {
            padding: 0.1em 0.2em;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        & .status-row1 {
            background-color: var(--alliance-highlight);
            font-weight: bold;
            font-variant-numeric: tabular-nums;
        }

        &:not(.highlight) .status-row2 {
            background-color: var(--neutral-action);
            color: var(--text-inactive-dark);
        }
        &.highlight .status-row2 {
            background-color: var(--alliance-action);
            font-weight: bold;
        }
    }

    .tower-points {
        flex: 0 0 auto;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: flex-end;
        min-width: 3.2em;
        font-variant-numeric: tabular-nums;
    }

    .points-value {
        font-weight: bold;
    }

    .points-unit {
        font-size: 0.7em;
        color: var(--text-inactive-dark);
    }
</style>
