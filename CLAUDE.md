# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sonify is a browser-based data sonification platform that maps abstract data through deterministic pipelines into real-time music and synchronized Canvas visualizations. Four interchangeable "lenses" sonify different domains: weather, cardiac activity, mathematical attractors, and network traffic.

Three audio backends with automatic fallback: **Lyria RealTime** (Google's generative model) > **ElevenLabs Music** (text-prompt generation) > **Mock** (sine-wave additive synth).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server (opens at http://localhost:8000)
python server.py

# Run on a different port
PORT=8001 python server.py
```

There are no tests, linter, or build steps configured.

## Architecture

### Data Flow Pipeline

Every tick (2-10 Hz depending on lens):
```
Simulator.tick(t) -> domain data dict
    -> Lens.map(data) -> ControlState (deterministic, EMA-smoothed, clamped)
    -> Audio Bridge.update(controls) -> PCM audio chunks
    -> Lens.viz_state(data) -> JSON for Canvas renderer
    -> WebSocket broadcasts both to browser
```

The key invariant: **Lyria/ElevenLabs/Mock are always downstream** -- the generative model never decides meaning. All mappings are deterministic, monotone, and continuous (see `SCIENCE.md` for the math).

### Server (`server.py`)

FastAPI app with a single WebSocket endpoint at `/ws`. Two concurrent async loops:
- **tick_loop**: runs the active lens, sends JSON text frames (viz + controls readout)
- **audio_loop**: pulls PCM chunks from the bridge, sends binary frames

Global mutable state: `active_lens`, `bridge`, `connected_clients`, `paused`, `use_live_weather`. Lens switching triggers `bridge.reset()`.

### Lenses (`lenses/`)

Abstract base: `Lens` in `lenses/base.py`. Each lens implements three methods:
- `tick(t)` -- generates domain data from a simulator
- `map(data)` -- maps domain data to `ControlState` dataclass (9 fields: bpm, density, brightness, guidance, scale, prompts, mute_bass, mute_drums, temperature)
- `viz_state(data)` -- produces JSON for the browser Canvas renderer

All numeric mapping goes through `self._ema(key, value)` for temporal smoothing (alpha=0.15). `ControlState.clamped()` enforces Lyria-valid ranges. `ControlState.diff()` uses dead-zone comparison to minimize API updates.

The four lenses: `AtmosphereLens`, `PulseLens`, `LatticeLens`, `FlowLens`. Registered in `lenses/__init__.py:LENSES` dict.

### Audio Bridges

All bridges share the same interface: `connect()`, `update(controls)`, `get_audio_chunk()`, `reset()`, `disconnect()`, `is_mock` property.

- **`LyriaBridge`** (`lyria_bridge.py`): Wraps the Google Lyria RealTime streaming session. Diffs ControlState and only sends changes. Falls back to `MockAudioGenerator` internally if no API key or connection fails.
- **`ElevenLabsBridge`** (`elevenlabs_bridge.py`): Converts ControlState to a text prompt via `_build_prompt()`, generates 30s segments via `_generation_loop()`. Debounces prompt changes (2s). Uses generation counter (`_gen_id`) to discard stale results after `reset()`.
- **`MockAudioGenerator`** (in `lyria_bridge.py`): Additive synthesizer applying 8 of 9 ControlState fields (everything except `prompts`, which requires a generative model). Includes scale quantization via equal temperament, LFO for rhythm, noise injection for temperature.

Audio format: 16-bit signed LE PCM, 48kHz, stereo, 2400-frame chunks (9600 bytes = 50ms).

### Data Sources (`data_sources/`)

- `simulators.py`: Pure-Python simulators for all 4 domains (WeatherSimulator, CardiacSimulator, MathSimulator with LorenzAttractor, NetworkSimulator with Poisson process). Zero external dependencies.
- `live_weather.py`: Open-Meteo API fetcher (free, no key). 5-minute cache TTL. Default location: Paris.

### Frontend (`static/`)

Single-page app in `static/index.html` -- all UI, Canvas rendering, and WebSocket client in one file. `static/worklet.js` is an AudioWorklet processor with a ring buffer (5s capacity) for PCM playback.

WebSocket protocol:
- Text frames: `{"viz": {...}, "controls": {...}, "lens": "...", "backend": "..."}` or init/pause messages
- Binary frames: raw PCM audio chunks
- Client sends: `switch_lens`, `set_param`, `pause`, `play`, `toggle_live`

## Key Design Constraints

- **Monotone mappings**: higher input always yields higher output (e.g., more wind = higher BPM). This makes sonification learnable.
- **EMA smoothing on all control dimensions** prevents jarring transitions. Cutoff ~0.13 Hz with default alpha=0.15 at 5 Hz tick rate.
- **All ControlState values clamped** to Lyria-valid ranges before sending (BPM 60-200, density 0-1, brightness 0-1, guidance 0-6, temperature 0-3).
- **Bridge selection cascade** at startup: Lyria -> (if Lyria fails) ElevenLabs -> Mock. Configured via `GOOGLE_API_KEY` and `ELEVENLABS_API_KEY` env vars in `.env`.

## Environment Variables

Set in `.env` (copied from `.env.example`):
- `GOOGLE_API_KEY` -- for Lyria RealTime (highest priority backend)
- `ELEVENLABS_API_KEY` -- for ElevenLabs Music API (fallback)
- `PORT` -- server port (default 8000)

No keys = mock sine-wave synth (still responds to 8 of 9 ControlState fields).

## File Map

```
server.py                         # FastAPI app, WebSocket endpoint, tick/audio loops
lenses/
  __init__.py                     # LENSES dict (name -> class)
  base.py                        # ControlState dataclass, abstract Lens, EMA
  atmosphere.py                  # Weather lens: wind->BPM, temp->brightness
  pulse.py                       # Cardiac lens: HR->BPM (1:1), stress->key
  lattice.py                     # Math lens: chaos->BPM/density/scale/prompts
  flow.py                        # Network lens: packets->density, latency->brightness
lyria_bridge.py                   # LyriaBridge + MockAudioGenerator
elevenlabs_bridge.py              # ElevenLabsBridge
data_sources/
  simulators.py                  # WeatherSim, CardiacSim, MathSim, NetworkSim
  live_weather.py                # Open-Meteo API fetcher
static/
  index.html                     # Full frontend (HTML+CSS+JS, single file)
  worklet.js                     # AudioWorklet PCM ring buffer
docs/
  ARCHITECTURE.md                # Architecture diagrams at multiple levels
  DEVELOPER_GUIDE.md             # Step-by-step guide for new developers
  USER_GUIDE.md                  # User guide with 10 educational use cases
  API_REFERENCE.md               # WebSocket protocol, all parameters
SCIENCE.md                        # Mathematical documentation of mappings
```

## How to Add a New Lens

1. Create `lenses/newlens.py` with a class that extends `Lens` from `lenses/base.py`
2. Implement `name`, `description`, `tick_hz`, `parameters` class attributes
3. Implement `tick(t)`, `map(data)`, `viz_state(data)` methods
4. Register in `lenses/__init__.py`: add to `LENSES` dict
5. Add a Canvas renderer function in `static/index.html` and update `animate()`
6. Add an icon in `buildLensButtons()` icons dict

## How to Add a New Audio Backend

1. Create a new bridge file (e.g., `mybridge.py`)
2. Implement the bridge interface: `connect()`, `update(controls)`, `get_audio_chunk()`, `reset()`, `disconnect()`, `is_mock` property
3. `get_audio_chunk()` must return 9600 bytes (2400 stereo frames, 16-bit LE PCM, 48kHz) or None
4. Add to `create_bridge()` cascade in `server.py`

## Key Gotchas

- All ControlState values must pass through `_ema()` for perceptual smoothing before being set
- `ControlState.clamped()` is called in `Lens.update()` -- do not call it manually in `map()`
- The mock synth ignores `prompts` entirely -- only Lyria and ElevenLabs respond to text prompts
- ElevenLabs debounces prompt changes by 2 seconds -- rapid slider movements are batched
- The frontend is a single HTML file -- no build step, no modules, no framework
- WebSocket binary frames are raw PCM, text frames are JSON -- both on the same connection
- `bridge.reset()` is called on every lens switch to clear audio state
