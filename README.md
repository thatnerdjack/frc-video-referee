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

The mock also runs an FTP server (on port 2121 by default) holding simulated clip files, so that
automatic storage management can be exercised without hardware. Pass `--disk-size` to shrink the
simulated media, and `POST /mock/storage` to consume space on demand.

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

[storage]
# Automatically reclaim space on the HyperDeck as it fills up over the event.
# Cleanup only ever runs during downtime between matches, never while a match is
# being recorded or reviewed, and never once the field is ready to start.
low_space_threshold = 2700 # Start cleaning below 45 minutes of remaining record time
target_record_time = 5400  # Keep cleaning until 90 minutes of headroom is restored
min_matches_retained = 8   # Never delete clips for the 8 most recent matches
# offload_path = "D:/var_archive" # Copy clips here before deleting them. Omit to just delete
# dry_run = true # Log what would be reclaimed without touching any files
```

### Storage management

Over a long event the HyperDeck's media fills with match recordings, and a full disk means
no recording at all. The VAR server watches the remaining record time the deck reports and,
once it drops below `low_space_threshold`, queues clips for removal.

The queue is only drained during downtime: the VAR server idle, the arena in pre-match, the
field not yet ready to start, and all of that having held for `quiet_period` seconds. If a
match becomes imminent, any transfer in progress is abandoned immediately and retried later.

Clips are removed over the deck's FTP server, since the HyperDeck control API has no way to
delete a clip. Orphan clips — files on the deck belonging to no recorded match — are always
reclaimed first, then the oldest matches whose scores the scorekeeper has already committed.
The most recent `min_matches_retained` matches, the match being recorded, and any match
loaded for review are never touched.

Set `offload_path` to archive clips to local storage before they are deleted; a clip is only
removed from the deck once its copy is verified complete. Running once with `dry_run = true`
is a good way to confirm the selection looks right before an event.

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