# Sonify

> *Hear what numbers hide. See what sound reveals.*

Sonify is a browser-based data sonification platform that converts abstract data into real-time music and synchronized visualizations. Four interchangeable "lenses" each sonify a different domain: weather, cardiac activity, mathematical attractors, and network traffic.

Three audio backends with automatic fallback: **Lyria RealTime** (Google's generative AI model) > **ElevenLabs Music** (text-prompt-based generation) > **Mock** (sine-wave additive synthesizer).

---

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Start the server
python server.py

# 3. Open in your browser
#    http://localhost:8000
#    Click "Start Experience"
```

Works immediately with the built-in mock audio synthesizer. No API keys needed.

For AI-generated music, see [API Key Setup](#api-key-setup) below.

---

## What It Does

Every slider you move changes the underlying data, which changes the music and the visuals simultaneously:

| Lens | Domain | Example Mapping |
|------|--------|----------------|
| **Atmosphere** | Weather | Wind speed -> tempo, temperature -> brightness, rain -> piano arpeggios |
| **Pulse** | Cardiac | Heart rate -> BPM (1:1), stress -> minor key, arrhythmia -> glitch sounds |
| **Lattice** | Mathematics | Lorenz chaos level -> tempo + density + scale + experimental prompts |
| **Flow** | Network Traffic | Packet rate -> density, latency -> brightness (inverse), bursts -> tempo spike |

All mappings are deterministic, monotone, and EMA-smoothed. The same data always produces the same sound. See `SCIENCE.md` for the full mathematical documentation.

---

## API Key Setup

Copy `.env.example` to `.env` and add one or both keys:

```
GOOGLE_API_KEY=your-google-key
ELEVENLABS_API_KEY=your-elevenlabs-key
```

The app selects the best available backend automatically:

| Priority | Backend | Key Required | What You Get |
|----------|---------|-------------|--------------|
| 1 | **Lyria RealTime** | `GOOGLE_API_KEY` | Real-time streaming with live control parameters |
| 2 | **ElevenLabs Music** | `ELEVENLABS_API_KEY` | 30-second AI-generated segments from text prompts |
| 3 | **Mock (sine wave)** | None | Additive synth driven by 8 of 9 ControlState fields |

- **Google API key:** https://aistudio.google.com/apikey -- uses the `lyria-realtime-exp` model
- **ElevenLabs API key:** https://elevenlabs.io -- uses the Music API with `pcm_48000` output
- **No keys:** Falls back to the mock sine-wave synthesizer (still responds to BPM, density, brightness, scale, guidance, temperature, mute_bass, mute_drums)

---

## Architecture

```
+-------------------------------------------------------------------+
|  BROWSER (static/index.html)                                      |
|  +-------------------+  +-------------------+  +----------------+ |
|  | UI Controls       |  | Canvas Renderer   |  | AudioWorklet   | |
|  | (sidebar sliders)  |  | (4 lens-specific) |  | (PCM playback) | |
|  +---------+---------+  +---------+---------+  +-------+--------+ |
|            |                      |                     ^          |
|            v                      |                     |          |
|  +---------+----------------------+---------------------+--------+ |
|  |             WebSocket Client (ws://host/ws)                   | |
|  +------+-------------------------------------------------------+ |
+=========|=========================================================+
          |  text: JSON {viz, controls}
          |  binary: raw PCM (9600 bytes = 50ms)
          |  client: JSON commands
+=========|=========================================================+
|  PYTHON |SERVER (server.py)                                       |
|  +------+---------+  +-----------+  +---------------------------+ |
|  | Tick Loop       |  | Audio     |  | WebSocket Handler        | |
|  | (2-10 Hz/lens)  |  | Loop      |  | (per-client coroutine)   | |
|  +------+----------+  | (~50ms)   |  +---------------------------+ |
|         |              +-----+-----+                               |
|         v                    |                                     |
|  +------+----------+  +-----+-----+                               |
|  | Active Lens      |  | Audio     |                               |
|  |  .tick(t)->data  |  | Bridge    |                               |
|  |  .map(data)->ctrl|  |           |                               |
|  |  .viz_state()->viz|  | Lyria /   |                               |
|  +------------------+  | ElevenLabs|                               |
|                        | / Mock    |                               |
|                        +-----------+                               |
+===================================================================+
```

### Data Flow Pipeline

Every tick (2-10 Hz depending on lens):

```
Simulator.tick(t) -> domain data dict
    -> Lens.map(data) -> ControlState (deterministic, EMA-smoothed, clamped)
    -> Audio Bridge.update(controls) -> PCM audio chunks
    -> Lens.viz_state(data) -> JSON for Canvas renderer
    -> WebSocket broadcasts both to browser
```

The key invariant: **Lyria/ElevenLabs/Mock are always downstream** -- the generative model never decides meaning. All mappings are deterministic, monotone, and continuous.

---

## File Structure

```
sonify/
  server.py                       # FastAPI + WebSocket hub + tick/audio loops
  pyproject.toml                  # Project metadata and dependencies
  requirements.txt                # pip install -r requirements.txt
  .env.example                    # API key placeholders

  lenses/
    __init__.py                   # LENSES dict: name -> class
    base.py                       # ControlState dataclass + abstract Lens
    atmosphere.py                 # Weather -> music (wind=BPM, temp=brightness)
    pulse.py                      # Cardiac -> music (HR=BPM 1:1, stress=key)
    lattice.py                    # Math -> music (chaos=everything)
    flow.py                       # Network -> music (packets=density)

  lyria_bridge.py                 # Lyria RealTime session + MockAudioGenerator
  elevenlabs_bridge.py            # ElevenLabs Music API bridge

  data_sources/
    simulators.py                 # All 4 domain simulators (pure Python)
    live_weather.py               # Open-Meteo API fetcher (free, no key)

  static/
    index.html                    # Full frontend (HTML + CSS + JS, single file)
    worklet.js                    # AudioWorklet processor for PCM buffering

  docs/
    ARCHITECTURE.md               # Full architecture with ASCII diagrams
    DEVELOPER_GUIDE.md            # Step-by-step guide for new developers
    USER_GUIDE.md                 # User guide with 10 educational use cases
    API_REFERENCE.md              # WebSocket protocol, ControlState, parameters

  SCIENCE.md                      # Mathematical documentation of all mappings
  CLAUDE.md                       # Instructions for AI coding assistants
```

---

## The 4 Lenses

### Atmosphere (Weather)

Maps five weather variables to musical parameters. Wind -> tempo, temperature -> brightness, humidity -> density, rain -> arpeggios + guidance, storm compound condition (wind > 20 AND rain > 0.5) -> distorted synths.

**Parameters:** Wind Speed (0-30 m/s), Temperature (-10 to 40 C), Humidity (0-100%), Rain Intensity (0-1), Pressure (980-1040 hPa).

**Special feature:** Live Weather toggle fetches real data from Paris via Open-Meteo API.

### Pulse (Heart Rate)

The most direct mapping: musical BPM = heart rate BPM (1:1). HRV drives density, stress drives key changes (C Major -> Ab Major/F minor), arrhythmias inject glitch prompts.

**Parameters:** Heart Rate (40-200), HRV (0-1), Stress (0-1), Arrhythmia Chance (0-0.2).

### Lattice (Mathematics)

Sonifies the Lorenz attractor, logistic map, or sine superposition. The chaos slider controls the Lorenz system's rho parameter (rho = 10 + 35 * chaos), driving a transition from orderly piano through jazz fusion to experimental glitch.

**Parameters:** Chaos (0-1), Sigma (1-30), Beta (0.5-8), Speed (0.1-3), Mode (Lorenz/Logistic/Sine).

### Flow (Network Traffic)

Converts Poisson-process network traffic to music. Packet rate -> density, latency -> brightness (inverse), bursts -> +50 BPM spike + distortion, errors -> glitch prompts.

**Parameters:** Packet Rate (1-200/s), Latency (1-200 ms), Burst Active (0/1), Error Rate (0-0.2), Node Count (3-16).

---

## Mock Audio: What It Does

The mock synthesizer applies 8 of 9 ControlState fields (everything except `prompts`, which requires a generative AI model to interpret natural language):

| Field | Mock Effect |
|-------|-------------|
| `bpm` | LFO rate (rhythmic pulse at beat rate) |
| `brightness` | Base pitch 110-440 Hz, quantized to scale |
| `density` | Harmonic count (1-6 overtones) |
| `scale` | Pitch snapping to scale tones (equal temperament) |
| `guidance` | LFO depth and regularity |
| `temperature` | Gaussian noise floor (0-15%) |
| `mute_bass` | Removes fundamental + 2nd harmonic |
| `mute_drums` | Suppresses LFO rhythmic pulsing |
| `prompts` | **Not applied** (requires generative AI) |

---

## Design Principles

1. **Lyria is downstream** -- the model never decides meaning. Deterministic mappers control everything.
2. **Monotone mappings** -- higher wind = higher BPM, always. Makes sonification learnable.
3. **Perceptual stability** -- EMA smoothing on all inputs prevents jarring transitions. Cutoff ~0.13 Hz with alpha=0.15 at 5 Hz tick rate.
4. **All controls clamped** to valid ranges (BPM 60-200, density 0-1, brightness 0-1, guidance 0-6, temperature 0-3).

---

## Configuration

| Environment Variable | Purpose | Default |
|---------------------|---------|---------|
| `GOOGLE_API_KEY` | Lyria RealTime backend | None (mock fallback) |
| `ELEVENLABS_API_KEY` | ElevenLabs Music backend | None (mock fallback) |
| `PORT` | Server port | 8000 |

Set in `.env` file or as environment variables.

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full architecture with ASCII diagrams at multiple abstraction levels |
| [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | Step-by-step guide for developers new to web app development |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | User guide with 10 educational use cases |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | WebSocket protocol, ControlState fields, lens parameters |
| [SCIENCE.md](SCIENCE.md) | Mathematical documentation of all transfer functions and models |
| [CLAUDE.md](CLAUDE.md) | Instructions for AI coding assistants |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No sound after clicking Start | Click anywhere on the page first (browser autoplay policy) |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Port 8000 in use | `PORT=8001 python server.py` |
| Lyria connection fails | App cascades to ElevenLabs (if key set), then to mock audio |
| ElevenLabs audio delay | First segment takes 5-15s to generate. Subsequent segments are gapless. |
| Audio stops when moving sliders | Prompt changes are debounced (2s). Current segment finishes before new one starts. |
| Badge shows "Mock Audio" despite keys | Check key names in `.env` match exactly: `GOOGLE_API_KEY`, `ELEVENLABS_API_KEY` |
| Live Weather not working | Toggle "Live Weather" in the Atmosphere lens sidebar. Requires internet. |

---

## Requirements

- Python 3.10+
- Modern web browser (Chrome, Firefox, or Edge)
- No build tools, no npm, no webpack -- just Python and a browser
