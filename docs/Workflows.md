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
3. VAR server starts a pre-roll recording in the HyperDeck, restarting it every 10 seconds
   while it waits for the match to start (see "Pre-roll recording" below)
4. Scorekeepr clicks Start Match in Cheesy Arena
5. VAR server keeps the in-progress pre-roll recording as the recording for the match, so the
   clip also covers the moments leading up to the match start
6. Cheesy Arena reports end of the AUTO period
7. VAR server automatically adds a review event for end-of-AUTO scoring 3 seconds after the report from Cheesy Arena
8. Cheesy Arena reports end of the match
9. VAR server automatically adds a review event for end-of-match scoring 3 seconds after the report from Cheesy Arena
10. VAR server stops the HyperDeck recording 5 seconds after the end-of-match report from Cheesy Arena
11. VAR server moves to post-match review mode and warps to the end-of-AUTO event
12. VAR operator cross-checks AUTO scores and advances to end-of-match using the VAR tablet
13. VAR operator cross-checks end-of-match scores using the VAR tablet
14. VAR operator examines any other review events generated during the match using the VAR tablet
15. VAR operator presess VAR ready button on the VAR tablet
16. Head Referee sees the VAR ready status on the HR tablet
17. Head Referee signals scoring ready, and Scorekeeper commits match scores
18. VAR server automatically moves to Live view
19. VAR server requests final match scores from Cheesy Arena and logs them for display in the VAR interface

## Pre-roll recording

The HyperDeck cannot record continuously into a rolling buffer, so recording ahead of the match
is done with a series of short recordings instead:

1. The arena reports that it is ready to start a match
2. VAR server starts recording, naming the clip after the match which is currently loaded
3. Every `preroll-segment-duration` seconds, VAR server stops the recording and immediately
   starts a new one. Whichever recording is in progress when the match starts becomes the clip
   for that match, so it contains at most one segment worth of footage from before the match
4. Loading a different match in Cheesy Arena restarts the recording under the new match's name
5. Pre-roll stops when the arena is no longer ready to start, when the connection to Cheesy Arena
   or the HyperDeck is lost, or when the VAR operator loads a match for review
6. Pre-roll is abandoned if no match has started after `preroll-max-duration` seconds, so that an
   arena which sits in the ready state does not fill the HyperDeck with unused recordings. It
   resumes once arena readiness changes again or a new match is loaded

Times recorded for review events are always relative to the start of the match, and the VAR server
converts them into positions within the clip using the amount of pre-roll footage it captured.
The discarded pre-roll segments are left on the HyperDeck and can be deleted from the device.

# Logged Match Review

1. VAR operator selects a prior match from the match list on the VAR tablet
2. VAR server directs the HyperDeck to go to Output mode and load the appropriate match clip
3. VAR server downloads detailed scoring data for the match from Cheesy Arena and displays it on the tablet
4. VAR operator selects review events from a list on the tablet, or selects a moment on the tablet's match timeline
5. VAR server warps the HyperDeck to the appropriate position in the clip

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