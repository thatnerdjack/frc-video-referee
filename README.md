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

[var]
preroll-enabled = true # Start recording before the match starts
preroll-segment-duration = 10.0 # Restart the pre-roll recording at this interval, in seconds
```

### Pre-roll recording

As soon as Cheesy Arena reports that the field is ready to start a match, the VAR server starts
recording on the HyperDeck. Because the HyperDeck cannot record continuously into a rolling
buffer, that recording is restarted every `preroll-segment-duration` seconds while waiting for
the match to begin. Whichever recording happens to be running when the match starts is kept as
the clip for that match, so it includes up to one segment worth of footage from before the match
started without leaving a long unused recording in front of it.

The recordings which get discarded this way are still left on the HyperDeck's disk, so they can
be cleaned up from the device between events. If no match starts within `preroll-max-duration`
seconds (10 minutes by default), pre-roll is abandoned until the arena readiness changes or a new
match is loaded. Set `preroll-enabled = false` to only record from the start of the match.

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