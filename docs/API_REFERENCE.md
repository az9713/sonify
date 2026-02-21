# Sonify API Reference

This document provides complete reference documentation for the WebSocket protocol, ControlState fields, lens parameters, and audio bridge interfaces.

---

## Table of Contents

1. [WebSocket Protocol](#1-websocket-protocol)
2. [ControlState Reference](#2-controlstate-reference)
3. [Lens Parameters Reference](#3-lens-parameters-reference)
4. [Audio Bridge Interface](#4-audio-bridge-interface)
5. [Audio Format Specification](#5-audio-format-specification)
6. [HTTP Endpoints](#6-http-endpoints)
7. [Transfer Function Reference](#7-transfer-function-reference)
8. [Scale Reference](#8-scale-reference)
9. [Simulator Reference](#9-simulator-reference)
10. [Configuration Reference](#10-configuration-reference)

---

## 1. WebSocket Protocol

### 1.1 Connection

**Endpoint:** `ws://localhost:8000/ws` (or `wss://` for HTTPS)

**Binary type:** The WebSocket uses mixed frames:
- **Text frames** carry JSON messages
- **Binary frames** carry raw PCM audio data

### 1.2 Client -> Server Messages

All messages are JSON text frames.

#### switch_lens

Switch the active sonification lens. Triggers `bridge.reset()` on the server.

```json
{
    "type": "switch_lens",
    "lens": "atmosphere"
}
```

| Field | Type | Values | Required |
|-------|------|--------|----------|
| type | string | `"switch_lens"` | yes |
| lens | string | `"atmosphere"`, `"pulse"`, `"lattice"`, `"flow"` | yes |

#### set_param

Set a parameter value on the active lens.

```json
{
    "type": "set_param",
    "name": "wind_speed",
    "value": 15.0
}
```

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| type | string | `"set_param"` | yes |
| name | string | Parameter name (from lens's `parameters` list) | yes |
| value | number | New value (must be within parameter's min/max range) | yes |

#### pause

Pause the sonification. Stops both tick_loop and audio_loop from broadcasting.

```json
{
    "type": "pause"
}
```

#### play

Resume the sonification after pausing.

```json
{
    "type": "play"
}
```

#### toggle_live

Enable or disable live weather data for the Atmosphere lens.

```json
{
    "type": "toggle_live",
    "enabled": true
}
```

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| type | string | `"toggle_live"` | yes |
| enabled | boolean | `true` to enable, `false` to disable | yes |

### 1.3 Server -> Client Messages

#### init (text frame)

Sent once when a client connects. Contains all lens metadata needed to build the UI.

```json
{
    "type": "init",
    "lens": "atmosphere",
    "lenses": {
        "atmosphere": {
            "description": "Weather patterns become sound and light",
            "parameters": [
                {
                    "name": "wind_speed",
                    "label": "Wind Speed (m/s)",
                    "min": 0,
                    "max": 30,
                    "step": 0.5,
                    "default": 5.0,
                    "effects": [
                        "-> BPM: 70 + wind * 3.67 (faster wind = faster tempo)"
                    ]
                }
            ]
        },
        "pulse": { "..." },
        "lattice": { "..." },
        "flow": { "..." }
    },
    "is_mock": false,
    "backend": "lyria",
    "paused": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| type | string | Always `"init"` |
| lens | string | Currently active lens name |
| lenses | object | Map of lens name -> {description, parameters} |
| is_mock | boolean | Whether the audio engine is the mock synthesizer |
| backend | string | `"lyria"`, `"elevenlabs"`, or `"mock"` |
| paused | boolean | Current pause state |

#### paused (text frame)

Broadcast to all clients when pause state changes.

```json
{
    "type": "paused",
    "paused": true
}
```

#### tick (text frame)

Broadcast every tick (2-10 Hz depending on the active lens). Contains visualization data and control state readout.

```json
{
    "viz": {
        "type": "atmosphere",
        "particle_velocity": 0.5,
        "particle_count": 150,
        "particle_size": 3.2,
        "color": {"r": 255, "g": 220, "b": 100},
        "wind_angle": 1.23,
        "rain_drops": false,
        "lightning": false,
        "data": {
            "temperature": 22.0,
            "wind_speed": 15.0,
            "humidity": 60.0,
            "pressure": 1013.0,
            "rain": 0.1
        }
    },
    "controls": {
        "bpm": 125,
        "density": 0.60,
        "brightness": 0.64,
        "guidance": 3.2,
        "scale": "C_MAJOR_A_MINOR",
        "prompts": [
            {"text": "Ambient, smooth pianos, dreamy", "weight": 1.0}
        ],
        "mute_bass": false,
        "mute_drums": false
    },
    "lens": "atmosphere",
    "is_mock": false,
    "backend": "lyria"
}
```

| Field | Type | Description |
|-------|------|-------------|
| viz | object | Visualization state (structure varies by lens type) |
| controls | object | Current ControlState values (after EMA smoothing and clamping) |
| lens | string | Active lens name |
| is_mock | boolean | Whether using mock audio |
| backend | string | Active backend identifier |

#### audio (binary frame)

Sent approximately 20 times per second. Contains raw PCM audio data.

| Property | Value |
|----------|-------|
| Frame type | Binary |
| Size | 9600 bytes |
| Content | 2400 stereo frames of 16-bit signed little-endian PCM at 48kHz |

---

## 2. ControlState Reference

File: `lenses/base.py:9-61`

ControlState is a Python dataclass with 9 fields that drive the audio engine. All values are deterministically computed from domain data by each lens's `map()` method.

### 2.1 Field Reference

| Field | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| `bpm` | int | 60-200 | 120 | Musical tempo in beats per minute |
| `density` | float | 0.0-1.0 | 0.5 | Number of simultaneous musical voices/layers |
| `brightness` | float | 0.0-1.0 | 0.5 | Timbral brightness (dark=0 to bright=1) |
| `guidance` | float | 0.0-6.0 | 4.0 | How closely the AI follows text prompts |
| `scale` | str | Scale enum | `"SCALE_UNSPECIFIED"` | Musical key/mode |
| `prompts` | list[dict] | [{text, weight}] | `[{"text":"ambient","weight":1.0}]` | Text descriptions for the AI |
| `mute_bass` | bool | True/False | False | Suppress bass frequencies |
| `mute_drums` | bool | True/False | False | Suppress rhythmic percussion |
| `temperature` | float | 0.0-3.0 | 1.1 | Randomness/experimentalism of AI output |

### 2.2 Methods

#### `clamped() -> ControlState`

Returns a copy with all numeric values clamped to valid ranges:
- `bpm`: max(60, min(200, int(bpm)))
- `density`: max(0.0, min(1.0, density))
- `brightness`: max(0.0, min(1.0, brightness))
- `guidance`: max(0.0, min(6.0, guidance))
- `temperature`: max(0.0, min(3.0, temperature))

#### `diff(other: ControlState) -> dict`

Returns a dictionary of fields that changed between `self` and `other`. Uses dead-zone thresholds:
- `bpm`: exact integer comparison
- `density`, `brightness`, `guidance`, `temperature`: change threshold of 0.01
- `scale`: exact string comparison
- `prompts`: exact list comparison
- `mute_bass`, `mute_drums`: exact boolean comparison

### 2.3 Valid Scale Values

| Scale String | Key | Notes | Mood |
|-------------|-----|-------|------|
| `"SCALE_UNSPECIFIED"` | Chromatic | All 12 semitones | Neutral |
| `"C_MAJOR_A_MINOR"` | C Major / A minor | C D E F G A B | Bright, consonant |
| `"D_MAJOR_B_MINOR"` | D Major / B minor | C# D E F# G A B | Bright, joyful |
| `"A_FLAT_MAJOR_F_MINOR"` | Ab Major / F minor | Ab Bb C Db Eb F G | Dark, melancholic |
| `"G_FLAT_MAJOR_E_FLAT_MINOR"` | Gb Major / Eb minor | Gb Ab Bb Cb Db Eb F | Dark, brooding |

---

## 3. Lens Parameters Reference

### 3.1 Parameter Object Schema

Each parameter in a lens's `parameters` list has this structure:

```python
{
    "name": str,        # Internal identifier (used in set_param messages)
    "label": str,       # Human-readable label for UI display
    "min": float,       # Minimum slider value
    "max": float,       # Maximum slider value
    "step": float,      # Slider increment
    "default": float,   # Initial value
    "effects": [str],   # List of descriptions of what this parameter affects
}
```

### 3.2 Atmosphere Lens Parameters

File: `lenses/atmosphere.py:14-54`

| Name | Label | Min | Max | Step | Default |
|------|-------|-----|-----|------|---------|
| `wind_speed` | Wind Speed (m/s) | 0 | 30 | 0.5 | 5.0 |
| `temperature` | Temperature (C) | -10 | 40 | 1 | 20.0 |
| `humidity` | Humidity (%) | 0 | 100 | 1 | 50.0 |
| `rain` | Rain Intensity | 0 | 1 | 0.05 | 0.0 |
| `pressure` | Pressure (hPa) | 980 | 1040 | 1 | 1013.0 |

### 3.3 Pulse Lens Parameters

File: `lenses/pulse.py:16-47`

| Name | Label | Min | Max | Step | Default |
|------|-------|-----|-----|------|---------|
| `heart_rate` | Heart Rate (bpm) | 40 | 200 | 1 | 72.0 |
| `hrv` | HRV (variability) | 0 | 1 | 0.05 | 0.5 |
| `stress` | Stress Level | 0 | 1 | 0.05 | 0.2 |
| `arrhythmia_chance` | Arrhythmia Chance | 0 | 0.2 | 0.01 | 0.0 |

### 3.4 Lattice Lens Parameters

File: `lenses/lattice.py:16-57`

| Name | Label | Min | Max | Step | Default |
|------|-------|-----|-----|------|---------|
| `chaos` | Chaos (rho) | 0 | 1 | 0.02 | 0.7 |
| `sigma` | Sigma | 1 | 30 | 0.5 | 10.0 |
| `beta` | Beta | 0.5 | 8 | 0.1 | 2.67 |
| `speed` | Speed | 0.1 | 3 | 0.1 | 1.0 |
| `mode` | Mode | 0 | 1 | 0.5 | 0.0 |

Mode values: 0 = Lorenz attractor, 0.5 = Logistic map, 1.0 = Sine superposition.

### 3.5 Flow Lens Parameters

File: `lenses/flow.py:16-54`

| Name | Label | Min | Max | Step | Default |
|------|-------|-----|-----|------|---------|
| `packet_rate` | Packet Rate (/s) | 1 | 200 | 1 | 30.0 |
| `latency` | Latency (ms) | 1 | 200 | 1 | 50.0 |
| `burst` | Burst Active | 0 | 1 | 1 | 0.0 |
| `error_rate` | Error Rate | 0 | 0.2 | 0.01 | 0.01 |
| `num_nodes` | Node Count | 3 | 16 | 1 | 8.0 |

---

## 4. Audio Bridge Interface

All three audio bridges share the same implicit interface. There is no formal abstract base class; the interface is defined by convention.

### 4.1 Interface Methods

```python
class AudioBridge:
    """Implicit interface shared by LyriaBridge, ElevenLabsBridge, MockAudioGenerator."""

    @property
    def is_mock(self) -> bool:
        """Returns True if the bridge is using the mock synthesizer fallback."""

    async def connect(self) -> None:
        """Establish connection to the audio backend.

        Called once at startup. If connection fails, the bridge should
        fall back to MockAudioGenerator internally and set is_mock=True.
        """

    async def update(self, controls: ControlState) -> None:
        """Send new control state to the audio engine.

        Called every tick (2-10 Hz). Implementations should diff against
        previous state to minimize API calls.

        Args:
            controls: A clamped ControlState from the active lens.
        """

    async def get_audio_chunk(self) -> bytes | None:
        """Return the next PCM audio chunk, or None if unavailable.

        Called ~20 times per second by the audio_loop.
        Must return 9600 bytes (2400 stereo frames of 16-bit PCM at 48kHz)
        or None if no audio is available.
        """

    async def reset(self) -> None:
        """Reset the audio engine state.

        Called when the user switches lenses. Implementations should:
        - Clear any cached control state
        - Drain audio queues
        - Reset the audio context/session
        """

    async def disconnect(self) -> None:
        """Clean up resources.

        Called once at shutdown. Cancel background tasks, close sessions.
        """
```

### 4.2 LyriaBridge

File: `lyria_bridge.py:166-364`

**Constructor:** `LyriaBridge()`

- Reads `GOOGLE_API_KEY` from environment
- If no key, sets `_use_mock = True`

**Key behaviors:**
- Uses `ControlState.diff()` to send only changed parameters to Lyria
- BPM or scale changes trigger `session.reset_context()` for musical coherence
- Background `_receive_audio()` task continuously reads from the Lyria session
- Audio is queued in an `asyncio.Queue(maxsize=100)`
- On queue overflow, drops oldest chunk (prevents memory accumulation)

### 4.3 ElevenLabsBridge

File: `elevenlabs_bridge.py`

**Constructor:** `ElevenLabsBridge()`

- Reads `ELEVENLABS_API_KEY` from environment
- If no key, sets `_use_mock = True`

**Key behaviors:**
- Converts ControlState to text prompt via `_build_prompt()`
- Generates 30-second segments via `_generation_loop()` background task
- Prompt changes debounced at 2 seconds (`_DEBOUNCE_SECONDS = 2.0`)
- Uses generation counter (`_gen_id`) to discard stale API responses after `reset()`
- Detects mono output and converts to stereo
- Exponential backoff on rate limiting (2s, 4s, 8s, ... up to 60s)
- Audio queued in `asyncio.Queue(maxsize=200)`

**Prompt construction rules:**

| ControlState Field | Prompt Fragment | Condition |
|---|---|---|
| prompts | Lens text prompts sorted by weight | Always included |
| bpm | "slow tempo" | bpm < 80 |
| bpm | "moderate tempo" | 80 <= bpm < 110 |
| bpm | "upbeat tempo" | 110 <= bpm < 140 |
| bpm | "fast energetic tempo" | bpm >= 140 |
| density | "sparse minimal arrangement" | density < 0.3 |
| density | "dense layered arrangement" | density > 0.7 |
| brightness | "dark muted tones" | brightness < 0.3 |
| brightness | "bright shimmering tones" | brightness > 0.7 |
| scale | Key + mood text | Exact match lookup |
| mute_bass | "no bass" | True |
| mute_drums | "no drums" | True |
| temperature | "experimental, unconventional" | temperature > 2.0 |
| temperature | "structured, predictable" | temperature < 0.5 |
| (always) | "instrumental" | Always appended |

### 4.4 MockAudioGenerator

File: `lyria_bridge.py:16-163`

**Constructor:** `MockAudioGenerator(sample_rate=48000, channels=2)`

**ControlState coverage (8 of 9 fields):**

| Field | Applied | Synth Parameter |
|-------|---------|----------------|
| bpm | Yes | LFO rate = bpm / 60.0 Hz |
| brightness | Yes | Base frequency = 110 + brightness * 330 Hz (then quantized) |
| density | Yes | Harmonic count = 1 + int(density * 5) |
| scale | Yes | Pitch quantization to scale tones |
| guidance | Yes | LFO depth = min(1.0, guidance / 6.0) |
| temperature | Yes | Noise floor = temperature / 3.0 * 0.15 |
| mute_bass | Yes | Remove harmonics k=1, k=2 |
| mute_drums | Yes | Bypass LFO (flat amplitude envelope) |
| prompts | **No** | Requires generative AI to interpret |

---

## 5. Audio Format Specification

### 5.1 PCM Format

| Property | Value |
|----------|-------|
| Encoding | Linear PCM (uncompressed) |
| Bit depth | 16-bit signed integer |
| Byte order | Little-endian |
| Sample rate | 48,000 Hz |
| Channels | 2 (stereo) |
| Channel layout | Interleaved (L, R, L, R, ...) |
| Chunk size | 2400 frames |
| Chunk bytes | 2400 frames * 2 channels * 2 bytes = 9600 bytes |
| Chunk duration | 2400 / 48000 = 0.05 seconds (50 ms) |
| Data rate | 9600 bytes * 20 chunks/sec = 192,000 bytes/sec (192 KB/s) |

### 5.2 Byte Layout of One Chunk

```
Byte offset  Content
0-1          Sample 0, Left channel  (int16, little-endian)
2-3          Sample 0, Right channel (int16, little-endian)
4-5          Sample 1, Left channel
6-7          Sample 1, Right channel
...
9596-9597    Sample 2399, Left channel
9598-9599    Sample 2399, Right channel
```

### 5.3 AudioWorklet Ring Buffer

File: `static/worklet.js`

| Property | Value |
|----------|-------|
| Buffer size | 480,000 float32 samples (48000 * 2 channels * 5 seconds) |
| Capacity | 5 seconds of stereo audio |
| Write format | Float32 (converted from int16 by dividing by 32768) |
| Read rate | 48,000 Hz (enforced by Web Audio API) |
| Read batch size | 128 frames per `process()` call |
| Underrun behavior | Output silence (zeros) |

---

## 6. HTTP Endpoints

### GET /

Returns `static/index.html`. The main application page.

### GET /api/lenses

Returns JSON describing all available lenses and their parameters.

**Response:**

```json
{
    "atmosphere": {
        "name": "atmosphere",
        "description": "Weather patterns become sound and light",
        "parameters": [...]
    },
    "pulse": {
        "name": "pulse",
        "description": "Your heartbeat becomes a symphony",
        "parameters": [...]
    },
    "lattice": {
        "name": "lattice",
        "description": "Mathematics made audible",
        "parameters": [...]
    },
    "flow": {
        "name": "flow",
        "description": "Network traffic as rhythm and light",
        "parameters": [...]
    }
}
```

### GET /static/{path}

Serves static files from the `static/` directory (index.html, worklet.js).

---

## 7. Transfer Function Reference

### 7.1 Atmosphere Lens

| Input | Output | Formula | EMA Key |
|-------|--------|---------|---------|
| wind_speed (0-30) | bpm (70-180) | `70 + wind * 3.67` | "bpm" |
| temperature (-10-40) | brightness (0-1) | `(temp + 10) / 50` | "brightness" |
| humidity (0-100) | density (0-1) | `humidity / 100` | "density" |
| rain_probability (0-1) | guidance (3.0-5.0) | `3.0 + rain * 2.0` | none |
| rain > 0.3 | prompts | "Piano arpeggios, rain, gentle" @ weight=rain | none |
| temp < 5 | prompts | "Ethereal Ambience, cold, sustained chords" @ 1.0 | none |
| temp > 30 | prompts | "Warm acoustic guitar, bright tones, upbeat" @ 1.0 | none |
| wind > 15 | prompts | "Spacey synths, wind, sweeping" @ wind/30 | none |
| wind > 20 AND rain > 0.5 | prompts | "Dirty synths, crunchy distortion, ominous drone" @ 0.8 | none |

### 7.2 Pulse Lens

| Input | Output | Formula | EMA Key |
|-------|--------|---------|---------|
| heart_rate (40-200) | bpm (60-200) | `max(60, min(200, hr))` | "bpm" |
| hrv_sdnn_ms (0-80) | density (0-1) | `hrv / 80` | "density" |
| stress (0-1) | brightness (0.3-0.9) | `0.3 + stress * 0.6` | "brightness" |
| stress (0-1) | guidance (3.5-5.0) | `3.5 + stress * 1.5` | none |
| stress > 0.5 | scale | `"A_FLAT_MAJOR_F_MINOR"` | none |
| stress <= 0.5 | scale | `"C_MAJOR_A_MINOR"` | none |
| hr < 80 AND stress < 0.3 | prompts | "Meditation, chill, ambient" @ 1.0 | none |
| hr > 140 | prompts | "EDM, upbeat, danceable" @ 1.0 | none |
| stress > 0.6 | prompts | "Tense, ominous drone" @ 1.0 | none |
| arrhythmia == True | prompts | "Glitchy effects, weird noises" @ 0.7 | none |

### 7.3 Lattice Lens

| Input | Output | Formula | EMA Key |
|-------|--------|---------|---------|
| amplitude (0-1) | brightness (0-1) | direct | "brightness" |
| chaos_level (0-1) | density (0-1) | direct | "density" |
| chaos_level (0-1) | bpm (80-160) | `80 + chaos * 80` | "bpm" |
| chaos_level (0-1) | guidance (3.0-5.0) | `3.0 + chaos * 2.0` | none |
| chaos_level (0-1) | temperature (0.8-1.8) | `0.8 + chaos * 1.0` | none |
| chaos_level < 0.3 | scale | `"C_MAJOR_A_MINOR"` | none |
| 0.3 <= chaos_level < 0.6 | scale | `"D_MAJOR_B_MINOR"` | none |
| chaos_level >= 0.6 | scale | `"G_FLAT_MAJOR_E_FLAT_MINOR"` | none |
| chaos_level < 0.3 | prompts | "Piano, melodic, classical, ordered" @ 1.0 | none |
| 0.3 <= chaos < 0.6 | prompts | "Jazz fusion, complex, experimental" @ 1.0 | none |
| chaos_level >= 0.6 | prompts | "Glitchy effects, experimental, weird noises" @ 1.0 | none |

### 7.4 Flow Lens

| Input | Output | Formula | EMA Key |
|-------|--------|---------|---------|
| packet_rate (1-200) | density (0-1) | `min(1.0, rate / 200)` | "density" |
| latency_ms (1-200) | brightness (0-1) | `max(0, 1.0 - latency / 200)` | "brightness" |
| load_level (0-1) | bpm (80-120 or +50 on burst) | `80 + load * 40 [+ 50 if burst]` | "bpm" |
| load_level (0-1) | guidance (3.5-5.0) | `3.5 + load * 1.5` | none |
| load_level (0-1) | temperature (1.0-1.5) | `1.0 + load * 0.5` | none |
| load < 0.3 | prompts | "Ambient, minimal, spacey synths" @ 1.0 | none |
| 0.3 <= load < 0.7 | prompts | "Chiptune, electronic, steady" @ 1.0 | none |
| load >= 0.7 | prompts | "Drum & Bass, intense, fast" @ 1.0 | none |
| is_burst == True | prompts | "Huge drop, intense, crunchy distortion" @ 0.8 | none |
| error_rate > 0.05 | prompts | "Glitchy effects, metallic twang" @ error_rate*5 | none |

---

## 8. Scale Reference

### 8.1 Available Scales

| Enum String | Key Signature | Pitch Classes (semitones from C) |
|-------------|---------------|----------------------------------|
| `SCALE_UNSPECIFIED` | Chromatic | All 12: {0,1,2,3,4,5,6,7,8,9,10,11} |
| `C_MAJOR_A_MINOR` | No sharps/flats | {0, 2, 4, 5, 7, 9, 11} |
| `D_MAJOR_B_MINOR` | 2 sharps | {1, 2, 4, 6, 7, 9, 11} |
| `A_FLAT_MAJOR_F_MINOR` | 4 flats | {0, 1, 3, 5, 7, 8, 10} |
| `G_FLAT_MAJOR_E_FLAT_MINOR` | 6 flats | {1, 3, 5, 6, 8, 10, 11} |

### 8.2 Scale Usage by Lens

| Lens | Condition | Scale |
|------|-----------|-------|
| Atmosphere | Always | `SCALE_UNSPECIFIED` (default) |
| Pulse | stress < 0.5 | `C_MAJOR_A_MINOR` |
| Pulse | stress >= 0.5 | `A_FLAT_MAJOR_F_MINOR` |
| Lattice | chaos < 0.3 | `C_MAJOR_A_MINOR` |
| Lattice | 0.3 <= chaos < 0.6 | `D_MAJOR_B_MINOR` |
| Lattice | chaos >= 0.6 | `G_FLAT_MAJOR_E_FLAT_MINOR` |
| Flow | Always | `SCALE_UNSPECIFIED` (default) |

---

## 9. Simulator Reference

### 9.1 WeatherSimulator

File: `data_sources/simulators.py:10-53`

Generates weather data using layered sinusoids plus Gaussian noise. Used by AtmosphereLens when live weather is not enabled.

**Output fields:**

| Field | Type | Range | Generation |
|-------|------|-------|------------|
| temperature | float | -10 to 40 | Diurnal cycle: base + 10*sin(t*0.02) + 3*sin(t*0.13) + noise |
| wind_speed | float | 0 to 100 | Oscillation: base + 15*|sin(t*0.05)| + 10*|sin(t*0.17)| + noise |
| humidity | float | 0 to 100 | Inversely correlated with temperature + oscillation |
| pressure | float | 990 to 1030 | Slow oscillation: 1013 + 15*sin(t*0.008) + noise |
| rain_probability | float | 0 to 1 | Derived from pressure and humidity |

### 9.2 CardiacSimulator

File: `data_sources/simulators.py:56-124`

Generates cardiac data including ECG waveform, heart rate variability, and arrhythmia events.

**Output fields:**

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| heart_rate | float | 40-200 | Current instantaneous heart rate |
| rr_interval_ms | float | 300-1500 | R-R interval in milliseconds |
| hrv_sdnn_ms | float | 0-80 | Standard deviation of R-R intervals |
| ecg_value | float | -0.2 to 1.1 | Current point on ECG waveform |
| arrhythmia | bool | True/False | Whether this beat is arrhythmic |
| stress | float | 0-1 | Input stress level |
| exercise_level | float | 0-1 | Input exercise level |

### 9.3 LorenzAttractor

File: `data_sources/simulators.py:127-166`

Lorenz system integrator using Euler method with dt=0.005.

**Parameters:** sigma (default 10.0), rho (default 28.0), beta (default 8/3)

**Output:** (x, y, z) coordinates + trail history (last 500 points) + chaos_metric (0-1)

### 9.4 MathSimulator

File: `data_sources/simulators.py:169-257`

Wraps three mathematical systems: Lorenz attractor, logistic map, and sine superposition.

### 9.5 NetworkSimulator

File: `data_sources/simulators.py:260-343`

Generates network traffic data using a Poisson process with burst events.

**Output fields:**

| Field | Type | Description |
|-------|------|-------------|
| packet_rate | float | Current packet arrival rate |
| packet_count | int | Packets in this tick interval (Poisson distributed) |
| latency_ms | float | Current round-trip latency |
| error_rate | float | Current packet error rate |
| errors | int | Errors in this tick |
| is_burst | bool | Whether a burst is active |
| throughput_mbps | float | Estimated throughput |
| active_edges | list[dict] | Active network connections |
| nodes | list[dict] | Node positions |
| load_level | float | Normalized load (0-1) |

---

## 10. Configuration Reference

### 10.1 Environment Variables

Set in `.env` file (loaded by python-dotenv at startup):

| Variable | Purpose | Default |
|----------|---------|---------|
| `GOOGLE_API_KEY` | Google AI API key for Lyria RealTime | None (uses mock) |
| `ELEVENLABS_API_KEY` | ElevenLabs API key for Music API | None (uses mock) |
| `PORT` | Server port number | 8000 |

### 10.2 Internal Constants

| Constant | Location | Value | Description |
|----------|----------|-------|-------------|
| EMA alpha | `lenses/base.py:83` | 0.15 | Smoothing factor (lower = smoother) |
| Tick rates | Each lens class | 4-10 Hz | Per-lens update rate |
| Audio chunk | `lyria_bridge.py:124` | 2400 frames | Samples per chunk |
| Audio queue (Lyria) | `lyria_bridge.py:180` | max 100 | Queue capacity |
| Audio queue (ElevenLabs) | `elevenlabs_bridge.py:44` | max 200 | Queue capacity |
| Worklet buffer | `static/worklet.js:9` | 5 seconds | Ring buffer capacity |
| ElevenLabs debounce | `elevenlabs_bridge.py:35` | 2.0 seconds | Prompt change debounce |
| ElevenLabs segment | `elevenlabs_bridge.py:51` | 30,000 ms | Generated segment length |
| Weather cache | `data_sources/live_weather.py:15` | 300 seconds | Weather data cache TTL |
| Default location | `data_sources/live_weather.py:17` | 48.8566, 2.3522 | Paris, France |

### 10.3 Tick Rates by Lens

| Lens | tick_hz | Interval | Rationale |
|------|---------|----------|-----------|
| Atmosphere | 4 Hz | 250 ms | Weather changes slowly |
| Pulse | 10 Hz | 100 ms | ECG waveform needs high resolution |
| Lattice | 8 Hz | 125 ms | Lorenz attractor needs smooth animation |
| Flow | 5 Hz | 200 ms | Network traffic is bursty but not sub-second |
