import { mount } from 'svelte'
import './app.css'
import App from './App.svelte'
import WebSocketClient from './lib/wsclient.svelte'
import {
  DEFAULT_MATCH_TIMING,
  DEFAULT_UI_SETTINGS,
  WebsocketEventType,
  type ControllerStatus,
  type HyperdeckStatus,
  type Match,
  type MatchTime,
  type MatchTiming,
  type RealtimeScore,
  type UISettings,
  type VARMatchTable,
} from './lib/model'
import { server_state } from './lib/server_state.svelte'

const defaultDevWebsocketAddress = window.location.hostname + ':8000';
const websocketAddress = import.meta.env.DEV ? (import.meta.env.VITE_VAR_SERVER || defaultDevWebsocketAddress) : window.location.host;

const ws = new WebSocketClient(websocketAddress);

// Settings sections added to the server after a panel was built arrive missing, so
// merge them over the defaults rather than replacing the whole object.
ws.subscribe(WebsocketEventType.UISettings, (data) => {
  server_state.ui_settings = { ...DEFAULT_UI_SETTINGS, ...(data as Partial<UISettings>) };
});
ws.subscribe(WebsocketEventType.ControllerStatus, (data) => {
  server_state.controller_status = data as ControllerStatus;
});
ws.subscribe(WebsocketEventType.CurrentMatchData, (data) => {
  server_state.realtime_match = data as Match;
});
ws.subscribe(WebsocketEventType.CurrentMatchTime, (data) => {
  server_state.match_time = data as MatchTime;
});
ws.subscribe(WebsocketEventType.MatchTiming, (data) => {
  server_state.match_timing = { ...DEFAULT_MATCH_TIMING, ...(data as Partial<MatchTiming>) };
});
ws.subscribe(WebsocketEventType.RealtimeScore, (data) => {
  server_state.realtime_score = data as RealtimeScore;
});
ws.subscribe(WebsocketEventType.MatchList, (data) => {
  server_state.matches = data as VARMatchTable;
});
ws.subscribe(WebsocketEventType.ArenaConnection, (data) => {
  server_state.arena_connected = data.connected;
});
ws.subscribe(WebsocketEventType.HyperdeckConnection, (data) => {
  server_state.hyperdeck_connected = data.connected;
});
ws.subscribe(WebsocketEventType.HyperdeckStatus, (data) => {
  server_state.hyperdeck_status = data as HyperdeckStatus;
});

ws.enable();

const app = mount(App, {
  target: document.getElementById('app')!,
  props: {
    ws: ws,
  },
})


export default app
