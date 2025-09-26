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
    MatchStatus,
    MatchType,
    PLACEHOLDER_MATCH,
    PLACEHOLDER_SCORE,
    PLACEHOLDER_SCORE_SUMMARY,
    type MatchEvent,
    type VARMatch,
  } from "./lib/model";
    import { REASONS } from "./lib/reasons";

  interface Props {
    ws: WebSocketClient;
    selectedEventIdx?: number;
  }

  let { ws, selectedEventIdx }: Props = $props();

  let current_match = $derived(
    server_state.matches[
      server_state.controller_status.selected_match_id ?? ""
    ],
  );
  let realtime_data = $derived(server_state.controller_status.realtime_data);

  let displayed_arena_match = $derived.by(() => {
    if (realtime_data) {
      return server_state.realtime_match;
    } else {
      if (current_match) {
        return (
          current_match.arena_data ?? {
            id: current_match.var_data.arena_id,
            match_type: MatchType.TEST,
            type_order: 0,
            long_name: current_match.var_data.var_id,
            short_name: current_match.var_data.var_id,
            red1: 0,
            red2: 0,
            red3: 0,
            blue1: 0,
            blue2: 0,
            blue3: 0,
            status: MatchStatus.SCHEDULED,
          }
        );
      } else {
        return PLACEHOLDER_MATCH;
      }
    }
  });

  let displayed_match_teams = $derived(
    current_match?.var_data.teams ?? { red: [0, 0, 0], blue: [0, 0, 0] },
  );

  let { red_score, blue_score, red_score_summary, blue_score_summary } =
    $derived.by(() => {
      if (realtime_data) {
        return {
          red_score: server_state.realtime_score.red.score,
          blue_score: server_state.realtime_score.blue.score,
          red_score_summary: server_state.realtime_score.red.score_summary,
          blue_score_summary: server_state.realtime_score.blue.score_summary,
        };
      } else {
        return {
          red_score:
            current_match.arena_data?.result?.red_score ?? PLACEHOLDER_SCORE,
          blue_score:
            current_match.arena_data?.result?.blue_score ?? PLACEHOLDER_SCORE,
          red_score_summary:
            current_match.arena_data?.result?.red_summary ??
            PLACEHOLDER_SCORE_SUMMARY,
          blue_score_summary:
            current_match.arena_data?.result?.blue_summary ??
            PLACEHOLDER_SCORE_SUMMARY,
        };
      }
    });

  let sorted_matches = $derived(
    Object.values(server_state.matches).sort((a, b) =>
      a.var_data.match_start_timestamp < b.var_data.match_start_timestamp
        ? 1
        : b.var_data.match_start_timestamp < a.var_data.match_start_timestamp
          ? -1
          : 0,
    ),
  );

  let event_list = $derived(current_match?.var_data.events ?? []);
  let sorted_events = $derived(
    Array.from(event_list).sort((a, b) => a.time - b.time),
  );
  let sorted_events_with_idx = $derived(
    sorted_events.map((event, idx) => ({ event_idx: idx + 1, event })),
  );

  let effective_time = $derived(
    server_state.controller_status.recording
      ? server_state.match_time.match_time_sec
      : server_state.hyperdeck_status.clip_time,
  );

  function loadMatch(match: VARMatch) {
    ws.sendCommand("load_match", { match_id: match.var_data.var_id });
  }
  function warpToEvent(event: MatchEvent) {
    if (current_match) {
      ws.sendCommand("warp_to_time", {
        match_id: current_match.var_data.var_id,
        time: event.time,
      });

      // TODO: This is kinda hot garbage, but it works for now
      selectedEventIdx = sorted_events_with_idx.find(
        (e) => e.event.event_id === event.event_id,
      )?.event_idx;
    }
  }
  function warpToTime(time: number) {
    if (current_match) {
      ws.sendCommand("warp_to_time", {
        match_id: current_match.var_data.var_id,
        time: time,
      });
    }
  }
  function addVARReview() {
    if (current_match) {
      ws.sendCommand("add_var_review", {
        match_id: current_match.var_data.var_id,
        time: effective_time,
      });
    }
  }
  function exitReview() {
    ws.sendCommand("exit_review", {});
  }

  function updateEvent(eventUpdates: Partial<MatchEvent>) {
    if (current_match && selectedEventIdx !== undefined) {
      const eventToUpdate = sorted_events_with_idx.find(e => e.event_idx === selectedEventIdx)?.event;
      if (eventToUpdate) {
        // Send update command to the server
        ws.sendCommand("update_event", {
          match_id: current_match.var_data.var_id,
          event_id: eventToUpdate.event_id,
          updates: eventUpdates
        });
      }
    }
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
      <div class="scoring-container">
        <ScoreCards
          hide_scores={realtime_data}
          {red_score}
          {blue_score}
          {red_score_summary}
          {blue_score_summary}
          teams={displayed_match_teams}
          swap={server_state.ui_settings.swap_red_blue}
          reef_level_rp_threshold={server_state.ui_settings
            .reef_level_rp_threshold}
          barge_rp_threshold={server_state.ui_settings.barge_rp_threshold}
        />
      </div>
      <div class="flex-spacer" style="flex: 1 1 0%"></div>
      <div class="event-info-container">
        {#if selectedEventIdx !== undefined}
          <EventCard 
            reasons={REASONS}
            redTeams={[displayed_arena_match.red1, displayed_arena_match.red2, displayed_arena_match.red3]}
            blueTeams={[displayed_arena_match.blue1, displayed_arena_match.blue2, displayed_arena_match.blue3]}
            eventIdx={selectedEventIdx}
            event={sorted_events_with_idx.find(e => e.event_idx === selectedEventIdx)?.event}
            match_timing={server_state.match_timing}
            onUpdateEvent={updateEvent}
          />
        {/if}
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
    <div class="events list-container">
      <button class="add-event" onclick={addVARReview}>Add VAR Review</button>
      <VerticalList
        data={sorted_events_with_idx.reverse()}
        key_func={(event) => event.event.event_id}
      >
        {#snippet item(data)}
          <EventListEntry
            event_idx={data.event_idx}
            event={data.event}
            match={current_match}
            match_timing={server_state.match_timing}
            onclick={warpToEvent}
          />
        {/snippet}
      </VerticalList>
    </div>
    <div class="matches list-container">
      <button class="go-live" onclick={exitReview}>Go Live</button>
      <VerticalList
        data={sorted_matches}
        key_func={(match) => match.var_data.var_id}
      >
        {#snippet item(data)}
          <MatchListEntry match={data} onclick={loadMatch} />
        {/snippet}
      </VerticalList>
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
  }

  main {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    width: 100%;
    height: 100%;
    overflow: hidden;
    padding-bottom: 20px; /* Spacer for the iOS home bar */

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
    display: flex;
    flex-direction: column;
  }

  .scoring-container {
    width: 100%;
  }

  .timeline-container {
    padding: 0 20px;
  }

  .event-info-container {
    margin: 10px;
    display: flex;
    justify-content: center;
  }

  .list-container {
    height: 100%;
    overflow: hidden;
  }

  button {
    background-color: var(--gray-600);
    color: var(--text-active-dark);
    border-radius: 8px;
    font-weight: bold;
    margin-top: 10px;
    height: 4em;
    box-shadow: 0 0 12px black;

    &.add-event {
      background-color: var(--blue-200);
      width: 160px;
    }

    &.go-live {
      background-color: var(--red-400);
      width: 140px;
    }
  }
</style>
