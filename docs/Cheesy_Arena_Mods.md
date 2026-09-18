# Required Cheesy Arena changes

These changes are required to Cheesy Arena to support all VAR server features:
1. A websocket with notifiers for:
   * RealtimeScore (Detailed scoring status)
   * MatchTime (timestamping within matches)
   * MatchLoad (match IDs and lineups)
   * ArenaStatus (match ready indication)
2. Websocket operation to signal VAR scoring done
3. List in RealtimeScore of field-requested VAR review moments
4. Button on HR panel to add to the VAR review list (scoring panels too?)
# Game-specific data tracked by the VAR server

The VAR panel mirrors Cheesy Arena's 2026 scoring model. These are the parts of the
arena's API that the panel depends on, and which need revisiting when the game changes:

* `MatchState` values in the arena's `field` package. The VAR server's copy of this
  enum must match exactly; 2026 removed the warmup state, which shifted every value
  after it.
* `matchTiming` fields. In 2026 teleop is described by a transition shift, four
  contested shifts and an endgame shift rather than a single teleop duration.
* `game.Score`: per-robot auto and endgame `TowerStatus`, and the `Hub`'s `WonAuto`
  flag plus its per-shift Fuel counts.
* `game.ScoreSummary`: the point breakdown and the three bonus ranking point flags.
  The panel treats these flags as authoritative for whether an RP was earned, since
  the arena applies rules such as G206 that the panel does not model.
* Bonus RP thresholds are configured on the arena's settings page. Mirror them in the
  VAR server's `[ui.*-rp]` settings so the panel's progress readouts agree.
