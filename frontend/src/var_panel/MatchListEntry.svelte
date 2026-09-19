<script lang="ts">
    import { Alliance, MatchStatus, type VARMatch } from "../lib/model";

    interface Props {
        match: VARMatch;
        selected?: boolean;
        /** Matches cannot be switched while one is being recorded */
        disabled?: boolean;
        onclick?: (match: VARMatch) => void;
    }
    let { match, selected = false, disabled = false, onclick }: Props = $props();

    let result = $derived(match.arena_data?.result);
    let result_style_class = $derived.by(() => {
        switch (match.arena_data?.status) {
            case MatchStatus.RED_WON:
                return "alliance red";
            case MatchStatus.BLUE_WON:
                return "alliance blue";
            case MatchStatus.TIE:
                return "tie";
            default:
                return "";
        }
    });

    let red_teams = $derived(match.var_data.teams[Alliance.RED] ?? [0, 0, 0]);
    let blue_teams = $derived(match.var_data.teams[Alliance.BLUE] ?? [0, 0, 0]);
</script>

<button
    class="match-card"
    class:selected
    type="button"
    {disabled}
    title={disabled ? "Not available while recording a match" : undefined}
    onclick={() => onclick?.(match)}
>
    <div class="card-header">{match.var_data.var_id}</div>
    <div class="match-details">
        {#if result}
            <div class="match-section {result_style_class}">
                {result.red_summary.score} - {result.blue_summary.score}
            </div>
        {:else if !match.arena_data}
            <div class="match-section muted">No arena data</div>
        {/if}
        {#if !match.clip_available}
            <div class="match-section muted">No video clip</div>
        {/if}
        <div class="match-section team-lists">
            <ol class="red">
                {#each red_teams as team, idx (idx)}
                    <li>{team}</li>
                {/each}
            </ol>
            <ol class="blue">
                {#each [...blue_teams].reverse() as team, idx (idx)}
                    <li>{team}</li>
                {/each}
            </ol>
        </div>
    </div>
</button>

<style>
    .match-card {
        color: var(--text-active);
        box-sizing: border-box;
        flex: 0 0 auto;
        border: 4px solid var(--gray-600);
        border-radius: 10px;
        overflow: clip;
        background-color: var(--gray-700);
        display: flex;
        flex-direction: column;
        width: 140px;
        box-shadow: 0 0 8px black;
        margin: 0 10px;
        cursor: pointer;
    }

    .match-card.selected {
        border-color: var(--green-action);
    }

    .match-card:disabled {
        opacity: 0.5;
        cursor: default;
    }

    .card-header {
        background-color: var(--gray-600);
        font-weight: bold;
        padding: 2px 0.5em 4px 0.5em;
        box-shadow: 0 0px 8px black;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .match-details {
        display: flex;
        flex-direction: column;
        gap: 5px;
        padding: 5px 0;
        align-items: center;
    }

    .match-section {
        box-sizing: border-box;
        background-color: var(--gray-600);
        border-radius: 8px;
        overflow: clip;
        width: 90%;
        padding: 0.2em;
        box-shadow: 0 0 8px black;
        font-variant-numeric: tabular-nums;
    }
    .match-section.muted {
        color: var(--text-inactive-dark);
        font-size: 0.85em;
    }
    .match-section.alliance {
        background-color: var(--alliance-overlay-background);
    }
    .match-section.tie {
        background-color: var(--neutral-action);
    }

    .team-lists {
        display: flex;
        padding: 0;
        & ol {
            flex: 1 1 0%;
        }
        & .red {
            background-color: var(--red-overlay-background);
        }
        & .blue {
            background-color: var(--blue-overlay-background);
        }
    }
    ol {
        list-style-type: none;
        padding: 0;
        margin: 0;
    }
</style>
