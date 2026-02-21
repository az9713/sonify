# Sonify Architecture

This document describes the architecture of Sonify at multiple levels of abstraction, from the high-level system overview down to individual component internals. All diagrams are ASCII art and all code references point to actual source files.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture Diagram](#2-high-level-architecture-diagram)
3. [Component Breakdown](#3-component-breakdown)
4. [Data Flow Pipeline](#4-data-flow-pipeline)
5. [Communication Flows](#5-communication-flows)
6. [Server Internals](#6-server-internals)
7. [Lens System Architecture](#7-lens-system-architecture)
8. [Audio Bridge Architecture](#8-audio-bridge-architecture)
9. [Frontend Architecture](#9-frontend-architecture)
10. [WebSocket Protocol](#10-websocket-protocol)
11. [Audio Pipeline](#11-audio-pipeline)
12. [Startup and Shutdown Sequences](#12-startup-and-shutdown-sequences)
13. [State Management](#13-state-management)

---

## 1. System Overview

Sonify is a real-time data sonification platform that converts abstract data (weather, cardiac, mathematical, network) into music and synchronized visualizations. The application follows a client-server architecture where the Python server produces both audio and visualization data, streaming them to the browser over a single WebSocket connection.

The fundamental design principle is that **all mappings from data to sound are deterministic**. The generative audio engine (Lyria, ElevenLabs, or a mock synthesizer) is always downstream -- it receives control parameters but never decides what those parameters mean.

```
+-----------------------------------------------------------------------+
|                        SONIFY SYSTEM                                  |
|                                                                       |
|  +---------------------+        WebSocket        +------------------+ |
|  |   Python Server     | <----text + binary----> |  Browser Client  | |
|  |   (FastAPI)         |                         |  (Single Page)   | |
|  |                     |                         |                  | |
|  |  - Tick Loop        |    text: JSON viz data  |  - Canvas viz    | |
|  |  - Audio Loop       |    binary: PCM audio    |  - AudioWorklet  | |
|  |  - Lens System      |    client: JSON cmds    |  - UI Controls   | |
|  |  - Audio Bridges    |                         |                  | |
|  +---------------------+                         +------------------+ |
+-----------------------------------------------------------------------+
```

---

## 2. High-Level Architecture Diagram

This diagram shows every major component and how they connect:

```
+===================================================================+
|                         BROWSER                                   |
|                                                                   |
|  +------------------+   +------------------+   +---------------+  |
|  |  UI Controls     |   |  Canvas          |   |  AudioWorklet |  |
|  |  (Sidebar)       |   |  Renderer        |   |  Processor    |  |
|  |                  |   |                  |   |               |  |
|  |  Lens Buttons    |   |  Atmosphere      |   |  Ring Buffer  |  |
|  |  Param Sliders   |   |  Pulse           |   |  (5s @ 48kHz) |  |
|  |  Live Toggle     |   |  Lattice         |   |  PCM -> Float |  |
|  |  Play/Pause      |   |  Flow            |   |  -> Speakers  |  |
|  +--------+---------+   +--------+---------+   +------+--------+  |
|           |                      |                     ^           |
|           |   User Actions       | vizState JSON       | PCM bytes |
|           v                      |                     |           |
|  +--------+----------------------+---------------------+--------+  |
|  |              WebSocket Client (ws://host/ws)                 |  |
|  |   Sends: JSON commands   Receives: text frames, binary PCM  |  |
|  +------+------------------------------------------------------+  |
+=========|==========================================================+
          |
          |  Single WebSocket connection
          |  (text frames = JSON, binary frames = PCM audio)
          |
+=========|==========================================================+
|  PYTHON |SERVER (FastAPI, server.py)                               |
|  +------+------------------------------------------------------+  |
|  |              WebSocket Endpoint (/ws)                        |  |
|  |   Accepts: client JSON    Broadcasts: text + binary frames   |  |
|  +------+----+----+--+------+---------+------------------------+  |
|         |    |    |  |      |         |                           |
|         |    |    |  |      |         |                           |
|  +------+--+ | +--+--+--+  |  +------+------+                    |
|  | Tick    | | | Audio  |  |  | WS Message  |                    |
|  | Loop    | | | Loop   |  |  | Handler     |                    |
|  | (async) | | | (async)|  |  | (per client)|                    |
|  +-+-------+ | +--+-----+  |  +------+------+                    |
|    |         |    |         |         |                            |
|    v         |    v         |         v                            |
|  +-+---------+--+ +--------+-+  +----+-----+                      |
|  | Active Lens  | | Audio    |  | Global   |                      |
|  |              | | Bridge   |  | State    |                      |
|  | .tick(t)     | |          |  |          |                      |
|  | .map(data)   | | .update()|  | lens     |                      |
|  | .viz_state() | | .get_    |  | paused   |                      |
|  +------+-------+ | chunk() |  | clients  |                      |
|         |         +----+-----+  +----------+                      |
|         v              |                                           |
|  +------+-------+      |  +----------------------------------+    |
|  | Simulator    |      +->| LyriaBridge / ElevenLabsBridge / |    |
|  | (per lens)   |         | MockAudioGenerator               |    |
|  +--------------+         +----------------------------------+    |
+===================================================================+
```

---

## 3. Component Breakdown

### 3.1 Server-Side Components

| Component | File | Responsibility |
|-----------|------|---------------|
| FastAPI Application | `server.py` | HTTP server, WebSocket endpoint, lifecycle management |
| Tick Loop | `server.py:129-180` | Runs active lens at its tick rate, broadcasts viz + controls |
| Audio Loop | `server.py:183-203` | Pulls PCM chunks from bridge, broadcasts binary frames |
| WebSocket Handler | `server.py:228-291` | Accepts client connections, processes commands |
| Lens Base | `lenses/base.py` | Abstract Lens class, ControlState dataclass, EMA smoothing |
| AtmosphereLens | `lenses/atmosphere.py` | Weather-to-music mapping |
| PulseLens | `lenses/pulse.py` | Cardiac-to-music mapping |
| LatticeLens | `lenses/lattice.py` | Math-to-music mapping (Lorenz, logistic, sine) |
| FlowLens | `lenses/flow.py` | Network-traffic-to-music mapping |
| LyriaBridge | `lyria_bridge.py` | Google Lyria RealTime API wrapper |
| ElevenLabsBridge | `elevenlabs_bridge.py` | ElevenLabs Music API wrapper |
| MockAudioGenerator | `lyria_bridge.py:16-163` | Additive synth fallback |
| WeatherSimulator | `data_sources/simulators.py:10-53` | Layered sinusoid weather generator |
| CardiacSimulator | `data_sources/simulators.py:56-124` | ECG waveform + HRV simulator |
| MathSimulator | `data_sources/simulators.py:169-257` | Lorenz, logistic map, sine superposition |
| NetworkSimulator | `data_sources/simulators.py:260-343` | Poisson-process traffic generator |
| LiveWeatherFetcher | `data_sources/live_weather.py` | Open-Meteo API client with cache |

### 3.2 Client-Side Components

| Component | File | Responsibility |
|-----------|------|---------------|
| Single Page App | `static/index.html` | All UI, rendering, WebSocket client in one file |
| AudioWorklet Processor | `static/worklet.js` | PCM ring buffer, real-time audio playback |

---

## 4. Data Flow Pipeline

Every tick follows the same pipeline, regardless of which lens or audio backend is active:

```
                    THE SONIFY DATA PIPELINE
                    (repeats every tick)

     +------------------+
     | Simulator / User |   Raw domain data (weather, cardiac, etc.)
     | Slider Values    |   e.g., {wind_speed: 15, temperature: 22, ...}
     +--------+---------+
              |
              v
     +--------+---------+
     | Lens.tick(t)      |   Generates domain data dict
     +--------+---------+
              |
              v
     +--------+---------+
     | Lens.map(data)    |   Deterministic transfer functions
     |                   |   e.g., bpm = 70 + wind * 3.67
     |   + EMA smoothing |   All values pass through _ema()
     +--------+---------+
              |
              v
     +--------+---------+
     | ControlState      |   9 fields: bpm, density, brightness,
     | .clamped()        |   guidance, scale, prompts, mute_bass,
     |                   |   mute_drums, temperature
     +---+--------+------+
         |        |
         |        v
         |   +----+----------+
         |   | Lens.viz_state |   JSON for Canvas renderer
         |   | (data)         |   e.g., particle positions, ECG trace
         |   +----+-----------+
         |        |
         v        v
     +---+--------+------+     +-------------------+
     | Bridge.update      |     | broadcast_text()  |
     | (controls)          |     | {viz, controls,   |
     +--------+------------+     |  lens, backend}   |
              |                  +--------+----------+
              v                           |
     +--------+------------+              |
     | Bridge.get_audio    |              |
     | _chunk()            |              |
     +--------+------------+              |
              |                           |
              v                           v
     +--------+------------+    +---------+--------+
     | broadcast_binary()  |    | WebSocket Text   |
     | (PCM bytes)         |    | Frame            |
     +--------+------------+    +---------+--------+
              |                           |
              +-------------+-------------+
                            |
                            v
                  +---------+--------+
                  | Browser receives |
                  | text -> Canvas   |
                  | binary -> Audio  |
                  +------------------+
```

### 4.1 Detailed Per-Tick Sequence

```
Time  Action                                    File:Line
----  ------                                    ---------
T+0   tick_loop wakes up                        server.py:134
T+1   active_lens.update(t) called              lenses/base.py:116-121
T+2     lens.tick(t) generates domain data      e.g., atmosphere.py:64-75
T+3     lens.map(data) computes ControlState    e.g., atmosphere.py:77-122
T+4       _ema() smooths each dimension         lenses/base.py:91-99
T+5       .clamped() enforces valid ranges      lenses/base.py:26-38
T+6     lens.viz_state(data) produces viz JSON  e.g., atmosphere.py:124-155
T+7   bridge.update(controls) sends to audio    server.py:154
T+8     (LyriaBridge) .diff() computes changes  lyria_bridge.py:241-257
T+9     (ElevenLabsBridge) builds text prompt    elevenlabs_bridge.py:132-188
T+10    (Mock) updates synth parameters          lyria_bridge.py:86-122
T+11  broadcast_text({viz, controls, lens})      server.py:169-175
T+12  asyncio.sleep(1/tick_hz)                   server.py:180

Concurrently:
T+?   audio_loop wakes up every ~50ms            server.py:186
T+?   bridge.get_audio_chunk() returns PCM       server.py:192
T+?   broadcast_binary(chunk) sends to clients   server.py:194
```

---

## 5. Communication Flows

### 5.1 Client-Server Communication Overview

```
+--------------------+                         +--------------------+
|  BROWSER CLIENT    |                         |  PYTHON SERVER     |
+--------------------+                         +--------------------+
|                    |                         |                    |
|  User clicks       |  {"type":"switch_lens", |                    |
|  "Pulse" button ---+-->  "lens":"pulse"}     |  Switches lens,    |
|                    |                         |  resets bridge     |
|                    |                         |                    |
|  User moves        |  {"type":"set_param",   |                    |
|  slider        ----+-->  "name":"wind_speed", |  Updates lens     |
|                    |     "value":25.0}       |  parameter         |
|                    |                         |                    |
|  User clicks       |  {"type":"pause"}       |                    |
|  Pause         ----+-->                      |  Stops tick/audio  |
|                    |                         |  loops             |
|                    |                         |                    |
|  User toggles      |  {"type":"toggle_live", |                    |
|  Live Weather  ----+-->  "enabled":true}     |  Enables live      |
|                    |                         |  weather fetching  |
|                    |                         |                    |
|                    |  <---  text frame  ---  |  Tick loop sends   |
|  Updates Canvas,   |  {"viz":{...},          |  viz + controls    |
|  control bars,     |   "controls":{...},     |  every tick        |
|  prompts display   |   "lens":"atmosphere",  |  (2-10 Hz)         |
|                    |   "backend":"lyria"}    |                    |
|                    |                         |                    |
|                    |  <--- binary frame ---  |  Audio loop sends  |
|  AudioWorklet      |  [9600 bytes PCM]       |  PCM chunks        |
|  processes PCM     |                         |  every ~50ms       |
|                    |                         |  (20 chunks/sec)   |
+--------------------+                         +--------------------+
```

### 5.2 Initial Connection Handshake

```
CLIENT                                          SERVER
  |                                               |
  |  WebSocket CONNECT /ws                        |
  |---------------------------------------------->|
  |                                               |
  |  WebSocket ACCEPT                             |
  |<----------------------------------------------|
  |                                               |
  |  text frame (init message)                    |
  |  {"type": "init",                             |
  |   "lens": "atmosphere",                       |
  |   "lenses": {                                 |
  |     "atmosphere": {desc, parameters},         |
  |     "pulse": {desc, parameters},              |
  |     "lattice": {desc, parameters},            |
  |     "flow": {desc, parameters}                |
  |   },                                          |
  |   "is_mock": false,                           |
  |   "backend": "lyria",                         |
  |   "paused": false}                            |
  |<----------------------------------------------|
  |                                               |
  |  Client builds UI from init data              |
  |  (lens buttons, parameter sliders)            |
  |                                               |
  |  text frame (tick data)                       |
  |  {"viz": {...}, "controls": {...},            |
  |   "lens": "atmosphere", "backend": "lyria"}   |
  |<----------------------------------------------| (repeats at tick_hz)
  |                                               |
  |  binary frame (PCM audio)                     |
  |  [9600 bytes: 2400 stereo frames @ 48kHz]     |
  |<----------------------------------------------| (repeats ~every 50ms)
```

### 5.3 Lens Switching Flow

```
CLIENT                    SERVER                    AUDIO BRIDGE
  |                         |                           |
  |  {"type":"switch_lens", |                           |
  |   "lens":"lattice"}     |                           |
  |------------------------>|                           |
  |                         |  active_lens = LatticeLens()
  |                         |  bridge.reset()           |
  |                         |-------------------------->|
  |                         |                           |
  |                         |  (Lyria) session.reset_context()
  |                         |  (ElevenLabs) drain queue, bump gen_id
  |                         |  (Mock) clear prev controls
  |                         |                           |
  |                         |  Next tick runs LatticeLens
  |                         |  tick_loop sends new viz  |
  |  {"viz": {type:"lattice",...},                      |
  |   "lens": "lattice",   |                           |
  |   "controls": {...}}   |                           |
  |<------------------------|                           |
  |                         |                           |
  |  Canvas switches to     |                           |
  |  lattice renderer       |                           |
```

### 5.4 Audio Data Flow Through Bridge Selection

```
                    +-----------------------+
                    |    create_bridge()    |
                    |    (server.py:29)     |
                    +-----------+-----------+
                                |
               GOOGLE_API_KEY?  |  ELEVENLABS_API_KEY?
              +--------+--------+--------+
              |  Yes   |                 |  Yes
              v        |  No             v
     +--------+------+ |       +---------+-------+
     | LyriaBridge   | |       | ElevenLabsBridge|
     +--------+------+ |       +---------+-------+
              |        |                 |
              v        v                 v
     +---------+------+        +---------+-------+
     | bridge.connect |        | bridge.connect  |
     +--------+-------+        +---------+-------+
              |                          |
       Success?                    Success?
      /        \                  /        \
    Yes         No              Yes         No
     |           |               |           |
     v           v               v           v
  Lyria      +---+---+       ElevenLabs  +---+---+
  Active     | Has   |       Active      | Mock  |
             | 11Labs|                   | Audio |
             | key?  |                   +-------+
             +---+---+
            /         \
          Yes          No
           |            |
           v            v
     ElevenLabs      Mock
     Fallback        Audio
```

### 5.5 Tick Loop and Audio Loop Concurrency

```
                         EVENT LOOP
              +----------------------------+
              |                            |
              v                            v
     +--------+--------+        +---------+--------+
     |   tick_loop()    |        |   audio_loop()   |
     |   (async task)   |        |   (async task)   |
     +--------+---------+        +---------+--------+
              |                            |
              | Every 1/tick_hz seconds    | Every ~50ms
              | (200ms for 5Hz lens)       |
              |                            |
              v                            v
     +--------+---------+        +---------+--------+
     | lens.update(t)   |        | bridge.get_      |
     | -> (controls,viz)|        | audio_chunk()    |
     +--------+---------+        +---------+--------+
              |                            |
              v                            v
     +--------+---------+        +---------+--------+
     | bridge.update    |        | broadcast_binary |
     | (controls)       |        | (chunk)          |
     +--------+---------+        +---------+--------+
              |                            |
              v                            |
     +--------+---------+                  |
     | broadcast_text   |                  |
     | ({viz,controls}) |                  |
     +------------------+                  |
              |                            |
              +---------> Both broadcast to all connected WebSocket clients
```

---

## 6. Server Internals

### 6.1 Server Module Structure

File: `server.py`

```
server.py
|
+-- load_dotenv()                      # Load .env file at import time
+-- create_bridge()                    # Factory: select audio backend
+-- lifespan(app)                      # Async context manager for startup/shutdown
+-- app = FastAPI(...)                 # FastAPI application instance
|
+-- Global State:
|   +-- bridge                         # Audio bridge instance
|   +-- active_lens                    # Current Lens instance
|   +-- active_lens_name               # String name of active lens
|   +-- connected_clients              # List of WebSocket connections
|   +-- weather_fetcher                # LiveWeatherFetcher instance
|   +-- tick_task / audio_task         # asyncio.Task references
|   +-- use_live_weather               # Boolean toggle
|   +-- paused                         # Boolean toggle
|
+-- Helper Functions:
|   +-- get_backend_name()             # "lyria" | "elevenlabs" | "mock"
|   +-- create_lens(name)              # Instantiate lens by name
|   +-- broadcast_text(data)           # Send JSON to all clients
|   +-- broadcast_binary(data)         # Send PCM to all clients
|
+-- Async Loops:
|   +-- tick_loop()                    # Main data processing loop
|   +-- audio_loop()                   # Audio chunk streaming loop
|
+-- Routes:
|   +-- GET /                          # Serves static/index.html
|   +-- GET /api/lenses                # Returns lens metadata JSON
|   +-- WS  /ws                        # WebSocket endpoint
|
+-- main()                             # Entry point (uvicorn runner)
```

### 6.2 Lifecycle

```
  python server.py
        |
        v
  load_dotenv()           # Read .env file
  create_bridge()         # Select backend (no connection yet)
        |
        v
  uvicorn starts FastAPI
        |
        v
  lifespan() __aenter__
        |
        +-- create_lens("atmosphere")
        +-- bridge.connect()
        +-- (cascade check: Lyria fell back to mock + ElevenLabs key exists?)
        |       +-- Yes: switch to ElevenLabsBridge, connect again
        +-- Start tick_loop() as asyncio.Task
        +-- Start audio_loop() as asyncio.Task
        +-- Print server URL and audio mode
        |
        v
  Server running (accepting WebSocket connections)
        |
        v
  lifespan() __aexit__ (on shutdown)
        |
        +-- Cancel tick_task
        +-- Cancel audio_task
        +-- bridge.disconnect()
```

---

## 7. Lens System Architecture

### 7.1 Lens Inheritance Hierarchy

```
              +------------------+
              |    Lens (ABC)    |
              |    base.py       |
              +--------+---------+
              | name             |
              | description      |
              | tick_hz          |
              | parameters       |
              | _params          |
              | _ema_state       |
              | _ema_alpha       |
              +------------------+
              | set_param()      |
              | get_params()     |
              | _ema()           |
              | update()         |
              | tick()    (ABC)  |
              | map()     (ABC)  |
              | viz_state()(ABC) |
              +--------+---------+
                       |
          +------------+------------+------------+
          |            |            |            |
+---------+--+ +-------+----+ +----+-------+ +--+---------+
|Atmosphere  | |  Pulse     | |  Lattice   | |  Flow      |
|Lens        | |  Lens      | |  Lens      | |  Lens      |
|            | |            | |            | |            |
| tick_hz=4  | | tick_hz=10 | | tick_hz=8  | | tick_hz=5  |
|            | |            | |            | |            |
| Weather    | | Cardiac    | | Lorenz/    | | Network    |
| Simulator  | | Model      | | Logistic/  | | Poisson    |
| or Live    | | (built-in) | | Sine       | | Process    |
| Weather    | |            | | Simulator  | | (built-in) |
+------------+ +------------+ +------------+ +------------+
```

### 7.2 ControlState Dataclass

File: `lenses/base.py:9-61`

```
ControlState
+---------------------------+------------------+-------------------+
| Field         | Type      | Valid Range       | Default           |
+---------------+-----------+-------------------+-------------------+
| bpm           | int       | 60 - 200          | 120               |
| density       | float     | 0.0 - 1.0         | 0.5               |
| brightness    | float     | 0.0 - 1.0         | 0.5               |
| guidance      | float     | 0.0 - 6.0         | 4.0               |
| scale         | str       | Scale enum string  | SCALE_UNSPECIFIED |
| prompts       | list[dict]| [{text, weight}]   | [{"text":"ambient","weight":1.0}] |
| mute_bass     | bool      | True/False         | False             |
| mute_drums    | bool      | True/False         | False             |
| temperature   | float     | 0.0 - 3.0         | 1.1               |
+---------------+-----------+-------------------+-------------------+

Methods:
  .clamped()  -> ControlState   # Enforce valid ranges
  .diff(other) -> dict          # Dead-zone comparison for change detection
```

### 7.3 EMA Smoothing Flow

```
Raw Value (e.g., wind=25.5)
        |
        v
   _ema("bpm", 70 + 25.5 * 3.67)
        |
        v
   y[n] = alpha * x[n] + (1 - alpha) * y[n-1]
        |  alpha = 0.15
        |  Cutoff frequency ~0.13 Hz at 5 Hz tick rate
        v
   Smoothed Value (gradually approaches target over ~7.7 seconds)
        |
        v
   ControlState field (e.g., bpm=163)
        |
        v
   .clamped() -> bpm = max(60, min(200, 163)) = 163
```

### 7.4 Lens Parameter -> ControlState Mapping (AtmosphereLens example)

```
User Slider              tick()                    map()
                         (domain data)             (ControlState)

wind_speed=15 ---------> {wind_speed: 15}
                              |
                              +-----------> bpm = 70 + 15 * 3.67 = 125
                              |             (after EMA smoothing)
temperature=22 --------> {temperature: 22}
                              |
                              +-----------> brightness = (22+10)/50 = 0.64
                              |
humidity=60 -----------> {humidity: 60}
                              |
                              +-----------> density = 60/100 = 0.60
                              |
rain=0.4 --------------> {rain_probability: 0.4}
                              |
                              +-----------> guidance = 3.0 + 0.4*2.0 = 3.8
                              +-----------> prompts += "Piano arpeggios" @ 0.4
                              |
pressure=1013 ---------> {pressure: 1013}
                              |
                              +-----------> (visualization only)
```

---

## 8. Audio Bridge Architecture

### 8.1 Bridge Interface (shared by all three backends)

```
AudioBridge (implicit interface -- no formal ABC)
+-----------------------------------------------------+
| connect()          -> None    # Establish connection  |
| update(controls)   -> None    # Send ControlState     |
| get_audio_chunk()  -> bytes   # Return PCM chunk      |
| reset()            -> None    # Reset on lens switch   |
| disconnect()       -> None    # Clean shutdown         |
| is_mock            -> bool    # Property: is fallback? |
+-----------------------------------------------------+
```

### 8.2 LyriaBridge Internals

File: `lyria_bridge.py:166-364`

```
LyriaBridge
+----------------------------------------------------------+
| _api_key         # GOOGLE_API_KEY from env                |
| _use_mock        # True if no API key or connection failed|
| _session         # Lyria RealTime session object          |
| _client          # google.genai Client                    |
| _prev_controls   # Previous ControlState (for diffing)   |
| _mock            # MockAudioGenerator (fallback)          |
| _audio_queue     # asyncio.Queue[bytes] (max 100)        |
| _receive_task    # Background task for receiving audio    |
+----------------------------------------------------------+

Control Update Flow:
  update(controls)
       |
       +-- Mock mode? --> mock.update_from_controls(controls)
       |
       +-- First update? --> _send_full_state(controls)
       |                          |
       |                          +-- session.set_weighted_prompts(...)
       |                          +-- session.set_music_generation_config(...)
       |                          +-- session.play()
       |
       +-- Subsequent? --> controls.diff(prev_controls)
                               |
                               +-- No changes? --> skip
                               +-- Changes? --> _send_changes(controls, changes)
                                                    |
                                                    +-- prompts changed? --> set_weighted_prompts
                                                    +-- config changed?  --> set_music_generation_config
                                                    +-- bpm/scale changed? --> reset_context()

Audio Receive Flow (background task):
  _receive_audio()
       |
       +-- async for message in session.receive():
               |
               +-- Extract audio_chunks from server_content
               +-- Decode base64 if needed
               +-- Put into _audio_queue (drop oldest on overflow)
```

### 8.3 ElevenLabsBridge Internals

File: `elevenlabs_bridge.py`

```
ElevenLabsBridge
+----------------------------------------------------------+
| _api_key           # ELEVENLABS_API_KEY from env          |
| _use_mock          # True if no key or init failed        |
| _client            # ElevenLabs client                    |
| _audio_queue       # asyncio.Queue[bytes] (max 200)       |
| _current_prompt    # Latest prompt from update()          |
| _committed_prompt  # Prompt currently generating/playing  |
| _pending_prompt    # Waiting for debounce                 |
| _last_prompt_change# Timestamp of last prompt change      |
| _gen_id            # Monotonic counter for stale detection |
| _generation_task   # Background asyncio.Task              |
+----------------------------------------------------------+

Prompt Construction Flow:
  update(controls)
       |
       v
  _build_prompt(controls)
       |
       +-- Sort prompts by weight descending
       +-- Add tempo descriptor (bpm < 80: "slow tempo", etc.)
       +-- Add arrangement descriptor (density < 0.3: "sparse", etc.)
       +-- Add tonal descriptor (brightness < 0.3: "dark", etc.)
       +-- Add scale/mood text
       +-- Add mute flags ("no bass", "no drums")
       +-- Add temperature descriptor
       +-- Append "instrumental"
       +-- Join with commas
       |
       v
  "Ethereal Ambience, cold, sustained chords, slow tempo,
   sparse minimal arrangement, dark muted tones, instrumental"

Generation Loop:
  _generation_loop()     (continuous background task)
       |
       +-- Wait for any prompt to exist
       |
       +-- First prompt? Commit immediately (no debounce)
       |
       +-- Generate segment with committed prompt:
       |     |
       |     +-- _generate_segment(prompt, gen_id)
       |           |
       |           +-- _call_api_sync(prompt)  # In thread executor
       |           |     |
       |           |     +-- client.music.stream(prompt, 30000ms, pcm_48000)
       |           |     +-- Collect all bytes
       |           |
       |           +-- Check gen_id (discard if stale from reset())
       |           +-- Convert mono to stereo if needed
       |           +-- Split into 9600-byte chunks
       |           +-- Queue ALL chunks (never abort mid-segment)
       |
       +-- Check for debounced prompt change
       |     |
       |     +-- _should_regenerate()
       |           |
       |           +-- pending_prompt != committed_prompt?
       |           +-- elapsed >= 2.0 seconds since last change?
       |
       +-- If new prompt ready: commit and loop
       +-- If no change: wait, then generate another segment
```

### 8.4 MockAudioGenerator Internals

File: `lyria_bridge.py:16-163`

```
MockAudioGenerator
+----------------------------------------------------------+
| _phase          # Waveform phase accumulator              |
| _freq           # Current frequency (glides to target)    |
| _target_freq    # Target frequency from brightness        |
| _volume         # Master volume (0.3)                     |
| _harmonics      # List of (multiplier, amplitude) pairs   |
| _lfo_phase      # LFO phase accumulator                   |
| _lfo_rate       # LFO rate from BPM                       |
| _lfo_depth      # LFO depth from guidance                 |
| _noise_level    # Noise amplitude from temperature        |
| _mute_drums     # LFO bypass flag                         |
+----------------------------------------------------------+

ControlState -> Synth Parameters:
  brightness  --> base_freq = 110 + brightness * 330
                  --> _quantize_to_scale(freq, scale_notes)
                  --> _target_freq
  density     --> n_harmonics = 1 + int(density * 5)
                  --> _harmonics = [(k, 0.3/k) for k in 1..n]
  mute_bass   --> remove harmonics k=1, k=2 (if 3+ present)
  bpm         --> _lfo_rate = bpm / 60.0
  guidance    --> _lfo_depth = min(1.0, guidance / 6.0)
  temperature --> _noise_level = temperature / 3.0 * 0.15
  mute_drums  --> _mute_drums = True/False

Audio Generation (generate_chunk):
  For each of 2400 samples:
    1. Glide frequency toward target
    2. Compute LFO value (or flat 1.0 if mute_drums)
    3. Sum harmonics: sum(amp * sin(phase * mult))
    4. Add Gaussian noise (temperature)
    5. Multiply by volume * LFO
    6. Accumulate phase
    7. Convert to 16-bit int, duplicate for stereo
    8. Pack as little-endian bytes
```

---

## 9. Frontend Architecture

### 9.1 Single Page Application Structure

File: `static/index.html`

```
index.html
|
+-- <style> CSS
|     +-- CSS custom properties (--bg, --accent, etc.)
|     +-- Layout: header, sidebar, canvas-wrap
|     +-- Component styles: lens-btn, param-group, control-bar, etc.
|
+-- <body> HTML
|     +-- <header>
|     |     +-- "Sonify" title
|     |     +-- Play/Pause button (#play-pause-btn)
|     |     +-- Status badge (#status-badge)
|     |
|     +-- <div class="main">
|           +-- <aside class="sidebar">
|           |     +-- Lens buttons section (#lens-buttons)
|           |     +-- Parameters section (#param-sliders)
|           |     +-- Live Weather toggle (#live-toggle)
|           |     +-- Lyria Controls readout (#controls-readout)
|           |     +-- Active Prompts display (#prompts-display)
|           |
|           +-- <div class="canvas-wrap">
|                 +-- <canvas id="viz-canvas">
|                 +-- <div id="data-overlay">
|                 +-- <div id="start-overlay">
|
+-- <script> JavaScript
      +-- State variables (ws, audioCtx, vizState, etc.)
      +-- initAudio()          # AudioContext + WorkletNode setup
      +-- connectWS()          # WebSocket connection + handlers
      +-- buildLensButtons()   # Create lens selector UI
      +-- buildParamSliders()  # Create parameter slider UI
      +-- updateControlsReadout()  # Update control bars + prompts
      +-- renderAtmosphere()   # Canvas renderer for weather
      +-- renderPulse()        # Canvas renderer for cardiac
      +-- renderLattice()      # Canvas renderer for math
      +-- renderFlow()         # Canvas renderer for network
      +-- animate()            # requestAnimationFrame loop
      +-- Event listeners      # start-btn, play-pause, live-toggle
```

### 9.2 Browser Audio Pipeline

```
  WebSocket                                Web Audio API
  binary frame          AudioWorklet        Speakers
                        Processor
+----------+      +-------------------+      +--------+
| 9600     |      | PCMPlayerProcessor|      |        |
| bytes    | ---> |                   | ---> | Audio  |
| (PCM)    |      | Ring Buffer       |      | Output |
+----------+      | (5s capacity)     |      |        |
                  |                   |      +--------+
  port.post       | writePos          |
  Message()       | readPos           |      process() called
                  | samplesAvailable  |      at 48kHz by browser
                  +-------------------+      (128 frames per call)

Detail:
  1. WebSocket receives ArrayBuffer (binary frame)
  2. onmessage posts buffer to WorkletNode port
  3. Worklet's _writeFromPCM16() converts int16 -> float32
  4. Writes to ring buffer at writePos
  5. process() reads from ring buffer at readPos
  6. Deinterleaves stereo (L, R, L, R) to separate channels
  7. If buffer underflows: outputs silence (no artifacts)
```

---

## 10. WebSocket Protocol

### 10.1 Message Types

```
CLIENT -> SERVER:
+------------------------------------------------------+
| Type           | Fields                               |
|----------------|--------------------------------------|
| switch_lens    | {type, lens: string}                 |
| set_param      | {type, name: string, value: number}  |
| pause          | {type}                               |
| play           | {type}                               |
| toggle_live    | {type, enabled: boolean}             |
+------------------------------------------------------+

SERVER -> CLIENT:
+------------------------------------------------------+
| Type / Frame   | Content                              |
|----------------|--------------------------------------|
| init (text)    | {type, lens, lenses, is_mock,        |
|                |  backend, paused}                    |
| paused (text)  | {type, paused: boolean}              |
| tick (text)    | {viz, controls, lens, is_mock,       |
|                |  backend}                            |
| audio (binary) | Raw PCM bytes (9600 bytes = 50ms)    |
+------------------------------------------------------+
```

---

## 11. Audio Pipeline

### 11.1 PCM Format Specification

```
+---------------------------------------------+
| Audio Format: Linear PCM                     |
|---------------------------------------------|
| Bit depth:     16-bit signed integer         |
| Byte order:    Little-endian                 |
| Sample rate:   48,000 Hz                     |
| Channels:      2 (interleaved stereo)        |
| Frame layout:  [L_int16][R_int16][L][R]...   |
| Chunk size:    2400 frames                    |
|   = 2400 * 2 channels * 2 bytes              |
|   = 9600 bytes per chunk                     |
|   = 50 milliseconds of audio                 |
| Data rate:     9600 * 20 = 192 KB/s          |
+---------------------------------------------+
```

### 11.2 End-to-End Audio Latency

```
Audio Source          Network        Browser Processing

Bridge generates      WebSocket      Worklet receives
PCM chunk             transmit       and buffers
(~0ms for mock)       (~1-5ms LAN)   (~0ms write)
(~50ms for Lyria)                    |
(~5-15s first segment               Ring buffer
 for ElevenLabs)                     provides ~50ms
                                     of jitter
                                     absorption
                                     |
                                     process() reads
                                     at 48kHz
                                     (128 samples
                                     = 2.67ms)
                                     |
                                     Audio output

Total latency (steady state):
  Mock:        ~55-60ms  (generation + network + buffer)
  Lyria:       ~100-150ms (streaming + network + buffer)
  ElevenLabs:  ~50-60ms once buffered (segment pre-generated)
               ~5-15s for first segment after prompt change
```

---

## 12. Startup and Shutdown Sequences

### 12.1 Full Startup Sequence

```
1.  User runs: python server.py
2.  Python loads server.py
3.  load_dotenv() reads .env file
4.  create_bridge() checks env vars:
      GOOGLE_API_KEY set?  -> LyriaBridge()
      ELEVENLABS_API_KEY?  -> ElevenLabsBridge()
      Neither?             -> LyriaBridge() (will use mock internally)
5.  uvicorn starts, calls lifespan() context manager
6.  lifespan __aenter__:
      a. create_lens("atmosphere") -> AtmosphereLens instance
      b. bridge.connect()
           - Lyria: tries google.genai connection to lyria-realtime-exp
           - ElevenLabs: instantiates ElevenLabs client
           - Mock: just sets _connected = True
      c. Cascade check: if Lyria fell back to mock AND ELEVENLABS_API_KEY set:
           - disconnect Lyria bridge
           - create ElevenLabsBridge
           - connect it
      d. Start tick_loop() as asyncio.Task
      e. Start audio_loop() as asyncio.Task
      f. Print "Sonify running at http://localhost:8000"
      g. Print "Audio mode: [Lyria RealTime | ElevenLabs Music | Mock]"
7.  Server accepts HTTP requests and WebSocket connections
8.  User opens browser to http://localhost:8000
9.  Browser loads index.html (GET /)
10. User clicks "Start Experience"
      - initAudio() creates AudioContext + AudioWorkletNode
      - connectWS() opens WebSocket to /ws
      - animate() starts requestAnimationFrame loop
11. Server sends init message with all lens info
12. Client builds UI (lens buttons, sliders)
13. Tick loop begins broadcasting viz + controls
14. Audio loop begins broadcasting PCM chunks
```

### 12.2 Shutdown Sequence

```
1.  Server receives SIGINT (Ctrl+C) or SIGTERM
2.  uvicorn calls lifespan __aexit__:
      a. tick_task.cancel()
      b. audio_task.cancel()
      c. bridge.disconnect()
           - Lyria: cancel receive task, session.stop()
           - ElevenLabs: set stop event, cancel generation task
           - Mock: no-op
3.  uvicorn closes all WebSocket connections
4.  Process exits
```

---

## 13. State Management

### 13.1 Server Global State

```
+--------------------+--------+------------------------------------------+
| Variable           | Type   | Modified By                               |
+--------------------+--------+------------------------------------------+
| bridge             | Bridge | create_bridge(), lifespan cascade         |
| active_lens        | Lens   | lifespan, WS switch_lens handler         |
| active_lens_name   | str    | lifespan, WS switch_lens handler         |
| connected_clients  | list   | WS connect/disconnect handlers           |
| weather_fetcher    | Fetcher| Created once at module load               |
| tick_task           | Task   | lifespan start/stop                      |
| audio_task          | Task   | lifespan start/stop                      |
| use_live_weather   | bool   | WS toggle_live handler                   |
| paused             | bool   | WS pause/play handlers                   |
+--------------------+--------+------------------------------------------+
```

### 13.2 Per-Lens State

```
Lens Instance State:
  _params          dict[str, float]    Slider values (set by set_param())
  _ema_state       dict[str, float]    EMA filter state per dimension
  _ema_alpha       float               Smoothing factor (0.15)

Lens-specific State:
  AtmosphereLens:  _live_data          Live weather data or None
  PulseLens:       _ecg_history        ECG waveform history (300 points)
  LatticeLens:     _sim, _lorenz       MathSimulator, LorenzAttractor instances
  FlowLens:        _node_positions     Network graph node positions
                   _node_activity      Per-node activity levels
```

### 13.3 Client State

```
JavaScript State:
  ws               WebSocket           Connection to server
  audioCtx         AudioContext         Web Audio API context
  workletNode      AudioWorkletNode     PCM processor
  currentLens      string               Active lens name
  vizState         object               Latest viz data from server
  lensesInfo       object               Lens metadata from init message
  animFrame        number               requestAnimationFrame handle
  isPaused         boolean              Pause state
  particles        array                Atmosphere renderer state
```

---

## Summary: Layer Map

```
Layer 5 (User)    : Browser UI -- buttons, sliders, canvas, audio output
Layer 4 (Render)  : Canvas renderers (4 lens-specific) + AudioWorklet
Layer 3 (Network) : WebSocket (text JSON + binary PCM)
Layer 2 (Logic)   : Tick loop + Audio loop + Lens system + Bridge factory
Layer 1 (Data)    : Simulators + ControlState + Transfer functions
Layer 0 (Audio)   : Lyria API / ElevenLabs API / Mock additive synth
```

Each layer only communicates with its adjacent layers. The lens system (Layer 1-2) never reaches into the browser (Layer 4-5), and the audio bridges (Layer 0) never decide what the ControlState values should be.
