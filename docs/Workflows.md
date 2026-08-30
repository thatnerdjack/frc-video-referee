# Overview

This document describes the expected workflows for using the VAR system

## Users and Components

* VAR server: The server application managing the VAR infrastructure
* VAR tablet: The tablet with all of the VAR-facing controls
* VAR operator: The referee running the VAR system and performing video reviews
* HyperDeck: Recording and playback appliance
* Cheesy Arena (CA): The server running the playing field electronics and scoring systems
* Scorekeeper: The main operator of Cheesy Arena, controlling overall match flow
* Head Referee (HR): The lead referee, operating Cheesy Arena's head referee tablet

# Match Cycle

1. Arena transitions to the match ready state (as reported in ArenaStatus notifications)
2. VAR server automatically exits in-progress reviews and goes to the Live view
3. Scorekeepr clicks Start Match in Cheesy Arena
4. VAR server starts a recording in the HyperDeck
5. Cheesy Arena reports end of the AUTO period
6. VAR server automatically adds a review event for end-of-AUTO scoring 3 seconds after the report from Cheesy Arena
7. Cheesy Arena reports end of the match
8. VAR server automatically adds a review event for end-of-match scoring 3 seconds after the report from Cheesy Arena
9. VAR server stops the HyperDeck recording 5 seconds after the end-of-match report from Cheesy Arena
10. VAR server moves to post-match review mode and warps to the end-of-AUTO event
11. VAR operator cross-checks AUTO scores and advances to end-of-match using the VAR tablet
12. VAR operator cross-checks end-of-match scores using the VAR tablet
13. VAR operator examines any other review events generated during the match using the VAR tablet
14. VAR operator presess VAR ready button on the VAR tablet
15. Head Referee sees the VAR ready status on the HR tablet
16. Head Referee signals scoring ready, and Scorekeeper commits match scores
17. VAR server automatically moves to Live view
18. VAR server requests final match scores from Cheesy Arena and logs them for display in the VAR interface

# Logged Match Review

1. VAR operator selects a prior match from the match list on the VAR tablet
2. VAR server directs the HyperDeck to go to Output mode and load the appropriate match clip
3. VAR server downloads detailed scoring data for the match from Cheesy Arena and displays it on the tablet
4. VAR operator selects review events from a list on the tablet, or selects a moment on the tablet's match timeline
5. VAR server warps the HyperDeck to the appropriate position in the clip

# Reclaiming HyperDeck storage

1. HyperDeck reports its remaining record time in its MediaWorkingSet notifications
2. Once remaining record time drops below the configured threshold, VAR server builds a queue of clips to reclaim
3. Orphan clips (present on the deck but belonging to no recorded match) are queued first, then the oldest matches whose scores have been committed
4. VAR server waits for downtime: no recording or review in progress, arena in pre-match, field not ready to start, and no change to any of that for a settling period
5. During downtime the VAR server works through the queue one clip at a time, optionally copying each clip to a configured archive location before deleting it over FTP
6. If the arena becomes ready to start a match, any transfer in progress is abandoned and the queue is left for the next downtime window
7. Cleanup stops once the remaining record time reaches the configured target

# In-match review request by VAR operator

1. VAR operator presses a button on the VAR tablet to add a review event. VAR tablet records the moment the button was pressed
2. VAR operator adds optional information to the event (team, location, reason)
3. VAR operator saves the event; VAR tablet sends the event details to the VAR server
4. The event now apperas in the event list on the VAR tablet

# In-match review request by HR

1. Head Referee presses a VAR review button on the HR tablet.
2. Cheesy Arena logs the match time and adds the event to a list of HR-requested reviews
3. VAR server receives the event list in its next RealtimeScore notification
4. VAR server auto-creates a review event based on the data provided by Cheesy Arena
5. The VAR operator optionally edits the event to add more details