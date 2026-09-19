<script lang="ts">
    import {
        Alliance,
        type Score,
        type ScoreSummary,
        type Shift,
        type TeamTable,
        type UISettings,
    } from "../lib/model";
    import AllianceScoreCard from "./AllianceScoreCard.svelte";

    interface Props {
        /** Hide the score and RP details until the operator asks for them */
        hide_scores: boolean;
        red_score: Score;
        blue_score: Score;
        red_score_summary: ScoreSummary;
        blue_score_summary: ScoreSummary;
        teams: TeamTable;
        settings: UISettings;
        /** Shift currently in progress, highlighted in each fuel strip */
        current_shift?: Shift | null;
    }
    let {
        hide_scores,
        red_score,
        blue_score,
        red_score_summary,
        blue_score_summary,
        teams,
        settings,
        current_shift = null,
    }: Props = $props();

    let swap = $derived(settings.swap_red_blue);

    let hide_rp = $state(true);
    let hide_final_score = $state(true);

    // Re-hide the scores whenever the panel switches back to live data, so that the
    // next match does not start with the previous match's reveal still in effect.
    $effect(() => {
        if (hide_scores) {
            hide_rp = true;
            hide_final_score = true;
        }
    });

    let red_teams = $derived(teams[Alliance.RED] ?? [0, 0, 0]);
    let blue_teams = $derived(teams[Alliance.BLUE] ?? [0, 0, 0]);
</script>

<div class="score-root" class:swap>
    <AllianceScoreCard
        is_blue={true}
        score={blue_score}
        score_summary={blue_score_summary}
        opponent_summary={red_score_summary}
        teams={blue_teams}
        hide_final_score={hide_scores && hide_final_score}
        hide_rp={hide_scores && hide_rp}
        toggle_final_score={() => (hide_final_score = !hide_final_score)}
        toggle_rp={() => (hide_rp = !hide_rp)}
        final_score_on_right={!swap}
        {settings}
        {current_shift}
    />
    <AllianceScoreCard
        is_blue={false}
        score={red_score}
        score_summary={red_score_summary}
        opponent_summary={blue_score_summary}
        teams={red_teams}
        hide_final_score={hide_scores && hide_final_score}
        hide_rp={hide_scores && hide_rp}
        toggle_final_score={() => (hide_final_score = !hide_final_score)}
        toggle_rp={() => (hide_rp = !hide_rp)}
        final_score_on_right={swap}
        {settings}
        {current_shift}
    />
</div>

<style>
    .score-root {
        display: flex;
        flex-direction: row;
        align-items: stretch;
        gap: 10px;
        padding: 10px;
    }
    .score-root.swap {
        flex-direction: row-reverse;
    }

    /* Stack the alliances when there is not enough width for them side by side,
       keeping the swapped alliance first so the order still matches the field view */
    @media (max-width: 700px) {
        .score-root {
            flex-direction: column;
        }
        .score-root.swap {
            flex-direction: column-reverse;
        }
    }
</style>
