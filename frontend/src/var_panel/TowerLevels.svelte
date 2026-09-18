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

    const levels = [TowerStatus.LEVEL_3, TowerStatus.LEVEL_2, TowerStatus.LEVEL_1];

    /** Teams parked at each rung of the tower, highest rung first */
    let rungs = $derived(
        levels.map((level) => ({
            level,
            label: towerStatusLabel(level),
            teams: teams.filter((_, idx) => statuses[idx] === level),
        })),
    );
    let grounded = $derived(
        teams.filter(
            (_, idx) => (statuses[idx] ?? TowerStatus.NONE) === TowerStatus.NONE,
        ),
    );
</script>

<div class="tower">
    {#each rungs as rung (rung.level)}
        <div class="rung" class:occupied={rung.teams.length > 0}>
            <div class="rung-label">{rung.label}</div>
            <div class="rung-teams">
                {#each rung.teams as team (team)}
                    <span class="team-chip">{team}</span>
                {/each}
            </div>
        </div>
    {/each}
    <div class="rung ground">
        <div class="rung-label">None</div>
        <div class="rung-teams">
            {#each grounded as team (team)}
                <span class="team-chip empty">{team}</span>
            {/each}
        </div>
    </div>
    {#if points !== undefined}
        <div class="tower-points">{points} pts</div>
    {/if}
</div>

<style>
    .tower {
        display: flex;
        flex-direction: column;
        gap: 3px;
        width: 100%;
    }

    @media (max-height: 850px) {
        .tower {
            gap: 2px;
        }
        .rung {
            min-height: 1.6em;
        }
    }

    .rung {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 0.5em;
        border-radius: 6px;
        background-color: var(--neutral-action);
        padding: 2px 6px;
        min-height: 1.9em;
    }

    .rung.occupied {
        background-color: var(--alliance-action);
        color: var(--text-active);
    }

    .rung.ground {
        background-color: transparent;
        border: 1px dashed var(--neutral-inactive);
    }

    .rung-label {
        font-weight: bold;
        font-size: 0.85em;
        width: 4.5em;
        text-align: left;
        white-space: nowrap;
    }

    .rung-teams {
        flex: 1 1 0%;
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 4px;
        justify-content: flex-end;
    }

    .team-chip {
        background-color: var(--alliance-highlight);
        border-radius: 4px;
        padding: 0 0.4em;
        font-variant-numeric: tabular-nums;
    }

    .team-chip.empty {
        background-color: transparent;
        color: var(--text-inactive-dark);
    }

    .tower-points {
        font-weight: bold;
        text-align: right;
        font-size: 0.85em;
        padding-top: 2px;
    }
</style>
