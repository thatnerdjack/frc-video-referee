<script lang="ts">
    import {
        autoFuel,
        bonusRankingPoints,
        fuelGoal,
        postMatchFuel,
        projectedRankingPoints,
        teleopFuel,
        towerPoints,
    } from "../lib/game";
    import type { Shift, Score, ScoreSummary, UISettings } from "../lib/model";
    import ShiftStrip from "./ShiftStrip.svelte";
    import TowerLevels from "./TowerLevels.svelte";

    interface Props {
        is_blue: boolean;
        score: Score;
        score_summary: ScoreSummary;
        /** Opponent's summary, used to project the ranking points for the match outcome */
        opponent_summary: ScoreSummary;
        teams: number[];
        hide_final_score: boolean;
        hide_rp: boolean;
        toggle_rp?: () => void;
        toggle_final_score?: () => void;
        final_score_on_right: boolean;
        settings: UISettings;
        /** Shift currently in progress, highlighted in the fuel strip */
        current_shift?: Shift | null;
    }
    let {
        is_blue,
        score,
        score_summary,
        opponent_summary,
        teams,
        hide_final_score,
        hide_rp,
        toggle_rp,
        toggle_final_score,
        final_score_on_right,
        settings,
        current_shift = null,
    }: Props = $props();

    let auto_fuel = $derived(autoFuel(score.hub));
    let teleop_fuel = $derived(teleopFuel(score.hub));
    let post_match_fuel = $derived(postMatchFuel(score.hub));
    let total_fuel = $derived(auto_fuel + teleop_fuel + post_match_fuel);

    let fuel_goal = $derived(fuelGoal(score_summary, settings));

    let rp_rows = $derived(bonusRankingPoints(score_summary, settings));
    let projected_rp = $derived(
        projectedRankingPoints(score_summary, opponent_summary, settings),
    );

    let outcome_label = $derived.by(() => {
        switch (projected_rp.outcome) {
            case "win":
                return "Win";
            case "loss":
                return "Loss";
            default:
                return "Tie";
        }
    });
</script>

{#snippet check(ok: boolean)}
    {#if ok}
        <span class="check ok">✓</span>
    {:else}
        <span class="check miss">✗</span>
    {/if}
{/snippet}

<section class="alliance-score" class:red={!is_blue} class:blue={is_blue}>
    <header class="score-header" class:swap={final_score_on_right}>
        <button
            class="score-total"
            type="button"
            aria-label="Toggle final score visibility"
            onclick={toggle_final_score}
        >
            {#if !hide_final_score}
                {score_summary.score}
            {:else}
                <span class="hidden-marker">••</span>
            {/if}
        </button>
        <div class="score-banner">
            {is_blue ? "Blue" : "Red"} Alliance
        </div>
    </header>

    <div class="score-card">
        <div class="score-title">Auto</div>
        <div class="score-content">
            <TowerLevels
                statuses={score.auto_tower_statuses}
                {teams}
                points={score_summary.auto_tower_points}
            />
            <div class="stat-row">
                <span class="stat-label">Auto Fuel</span>
                <span class="stat-value auto">{auto_fuel}</span>
                <span class="stat-label">Hub</span>
                <span class="stat-value">
                    {score.hub.won_auto ? "Won Auto" : "Lost Auto"}
                </span>
            </div>
        </div>
    </div>

    <div class="score-card">
        <div class="score-title">Fuel</div>
        <div class="score-content">
            <div class="fuel-totals">
                <div class="fuel-total">
                    <div class="fuel-count">{score_summary.num_fuel}</div>
                    <div class="fuel-goal">
                        {#if fuel_goal !== null}
                            of {fuel_goal}
                        {:else}
                            scored
                        {/if}
                    </div>
                </div>
                <div class="fuel-breakdown">
                    <div><span class="stat-label">Auto</span> {auto_fuel}</div>
                    <div><span class="stat-label">Teleop</span> {teleop_fuel}</div>
                    {#if post_match_fuel > 0}
                        <div>
                            <span class="stat-label">Post</span>
                            {post_match_fuel}
                        </div>
                    {/if}
                    {#if total_fuel !== score_summary.num_fuel}
                        <div class="mismatch" title="Counted by the hub but not scored">
                            {total_fuel} counted
                        </div>
                    {/if}
                </div>
            </div>
            <ShiftStrip hub={score.hub} {current_shift} />
        </div>
    </div>

    <div class="score-card">
        <div class="score-title">Endgame</div>
        <div class="score-content">
            <TowerLevels
                statuses={score.endgame_tower_statuses}
                {teams}
                points={score_summary.teleop_tower_points}
            />
            <div class="stat-row">
                <span class="stat-label">Tower Total</span>
                <span class="stat-value">{towerPoints(score_summary)}</span>
                <span class="stat-label">Fouls</span>
                <span class="stat-value">+{score_summary.foul_points}</span>
            </div>
        </div>
    </div>

    <div class="score-card rp-card">
        <div class="score-title">RP</div>
        <button
            class="score-content rp-wrapper"
            class:hide_rp
            type="button"
            aria-label="Toggle ranking point visibility"
            onclick={toggle_rp}
        >
            <div class="rp-summary">
                {#each rp_rows as rp (rp.key)}
                    <div class="status-box" class:highlight={rp.achieved}>
                        <div class="status-row1">{rp.label}</div>
                        <div class="status-row2">
                            {#if rp.goal > 0}
                                {rp.current}/{rp.goal}
                            {/if}
                            {@render check(rp.achieved)}
                        </div>
                    </div>
                {/each}
                <div class="status-box total-rp">
                    <div class="status-row1">{outcome_label}</div>
                    <div class="status-row2">
                        {projected_rp.total} RP
                    </div>
                </div>
            </div>
        </button>
    </div>
</section>

<style>
    .alliance-score {
        box-sizing: border-box;
        background-color: var(--alliance-background);
        padding: 0 10px 10px 10px;
        border-radius: 16px;
        border: 4px solid var(--alliance-overlay-background);
        box-shadow: 0 0 10px black;
        overflow: clip;

        flex: 1 1 0%;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .score-header {
        display: flex;
        flex-direction: row;
        font-weight: bold;
        align-items: center;
        gap: 8px;
        margin-top: 8px;
    }

    .score-header.swap {
        flex-direction: row-reverse;
    }

    .score-total {
        background-color: var(--alliance-overlay-background);
        color: var(--text-active);
        border-radius: 8px;
        box-shadow: 0 0 6px black;
        width: 3.5em;
        height: 2em;
        font-weight: bold;
        font-size: 1.1em;
        font-variant-numeric: tabular-nums;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
    }

    .hidden-marker {
        color: var(--text-inactive-dark);
    }

    .score-banner {
        flex: 1 1 0%;
        min-width: 0;
        text-align: center;
    }

    .score-card {
        background-color: var(--alliance-overlay-background);
        border-radius: 8px;
        box-shadow: 0 0 6px black;
        padding: 6px;

        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 6px;
    }

    .score-title {
        font-weight: bold;
        /* Wide enough for the longest section name ("Endgame") without clipping */
        width: 5em;
        font-size: 0.9em;
        flex: 0 0 auto;
        text-align: left;
    }

    .score-content {
        flex: 1 1 0%;
        min-width: 0;
        position: relative;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .stat-row {
        display: flex;
        flex-direction: row;
        align-items: baseline;
        justify-content: space-between;
        gap: 6px;
        font-size: 0.85em;
    }

    .stat-label {
        color: var(--text-inactive-dark);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-size: 0.85em;
    }

    .stat-value {
        font-weight: bold;
        font-variant-numeric: tabular-nums;
    }

    .stat-value.auto {
        color: var(--fuel-auto);
    }

    .fuel-totals {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 10px;
    }

    .fuel-total {
        display: flex;
        flex-direction: row;
        align-items: baseline;
        gap: 0.3em;
    }

    .fuel-count {
        font-size: 1.6em;
        font-weight: bold;
        color: var(--fuel);
        font-variant-numeric: tabular-nums;
        line-height: 1;
    }

    .fuel-goal {
        font-size: 0.8em;
        color: var(--text-inactive-dark);
        white-space: nowrap;
    }

    .fuel-breakdown {
        flex: 1 1 0%;
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 2px 10px;
        font-size: 0.85em;
        font-variant-numeric: tabular-nums;
    }

    .mismatch {
        color: var(--auto-action);
    }

    .check {
        font-weight: bold;
        display: inline-block;
        inline-size: 1em;
    }

    .ok {
        color: var(--green-200);
    }

    .miss {
        color: var(--red-200);
    }

    .rp-wrapper {
        color: inherit;
        cursor: pointer;
        text-align: inherit;
        border-radius: 6px;
    }

    /* Concealed scores sit on a shade of the alliance colour, so the card still
       reads as that alliance's while the numbers are hidden */
    .hide_rp {
        background-color: var(--alliance-highlight);
    }

    .rp-summary {
        /* Wraps to a second row rather than squeezing longer RP names */
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(5.5em, 1fr));
        gap: 6px;
        width: 100%;
    }

    .status-box {
        flex: 1 1 0%;
        min-width: 0;
        border-radius: 8px;
        overflow: clip;
        font-size: 0.9em;

        & div {
            padding: 0.25em 0.2em;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        & .status-row1 {
            background-color: var(--alliance-highlight);
            font-weight: bold;
        }

        &:not(.highlight) .status-row2 {
            background-color: var(--neutral-action);
        }
        &.highlight .status-row2 {
            background-color: var(--alliance-action);
        }
    }

    .total-rp .status-row2 {
        background-color: var(--neutral-highlight);
        font-weight: bold;
    }

    .hide_rp:after {
        content: "Tap to reveal";
        position: absolute;
        inset: 0;
        margin-inline: auto;
        width: fit-content;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        color: var(--text-active);
        pointer-events: none;
    }
    .hide_rp .rp-summary {
        visibility: hidden;
    }

    /* Very short displays: scale the whole card down so the scores, the event card
       and the timeline all still fit without scrolling */
    @media (max-height: 700px) {
        .alliance-score {
            font-size: 0.85em;
        }
    }

    @media (max-height: 650px) {
        .alliance-score {
            font-size: 0.75em;
            gap: 4px;
        }
        .score-card {
            padding: 3px 5px;
        }
    }

    /* Short landscape displays, e.g. a tablet in a stand: trade padding for the
       vertical room the event card and timeline need */
    @media (max-height: 850px) {
        .alliance-score {
            gap: 5px;
            padding-bottom: 6px;
        }
        .score-card {
            padding: 4px 6px;
        }
        .score-content {
            gap: 3px;
        }
        .score-header {
            margin-top: 5px;
        }
    }

    /* Stack each section's title above its contents once the card gets narrow,
       so section names are never squeezed into an unreadable column */
    @media (max-width: 900px) {
        .score-card {
            flex-direction: column;
            align-items: stretch;
        }
        .score-title {
            width: auto;
            font-size: 0.8em;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-inactive);
        }
        .fuel-count {
            font-size: 1.3em;
        }
    }
</style>
