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
Simulator.tick(t) → domain data dict
    → Lens.map(data) → ControlState (deterministic, EMA-smoothed, clamped)
    → Audio Bridge.update(controls) → PCM audio chunks
    → Lens.viz_state(data) → JSON for Canvas renderer
    → WebSocket broadcasts both to browser
```

The key invariant: **Lyria/ElevenLabs/Mock are always downstream** — the generative model never decides meaning. All mappings are deterministic, monotone, and continuous (see `SCIENCE.md` for the math).

### Server (`server.py`)

FastAPI app with a single WebSocket endpoint at `/ws`. Two concurrent async loops:
- **tick_loop**: runs the active lens, sends JSON text frames (viz + controls readout)
- **audio_loop**: pulls PCM chunks from the bridge, sends binary frames

Global mutable state: `active_lens`, `bridge`, `connected_clients`, `paused`, `use_live_weather`. Lens switching triggers `bridge.reset()`.

### Lenses (`lenses/`)

Abstract base: `Lens` in `lenses/base.py`. Each lens implements three methods:
- `tick(t)` — generates domain data from a simulator
- `map(data)` — maps domain data to `ControlState` dataclass (9 fields: bpm, density, brightness, guidance, scale, prompts, mute_bass, mute_drums, temperature)
- `viz_state(data)` — produces JSON for the browser Canvas renderer

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

Single-page app in `static/index.html` — all UI, Canvas rendering, and WebSocket client in one file. `static/worklet.js` is an AudioWorklet processor with a ring buffer (5s capacity) for PCM playback.

WebSocket protocol:
- Text frames: `{"viz": {...}, "controls": {...}, "lens": "...", "backend": "..."}` or init/pause messages
- Binary frames: raw PCM audio chunks
- Client sends: `switch_lens`, `set_param`, `pause`, `play`, `toggle_live`

## Key Design Constraints

- **Monotone mappings**: higher input always yields higher output (e.g., more wind = higher BPM). This makes sonification learnable.
- **EMA smoothing on all control dimensions** prevents jarring transitions. Cutoff ~0.13 Hz with default alpha=0.15 at 5 Hz tick rate.
- **All ControlState values clamped** to Lyria-valid ranges before sending (BPM 60-200, density 0-1, brightness 0-1, guidance 0-6, temperature 0-3).
- **Bridge selection cascade** at startup: Lyria → (if Lyria fails) ElevenLabs → Mock. Configured via `GOOGLE_API_KEY` and `ELEVENLABS_API_KEY` env vars in `.env`.

## Environment Variables

Set in `.env` (copied from `.env.example`):
- `GOOGLE_API_KEY` — for Lyria RealTime (highest priority backend)
- `ELEVENLABS_API_KEY` — for ElevenLabs Music API (fallback)
- `PORT` — server port (default 8000)

No keys = mock sine-wave synth (still responds to 8 of 9 ControlState fields).
