# Blackmagic HyperDeck Control API

This document describes the subset of BlackMagic's HyperDeck Control REST and Websocket APIs used for this project.

The complete API description can be found [here](https://documents.blackmagicdesign.com/DeveloperManuals/RESTAPIForHyperDeck.pdf)

All endpoints are underneath the path "/control/api/v1"

# Overall workflows

This section describes the expected owrkflow that the client will use

## Switching to live view

1. `PUT /transports/0/` with mode set to "InputPreview"

## Starting a recording

1. `POST /transports/0/record` to start a recording with a particular name
2. `GET /transports/0/clip` to read the metadata of the clip

## Stopping a recording

1. `POST /transports/0/stop` to stop the recording session
2. `GET /transports/0/clip` to refresh the final metadata for the clip

## Warping to a particular clip

1. Look up the clip in the list reported by the `/timelines/0` event
2. `PUT /transports/0/playback` with the following parameters:

```json
{
    "type": "Jog",
    "loop": false,
    "singleClip": true,
    "speed": 1.0,
    "position": <timelineIn value for the clip>
}
```

## Warping to a moment within a clip

Same as "Warping to a particular clip", but add an offset to the "position" field to hit the desired moment in the clip

# Transport status and control

## Transport mode

### PUT /transports/0

Description: Change the overall mode of the device

JSON Parameters:
* mode [string]: Transport mode. One of "InputPreview" or "Output"

Response: 204

### POST /transports/0/stop

Description: Stop a recording session

No Parameters

Response: 204

Changes the transport mode to InputPreview

### POST /transports/0/record

Description: Start a recording session

JSON Parameters:
* clipName [string]: Name to use for the clip. Automatically assigned by the server if not specified

Response: 204

Changes the transport mode to InputRecord

### PUT /transports/0/playback

Description: Set the state of playback

JSON Parameters:
* type [string]: Playback mode. One of "Play", "Jog", "Shuttle", or "Var"
* loop [boolean]: Whether playback loops
* singleClip [boolean]: Whether playback repeats the same clip or advances between clips
* speed [number]: Playback speed. Nominal speed is 1.0
* postition [integer]: Playback position on the timeline in frames. 0 is the first frame of the timeline

# Clip management

## Clip information

### GET /transports/0/clip

Description: Get information about the current clip

No Parameters

Response: 200 with JSON body:
* clip [object]
  * clipUniqueId [integer]: Integer ID for the clip
  * filePath [string]: Path to the clip file. Matches the "clipName" value used when recording
  * fileSize [integer]: Size of the clip file in bytes
  * codecFormat [object]
    * codec [string]: Codec format name
    * container [string]: Container format name
  * videoFormat [object]
    * name [string]: Overall name of the video format
    * frameRate [string]: Frame rate, represented as a decimal number
    * height [number]: Height of the video in pixels
    * width [number]: Width of the video in pixels
    * interlaced [boolean]: Whether the display format is interlaced
  * startTimecode [string]: The timecode of the start of the clip
  * durationTimecode [string]: The duration of the clip, formatted as a timecode
  * frameCount [integer]: The number of frames in the clip

### GET /clips

Description: Get information about all stored clips

No Parameters

Response: 200 with JSON body:
* clips [array]
  * Each member of the array is an object with the same contents as the "clip" object from GET /transports/0/clip

# Media and storage

## Media working set

### GET /control/api/v1/media/workingset

Description: Get information about the storage media available to the device

No Parameters

Response: 200 with JSON body matching the `/media/workingset` property described below

## Deleting clips

The control API has **no endpoint for deleting a clip**. The only remote file management
mechanism Blackmagic documents is the FTP server the deck exposes, so the VAR server's
automatic storage management (see `src/frc_video_referee/storage.py`) deletes and offloads
clips over FTP rather than through this API.

The FTP root contains one directory per media volume, named to match the `volume` field of
the active working set entry. A clip's `filePath` is relative to that directory, so a clip
on volume `sdcard` with a `filePath` of `Q01.mp4` lives at `/sdcard/Q01.mp4` over FTP.

# Websocket API

A websocket API is exposed for receiving real-time updates to state from the device. The client sends a request subscribing to a number of events,
and then the server sends events any time the data for a subscribed event changes.

The websocket can be connected at the "/control/api/v1/events/websocket" endpoint.

## Request messages from client

### Subscribe

Description: Sent by a client to request notifications on update to one or more properties

JSON body:
* data [object]
  * action [string]: Set to "subscribe"
  * properties [array]
    * Each member of the array is a string identifying what property to subscribe to
* type [string]: Set to "request"
* id [number]: Optional number that will be echoed back in the response

Example:

```json
{
    "data": {
        "action": "subscribe",
        "properties": [
            "/transports/0/record"
        ]
    },
    "type": "request"
}
```

### Unsubscribe

Description: Sent by a client to request that notifications be stopped for one or more properties

JSON body:
* data [object]
  * action [string]: Set to "unsubscribe"
  * properties [array]
    * Each member of the array is a string identifying what property to unsubscribe from
* type [string]: Set to "request"
* id [number]: Optional number that will be echoed back in the response

## Response messages from server

### Subscribe response

Description: Acknowledgement for a subscribe request

JSON body:
* data [object]
  * action [string]: Set to "subscribe"
  * properties [array]
    * Each member of the array is a string identifying what property to subscribe to
  * success [boolean]: Whether or not the request succeeded
  * values [object]: The current value for all properties subscribed in this request
* type [string]: Set to "response"
* id [number]: The ID that was provided in the subscribe request, if one was present

Example:

```json
{
    "data": {
        "action": "subscribe",
        "properties": [
            "/transports/0/record"
        ],
        "success": true,
        "values": {
            "/transports/0/record": {
                "recording": false
            }
        }
    },
    "type": "response"
}
```

### Unsubscribe response

Description: Acknowledgement for an unsubscribe request

JSON body:
* data [object]
  * action [string]: Set to "unsubscribe"
  * properties [array]
    * Each member of the array is a string identifying what property to subscribe to
  * success [boolean]: Whether or not the request succeeded
* type [string]: Set to "response"
* id [number]: The ID that was provided in the unsubscribe request, if one was present

### Event response

Description: Notification that a property has changed

JSON body:
* data [object]
  * action [string]: Set to "propertyValueChanged"
  * property [string]: Name of the property which has changed
  * value [object]: The new value of the property. Values are described in the "Property values" section
* type [string]: Set to "event"

Example:

```json
{
    "data": {
        "action": "propertyValueChanged",
        "property": "/transports/0/record",
        "value": {
            "recording": true
        }
    },
    "type": "event"
}
```

## Property values

### /timelines/0

Description: A table of the clips making up the timeline

JSON body:
* clips [array]
  * Each element is an object with the following body:
    * clipUniqueId [integer]: Unique identifier for the clip
    * frameCount [integer]: Duration of the clip in frames
    * durationTimecode [string]: Duration of the clip as a timecode
    * clipIn [integer]: The starting frame number within the clip
    * inTimecode [string]: The timecode of the first frame of the clip
    * timelineIn [integer]: The position in the timeline for the first frame of this clip
    * timelineInTimecode [string]: The timecode in the timeline for the first frame of this clip

### /media/workingset

Description: Information about the storage media available to the device

JSON body:
* size [integer]: Number of media devices in the working set
* workingset [array]
  * Each element is either null, or an object with the following body:
    * index [integer]: Index of the media device
    * activeDisk [boolean]: Whether this media is the one currently being recorded to
    * volume [string]: Volume name of the media. Matches the FTP directory holding its clips
    * deviceName [string]: Device name of the media
    * remainingRecordTime [integer]: Remaining record time on the media in seconds
    * totalSpace [integer]: Total space on the media in bytes
    * remainingSpace [integer]: Remaining space on the media in bytes
    * clipCount [integer]: Number of clips stored on the media

### /transports/0

Description: The current overall mode of the device

JSON body:
* mode [string]: Current transport mode. One of "InputPreview", "InputRecord", or "Output"

### /transports/0/playback

Description: Current configuration for playback

JSON body:
* type [string]: The current playback mode. One of "Play", "Jog", "Shuttle", or "Var"
* loop [boolean]: Whether playback loops continuously loops
* singleClip [boolean]: Whether playback stops at the end of the current clip
* speed [number]: The playback speed. 1.0 is normal speed
* position [integer]: Playback position on the timeline in units of frames

This value matches the value loaded to the PUT /transports/0/playback endpoint

### /transports/0/record

Description: Indication of whether a recording is in progress

JSON body:
* recording [boolean]: Whether or not recording is active. True iff transport mode is InputRecord

### /transports/0/clipIndex

Description: Indication of what clip is currently active

JSON body:
* clipIndex [number]: 0-based index of which clip in the timeline is active