<script lang="ts">
  import { server_state } from "./lib/server_state.svelte";
  import type WebSocketClient from "./lib/wsclient.svelte";
  import StatusHeader from "./var_panel/StatusHeader.svelte";
  import MatchListEntry from "./var_panel/MatchListEntry.svelte";
  import EventListEntry from "./var_panel/EventListEntry.svelte";
  import Timeline from "./var_panel/Timeline.svelte";
  import VerticalList from "./var_panel/VerticalList.svelte";
  import EventCard from "./var_panel/EventCard.svelte";
  import ScoreCards from "./var_panel/ScoreCards.svelte";
  import {
    PLACEHOLDER_MATCH,
    PLACEHOLDER_SCORE,
    PLACEHOLDER_SCORE_SUMMARY,
    PLACEHOLDER_TEAMS,
    type MatchEvent,
    type TeamTable,
    type VARMatch,
  } from "./lib/model";
  import { REASONS } from "./lib/reasons";
  import { shiftAtTime } from "./lib/match_time";

  interface Props {
    ws: WebSocketClient;
  }

  let { ws }: Props = $props();

  /** Event the operator has open in the detail card, tracked by id so that it
   * survives the list being re-sorted when new events arrive */
  let selected_event_id: string | null = $state(null);

  let current_match = $derived(
    server_state.controller_status.selected_match_id
      ? server_state.matches[server_state.controller_status.selected_match_id]
      : undefined,
  );
  let realtime_data = $derived(server_state.controller_status.realtime_data);
  let settings = $derived(server_state.ui_settings);

  let displayed_arena_match = $derived.by(() => {
    if (realtime_data) {
      return server_state.realtime_match;
    }
    if (current_match?.arena_data) {
      return current_match.arena_data;
    }
    if (current_match) {
      // A recorded match whose arena entry is gone, e.g. the schedule was regenerated
      return {
        ...PLACEHOLDER_MATCH,
        id: current_match.var_data.arena_id,
        long_name: current_match.var_data.var_id,
        short_name: current_match.var_data.var_id,
      };
    }
    return PLACEHOLDER_MATCH;
  });

  let displayed_match_teams = $derived.by(() => {
    if (realtime_data) {
      const match = server_state.realtime_match;
      return {
        red: [match.red1, match.red2, match.red3],
        blue: [match.blue1, match.blue2, match.blue3],
      } as TeamTable;
    }
    return current_match?.var_data.teams ?? PLACEHOLDER_TEAMS;
  });

  let { red_score, blue_score, red_score_summary, blue_score_summary } =
    $derived.by(() => {
      if (realtime_data) {
        return {
          red_score: server_state.realtime_score.red.score,
          blue_score: server_state.realtime_score.blue.score,
          red_score_summary: server_state.realtime_score.red.score_summary,
          blue_score_summary: server_state.realtime_score.blue.score_summary,
        };
      }
      const result = current_match?.arena_data?.result;
      return {
        red_score: result?.red_score ?? PLACEHOLDER_SCORE,
        blue_score: result?.blue_score ?? PLACEHOLDER_SCORE,
        red_score_summary: result?.red_summary ?? PLACEHOLDER_SCORE_SUMMARY,
        blue_score_summary: result?.blue_summary ?? PLACEHOLDER_SCORE_SUMMARY,
      };
    });

  let sorted_matches = $derived(
    Object.values(server_state.matches).sort((a, b) =>
      b.var_data.match_start_timestamp.localeCompare(
        a.var_data.match_start_timestamp,
      ),
    ),
  );

  let sorted_events_with_idx = $derived(
    Array.from(current_match?.var_data.events ?? [])
      .sort((a, b) => a.time - b.time)
      .map((event, idx) => ({ event_idx: idx + 1, event })),
  );
  /** Newest first for the side list, without disturbing the timeline ordering */
  let listed_events = $derived([...sorted_events_with_idx].reverse());

  let selected_event = $derived(
    sorted_events_with_idx.find((e) => e.event.event_id === selected_event_id),
  );

  // Drop a selection that no longer exists, e.g. after switching matches or
  // deleting the event that was open.
  $effect(() => {
    if (selected_event_id !== null && selected_event === undefined) {
      selected_event_id = null;
    }
  });

  /** Container for the event detail card, scrolled into view when a new event is picked */
  let event_card_container: HTMLDivElement | undefined = $state();

  $effect(() => {
    if (selected_event_id !== null) {
      event_card_container?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  });

  let effective_time = $derived(
    server_state.controller_status.recording
      ? server_state.match_time.match_time_sec
      : server_state.hyperdeck_status.clip_time,
  );

  let current_shift = $derived(
    realtime_data ? shiftAtTime(effective_time, server_state.match_timing) : null,
  );

  function loadMatch(match: VARMatch) {
    ws.sendCommand("load_match", { match_id: match.var_data.var_id });
  }

  function warpToEvent(event: MatchEvent) {
    if (!current_match) {
      return;
    }
    ws.sendCommand("warp_to_time", {
      match_id: current_match.var_data.var_id,
      time: event.time,
    });
    selected_event_id = event.event_id;
  }

  function warpToTime(time: number) {
    if (!current_match) {
      return;
    }
    ws.sendCommand("warp_to_time", {
      match_id: current_match.var_data.var_id,
      time: time,
    });
  }

  function addVARReview() {
    if (!current_match) {
      return;
    }
    ws.sendCommand("add_var_review", {
      match_id: current_match.var_data.var_id,
      time: effective_time,
    });
  }

  function exitReview() {
    ws.sendCommand("exit_review", {});
  }

  function updateEvent(eventUpdates: Partial<MatchEvent>) {
    if (!current_match || !selected_event) {
      return;
    }
    ws.sendCommand("update_event", {
      match_id: current_match.var_data.var_id,
      event_id: selected_event.event.event_id,
      updates: eventUpdates,
    });
  }

  function deleteEvent() {
    if (!current_match || !selected_event) {
      return;
    }
    ws.sendCommand("delete_event", {
      match_id: current_match.var_data.var_id,
      event_id: selected_event.event.event_id,
    });
    selected_event_id = null;
  }
</script>

<div class="top-container">
  <StatusHeader
    server_connected={ws.state.connected}
    arena_connected={server_state.arena_connected}
    hyperdeck_connected={server_state.hyperdeck_connected}
    match_name={displayed_arena_match.long_name}
    match_time_sec={effective_time}
    match_timing={server_state.match_timing}
    hyperdeck_status={server_state.hyperdeck_status}
  />

  <main>
    <div class="match-ui-container">
      <div class="match-scroll-area">
        <ScoreCards
          hide_scores={realtime_data}
          {red_score}
          {blue_score}
          {red_score_summary}
          {blue_score_summary}
          teams={displayed_match_teams}
          {settings}
          {current_shift}
        />

        <div class="event-info-container" bind:this={event_card_container}>
        {#if selected_event}
          <EventCard
            reasons={REASONS}
            redTeams={[
              displayed_arena_match.red1,
              displayed_arena_match.red2,
              displayed_arena_match.red3,
            ]}
            blueTeams={[
              displayed_arena_match.blue1,
              displayed_arena_match.blue2,
              displayed_arena_match.blue3,
            ]}
            eventIdx={selected_event.event_idx}
            event={selected_event.event}
            match_timing={server_state.match_timing}
            swap={settings.swap_red_blue}
            onUpdateEvent={updateEvent}
            onDeleteEvent={deleteEvent}
          />
          {:else}
            <div class="event-placeholder">
              {#if sorted_events_with_idx.length > 0}
                Select an event to review it
              {:else if current_match}
                No review events for this match
              {:else}
                No match loaded
              {/if}
            </div>
          {/if}
        </div>
      </div>

      <div class="timeline-container">
        <Timeline
          events={sorted_events_with_idx}
          {warpToEvent}
          {warpToTime}
          currentTime={effective_time}
          match_timing={server_state.match_timing}
        />
      </div>
    </div>

    <div class="side-panels">
      <div class="events list-container">
        <button
          class="panel-action add-event"
          type="button"
          disabled={!current_match}
          onclick={addVARReview}>Add VAR Review</button
        >
        <VerticalList
          data={listed_events}
          key_func={(event) => event.event.event_id}
          empty_message="No events"
        >
          {#snippet item(data)}
            <EventListEntry
              event_idx={data.event_idx}
              event={data.event}
              teams={displayed_match_teams}
              match_timing={server_state.match_timing}
              selected={data.event.event_id === selected_event_id}
              onclick={warpToEvent}
            />
          {/snippet}
        </VerticalList>
      </div>

      <div class="matches list-container">
        <button class="panel-action go-live" type="button" onclick={exitReview}
          >Go Live</button
        >
        <VerticalList
          data={sorted_matches}
          key_func={(match) => match.var_data.var_id}
          empty_message="No recorded matches"
        >
          {#snippet item(data)}
            <MatchListEntry
              match={data}
              selected={data.var_data.var_id ===
                server_state.controller_status.selected_match_id}
              onclick={loadMatch}
            />
          {/snippet}
        </VerticalList>
      </div>
    </div>
  </main>
</div>

<style>
  @import "./lib/base_colors.css";

  :global(html) {
    height: 100%;
    -webkit-user-select: none;
    -moz-user-select: none;
    user-select: none;
    overscroll-behavior: none;
  }

  :global(body) {
    height: 100%;
    margin: 0;
    touch-action: manipulation;
  }

  .top-container {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  main {
    flex: 1 1 0%;
    min-height: 0;
    display: flex;
    flex-direction: row;
    align-items: stretch;
    width: 100%;
    overflow: hidden;
    /* Spacer for the iOS home bar */
    padding-bottom: env(safe-area-inset-bottom, 20px);

    background:
      radial-gradient(rgba(0, 0, 0, 0.5) 15%, transparent 16%) 0 0,
      radial-gradient(rgba(0, 0, 0, 0.5) 15%, transparent 16%) 8px 8px,
      radial-gradient(rgba(255, 255, 255, 0.05) 15%, transparent 20%) 0 1px,
      radial-gradient(rgba(255, 255, 255, 0.05) 15%, transparent 20%) 8px 9px;
    background-color: var(--gray-700);
    background-size: 16px 16px;
  }

  .match-ui-container {
    flex: 1 1 0%;
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .match-scroll-area {
    flex: 1 1 0%;
    min-height: 0;
    overflow-y: auto;
  }

  .timeline-container {
    flex: 0 0 auto;
    padding: 10px 20px;
  }

  .event-info-container {
    margin: 10px;
    display: flex;
    justify-content: center;
  }

  .event-placeholder {
    color: var(--text-inactive-dark);
    padding: 1.5em;
    font-style: italic;
  }

  .side-panels {
    flex: 0 0 auto;
    display: flex;
    flex-direction: row;
    min-height: 0;
  }

  .list-container {
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
    overflow: hidden;
    padding: 0 6px;
  }

  .panel-action {
    flex: 0 0 auto;
    background-color: var(--gray-600);
    color: var(--text-active-dark);
    border-radius: 8px;
    font-weight: bold;
    margin-top: 10px;
    min-height: 3.5em;
    padding: 0 0.5em;
    box-shadow: 0 0 12px black;
    cursor: pointer;

    &:disabled {
      opacity: 0.5;
      cursor: default;
    }

    &.add-event {
      background-color: var(--blue-200);
      width: 160px;
    }

    &.go-live {
      background-color: var(--red-400);
      color: var(--text-active);
      width: 140px;
    }
  }

  /* Tablets in portrait, and small laptop windows: move the lists under the main
     column and scroll them sideways instead of squeezing the score cards. */
  @media (max-width: 1000px) {
    main {
      flex-direction: column;
      overflow-y: auto;
    }

    .match-ui-container {
      flex: 0 0 auto;
    }

    .match-scroll-area {
      flex: 0 0 auto;
      overflow: visible;
    }

    .side-panels {
      flex-direction: column;
      gap: 6px;
    }

    .list-container {
      flex-direction: row;
      align-items: center;
      gap: 10px;
      height: auto;

      --list-direction: row;
      --list-overflow-x: auto;
      --list-overflow-y: hidden;
    }

    .panel-action {
      margin-top: 0;
      min-height: 4em;
    }
  }
</style>
