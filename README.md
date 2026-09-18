# frc-video-referee
Video Assisted Referee system for off-season FRC events. Designed to integrate with Blackmagic Hyperdeck devices for video recording and playback, and Cheesy Arena for match information.

## Prerequisites

You must install the following tools for development and locally building these tools:
* [uv](https://github.com/astral-sh/uv)
* [Bun](https://bun.sh/)

When running on Windows, these commands will install the dependencies:
```
winget install -e astral-sh.uv
winget install -e Oven-sh.Bun
```

The VAR server expects an instance of Cheesy Arena to be running. If you are on an actual field, the VAR server will locate it automatically as
long as you are connected to the field admin network. If not on a field, you need to download [the Cheesy Arena repo](https://github.com/Team254/cheesy-arena)
and run an instance of the arena server yourself.

The VAR server expects to connect to a Hyperdeck device. If you do not have a physical device available, you can use the script `tools/mock_hyperdeck.py` to
run a mock version of the hyperdeck API. To run it, use the following command:
```
uv run tools/mock_hyperdeck.py
```

## Workspace setup

After cloning this repository use the following command to download dependencies, build the frontend assets, and build the VAR server application.
This should be done each time you update the repository

```
uv sync
cd frontend
bun run build
```

## Running the main server

Launch the VAR server application with the following command

```
uv run frc-video-referee
```

See the `--help` output for a listing of all options. You can place any options into a TOML file
and pass that file using the `--config` argument. There is no difference between passing an option
through the command line and passing an option via a config TOML file

### Sample configuration file

Use this config file as a starting point for your event

```toml
[arena]
password = "abcd1234" # Replace with your Cheesy Arena admin password

[hyperdeck]
address = "hyperdeck.local" # Replace with the actual address of your hyperdeck

[db]
folder = "myevent.db" # Create a new DB folder for each event

[ui]
swap-red-blue = true # Swap red vs blue in the UI to match the VAR field view
```

Keys may be written in either `kebab-case` (matching the command line arguments) or
`snake_case` (matching the field names).

### Ranking point configuration

The panel shows each alliance's bonus ranking points and the ranking points it would
earn if the match ended now. Off-season events often change these values, so they are
configurable. Add only the values you are changing; anything you leave out keeps its
default.

```toml
# Ranking points for the match result
[ui.match-rp]
win = 2   # Default 3
tie = 1   # Default 1
loss = 0  # Default 0

# Each bonus ranking point can be renamed, re-thresholded, re-weighted, or turned off
[ui.energized-rp]
threshold = 80  # Fuel needed, default 100
value = 1       # Ranking points awarded, default 1

[ui.supercharged-rp]
enabled = false # Hide this RP entirely, default true
threshold = 360 # Fuel needed, default 360

[ui.traversal-rp]
label = "Climb" # Name shown in the panel, default "Traversal"
threshold = 40  # Tower points needed, default 50
value = 2       # Ranking points awarded, default 1
```

Any bonus ranking point can be switched off with `enabled = false`, including all of
them at once. A disabled RP is hidden from the panel and left out of the projected RP
total, and disabling both Fuel RPs also drops the Fuel goal readout, so the card shows
"90 scored" rather than a target the event does not award. The win/tie/loss RP is
always shown, since every match has an outcome.

Set the thresholds to match the equivalent settings in Cheesy Arena, which computes
whether each RP was actually earned. The panel always shows the arena's verdict as
the check mark and uses the configured threshold only for the progress number beside
it, so a threshold that does not match the arena's is visible rather than hidden. Note
that the arena also withholds every bonus RP from an alliance penalized under G206, so
a "met the threshold but no check mark" reading can be correct.

## Rebuilding after making local changes

Changes to python code will automatically be used on the next `uv run frc-video-referee` invocation.

Changes to the frontend svelte/html/ts/css code requires a manual rebuild using the following command:

```
cd frontend
bun run build
```

Frontend changes take effect immediately after building, and will be served the next time the user reloads the webpage.

## Building deploayable packages

This repository can be packaged into a python wheel for installation on other systems. The wheel installs the frc-video-referee application which can be run standalone, separate from this repo

Use this command to build a wheel:
```
uv build
```

Outputs will be placed in the `dist` folder

## Running a frontend dev server

When developing the frontend, you can run an independent dev server for the frontend app which reacts to code changes without reloading
and displays more detailed fatal error messages. To use it, launch the primary VAR server as normal and then run the following commands
in a separate terminal:

```
cd frontend
bun run dev
```

This server will only be useable on localhost. To make it accessible on other devices (for example, a tablet), pass the argument `--host` to bun.

If you have changed the port use by the VAR server, or the VAR server is running on a different host than the frontend dev server, you
can specify the address of the server through the env var `VITE_VAR_SERVER`.

Powershell example:
```
cd frontend
$env:VITE_VAR_SERVER="rho.local:8000"
bun run dev --host
```

Bash example:
```
cd frontend
VITE_VAR_SERVER="rho.local:8000" bun run dev --host
```