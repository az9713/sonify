# Sonify Developer Guide

A step-by-step guide for developers who are new to web application development. This guide assumes you have experience with C, C++, or Java but have not built a full-stack web application before.

---

## Table of Contents

1. [Prerequisites and Setup](#1-prerequisites-and-setup)
2. [Key Concepts for C/C++/Java Developers](#2-key-concepts-for-ccjava-developers)
3. [Project Structure Walkthrough](#3-project-structure-walkthrough)
4. [Understanding the Python Backend](#4-understanding-the-python-backend)
5. [Understanding the Frontend](#5-understanding-the-frontend)
6. [How to Add a New Lens](#6-how-to-add-a-new-lens)
7. [How to Add a New Audio Backend](#7-how-to-add-a-new-audio-backend)
8. [How to Add a New Parameter to a Lens](#8-how-to-add-a-new-parameter-to-a-lens)
9. [Debugging Techniques](#9-debugging-techniques)
10. [Common Pitfalls and Solutions](#10-common-pitfalls-and-solutions)
11. [Testing Strategies](#11-testing-strategies)
12. [Code Style and Conventions](#12-code-style-and-conventions)

---

## 1. Prerequisites and Setup

### 1.1 Install Python

You need Python 3.10 or later. Check your version:

```bash
python --version
```

If you see "Python 3.10.x" or higher, you are good. If not, download Python from https://www.python.org/downloads/.

On Windows, make sure to check "Add Python to PATH" during installation.

### 1.2 Clone the Repository

```bash
git clone <repository-url>
cd sonify
```

### 1.3 Install Dependencies

```bash
pip install -r requirements.txt
```

This installs six packages:
- `fastapi` -- the web framework (like Spring Boot for Java, but Python)
- `uvicorn` -- the web server that runs FastAPI (like Tomcat for Java)
- `google-genai` -- Google's API client for the Lyria music model
- `elevenlabs` -- ElevenLabs API client for music generation
- `httpx` -- HTTP client for making API calls (like HttpURLConnection in Java)
- `python-dotenv` -- reads `.env` files for configuration

### 1.4 Configure API Keys (Optional)

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```
GOOGLE_API_KEY=your-google-key-here
ELEVENLABS_API_KEY=your-elevenlabs-key-here
```

If you leave both keys blank, the app uses a built-in mock synthesizer. This is perfectly fine for development.

### 1.5 Run the Server

```bash
python server.py
```

You should see:

```
  Sonify running at http://localhost:8000
  Audio mode: Mock (sine wave)
```

Open http://localhost:8000 in your browser and click "Start Experience".

### 1.6 Run on a Different Port

```bash
# Linux/Mac:
PORT=8001 python server.py

# Windows (Command Prompt):
set PORT=8001 && python server.py

# Windows (PowerShell):
$env:PORT=8001; python server.py
```

---

## 2. Key Concepts for C/C++/Java Developers

If you come from C, C++, or Java, some of the technologies in this project may be unfamiliar. This section explains each one by relating it to concepts you already know.

### 2.1 FastAPI (Web Framework)

**What it is:** FastAPI is a Python web framework, similar to Spring Boot (Java) or Express.js (Node.js). It handles HTTP requests and WebSocket connections.

**C/C++ analogy:** Think of it as a socket server where you register callback functions for specific URL paths. Instead of `accept()` + `recv()` + parsing HTTP manually, FastAPI does all of that for you.

**Java analogy:** Like a simplified Spring Boot. Instead of annotations like `@GetMapping("/")`, FastAPI uses decorators like `@app.get("/")`.

**Example from the codebase** (file: `server.py:209-211`):

```python
@app.get("/")
async def index():
    return FileResponse("static/index.html")
```

This says: "When the browser requests `GET /`, serve the file `static/index.html`."

### 2.2 WebSocket

**What it is:** A persistent, full-duplex communication channel between the browser and server. Unlike HTTP (request-response), WebSocket stays open and both sides can send messages at any time.

**C/C++ analogy:** Like a TCP socket that stays connected. After the initial HTTP handshake "upgrades" to WebSocket, you can `send()` and `recv()` freely in both directions, indefinitely.

**Java analogy:** Like a `ServerSocket` that never closes after `accept()`. Both sides can write to the stream whenever they want.

**Why Sonify uses it:** The server needs to push audio data (binary) and visualization data (JSON text) to the browser 20+ times per second. HTTP polling would be too slow. WebSocket gives us a persistent pipe.

**Example from the codebase** (file: `server.py:228-230`):

```python
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    # Now 'ws' is an open bidirectional channel
```

### 2.3 Async/Await (asyncio)

**What it is:** Python's way of doing non-blocking I/O. When you `await` something (like a network read), Python suspends your function and runs other code until the I/O completes.

**C analogy:** Like `select()` or `epoll()` but built into the language. Instead of manually managing a poll loop, you write code that looks sequential but actually yields control during I/O waits.

**Java analogy:** Like `CompletableFuture` or `virtual threads` (Java 21). Instead of one thread per connection, a single thread can handle many connections by switching between them during I/O waits.

**Why it matters for Sonify:** The server manages two concurrent loops (tick loop and audio loop) plus multiple WebSocket connections, all in a single thread. Without async, you would need multi-threading with locks.

**Example from the codebase** (file: `server.py:129-180`):

```python
async def tick_loop() -> None:
    while True:
        # This looks like a blocking loop, but...
        controls, viz = active_lens.update(t)
        await bridge.update(controls)        # Yields here during I/O
        await broadcast_text({...})          # Yields here too
        await asyncio.sleep(interval)        # Yields until timer fires
```

**Key rule:** Any function that uses `await` must be declared with `async def`. Any function declared with `async def` must be `await`ed when called.

### 2.4 DataClass

**What it is:** Python's equivalent of a C `struct` or a Java `record`. A class that holds data fields with no boilerplate.

**Example from the codebase** (file: `lenses/base.py:9-11`):

```python
@dataclass
class ControlState:
    bpm: int = 120
    density: float = 0.5
    brightness: float = 0.5
    # ...
```

This is equivalent to this Java code:

```java
public record ControlState(
    int bpm,
    float density,
    float brightness
    // ...
) {}
```

Or this C code:

```c
typedef struct {
    int bpm;
    float density;
    float brightness;
    // ...
} ControlState;
```

### 2.5 Abstract Base Class (ABC)

**What it is:** Python's equivalent of a Java `interface` or a C++ pure virtual class.

**Example from the codebase** (file: `lenses/base.py:64-121`):

```python
class Lens(abc.ABC):
    @abc.abstractmethod
    def tick(self, t: float) -> dict:
        ...

    @abc.abstractmethod
    def map(self, data: dict) -> ControlState:
        ...
```

This is like Java's:

```java
public abstract class Lens {
    public abstract Map<String, Object> tick(double t);
    public abstract ControlState map(Map<String, Object> data);
}
```

### 2.6 AudioWorklet (Browser Audio Processing)

**What it is:** A browser API for processing audio in a dedicated real-time thread. It runs a small JavaScript processor that fills audio buffers at exactly 48,000 samples per second.

**C analogy:** Like a real-time audio callback function registered with an audio driver (ALSA, WASAPI). The OS calls your function periodically with a buffer to fill, and you must return quickly or audio drops out.

**Key point:** The AudioWorklet runs in a separate thread from the main browser page. Communication happens through `MessagePort` (like a pipe between threads).

**Example from the codebase** (file: `static/worklet.js:40-64`):

```javascript
process(inputs, outputs, parameters) {
    // Called ~375 times/second (48000 / 128)
    // Must fill 128 stereo samples and return within ~2.67ms
    const left = outputs[0][0];
    const right = outputs[0][1];
    for (let i = 0; i < 128; i++) {
        if (this.samplesAvailable >= 2) {
            left[i] = this.buffer[this.readPos];      // Read L
            this.readPos = (this.readPos + 1) % this.bufferSize;
            right[i] = this.buffer[this.readPos];     // Read R
            this.readPos = (this.readPos + 1) % this.bufferSize;
            this.samplesAvailable -= 2;
        } else {
            left[i] = 0;   // Silence on underrun
            right[i] = 0;
        }
    }
    return true;
}
```

### 2.7 Canvas API (Browser 2D Drawing)

**What it is:** A browser API for drawing 2D graphics. You get a drawing context and call methods like `fillRect()`, `arc()`, `lineTo()` -- similar to Java's `Graphics2D` or C's SDL/Cairo.

**Example from the codebase** (file: `static/index.html`, the `renderPulse` function):

```javascript
ctx.beginPath();
ctx.strokeStyle = `rgb(${c.r}, ${c.g}, ${c.b})`;
ctx.lineWidth = 2;
for (let i = 0; i < history.length; i++) {
    const x = i * stepX;
    const y = traceY - history[i] * traceH * 0.5;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
}
ctx.stroke();
```

---

## 3. Project Structure Walkthrough

```
sonify/
|
+-- server.py                     # THE MAIN FILE. Start here.
|                                 # FastAPI app, WebSocket endpoint,
|                                 # tick loop, audio loop, bridge factory.
|
+-- lenses/                       # THE LENS SYSTEM
|   +-- __init__.py               # Exports LENSES dict (name -> class)
|   +-- base.py                   # ControlState dataclass + abstract Lens
|   +-- atmosphere.py             # Weather lens (wind -> BPM, etc.)
|   +-- pulse.py                  # Cardiac lens (HR -> BPM, 1:1)
|   +-- lattice.py                # Math lens (Lorenz chaos -> music)
|   +-- flow.py                   # Network lens (packets -> density)
|
+-- lyria_bridge.py               # Lyria RealTime API wrapper
|                                 # Also contains MockAudioGenerator
|
+-- elevenlabs_bridge.py          # ElevenLabs Music API wrapper
|
+-- data_sources/
|   +-- simulators.py             # Pure-Python simulators for all 4 domains
|   +-- live_weather.py           # Open-Meteo API fetcher
|
+-- static/
|   +-- index.html                # ENTIRE FRONTEND (HTML + CSS + JS)
|   +-- worklet.js                # AudioWorklet processor
|
+-- .env.example                  # Template for API keys
+-- requirements.txt              # Python dependencies
+-- pyproject.toml                # Project metadata
+-- SCIENCE.md                    # Mathematical documentation
+-- CLAUDE.md                     # Instructions for AI coding assistants
```

### Reading Order for New Developers

1. `lenses/base.py` -- understand ControlState and the Lens interface (small file)
2. `lenses/atmosphere.py` -- simplest lens, shows tick/map/viz_state pattern
3. `server.py` -- how lenses and bridges are connected
4. `lyria_bridge.py` -- start at MockAudioGenerator (line 16), then LyriaBridge
5. `static/worklet.js` -- small file, shows how PCM audio reaches speakers
6. `static/index.html` -- the UI and Canvas renderers

---

## 4. Understanding the Python Backend

### 4.1 The Server Entry Point

When you run `python server.py`, execution begins at the bottom of the file:

```python
# server.py:294-301
def main():
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    main()
```

`uvicorn.run("server:app", ...)` tells uvicorn to import the module `server` and find the variable named `app` (which is the FastAPI instance). Uvicorn then starts an HTTP server and routes requests to FastAPI.

### 4.2 The Lifespan Context Manager

FastAPI uses a "lifespan" function for startup/shutdown logic. This is called once when the server starts and once when it stops:

```python
# server.py:39-69
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP (runs once) ---
    active_lens = create_lens("atmosphere")
    await bridge.connect()
    # ... cascade fallback logic ...
    tick_task = asyncio.create_task(tick_loop())    # Start background loop
    audio_task = asyncio.create_task(audio_loop())  # Start background loop
    yield  # <-- Server runs here, handling requests
    # --- SHUTDOWN (runs once) ---
    tick_task.cancel()
    audio_task.cancel()
    await bridge.disconnect()
```

**C analogy:** Think of it as `main()` where you initialize resources, then enter a `while(1)` event loop (that is `yield`), then clean up on exit.

### 4.3 The Two Concurrent Loops

The server runs two asyncio tasks simultaneously:

1. **tick_loop** -- runs at the lens's tick rate (2-10 Hz). Calls the lens, sends results to the bridge and to all WebSocket clients.

2. **audio_loop** -- runs as fast as possible (~every 50ms). Pulls audio chunks from the bridge and sends them as binary frames to all WebSocket clients.

These are not threads. They are coroutines that take turns running on the same thread, yielding control during `await` calls.

### 4.4 The WebSocket Endpoint

```python
# server.py:228-291
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)

    # Send initial state
    await ws.send_text(json.dumps({...}))

    try:
        while True:
            msg = await ws.receive_text()  # Block until client sends
            data = json.loads(msg)
            # Handle commands...
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.remove(ws)
```

Each connected browser gets its own instance of this function running as a coroutine. The `await ws.receive_text()` suspends this coroutine until the client sends a message, allowing other coroutines (tick_loop, audio_loop, other clients) to run.

---

## 5. Understanding the Frontend

### 5.1 Why a Single File?

The entire frontend is in `static/index.html` -- HTML, CSS, and JavaScript all in one file. This is a deliberate simplicity choice. There is no build step, no npm, no webpack, no React. You edit the file and refresh the browser.

### 5.2 The Startup Sequence

When the user clicks "Start Experience":

```javascript
// static/index.html, near line 1021
document.getElementById('start-btn').addEventListener('click', async () => {
    document.getElementById('start-overlay').classList.add('hidden');
    await initAudio();     // 1. Create AudioContext + AudioWorklet
    resizeCanvas();        // 2. Set canvas to fill its container
    initParticles(150);    // 3. Initialize atmosphere particles
    connectWS();           // 4. Open WebSocket to server
    animate();             // 5. Start rendering loop
});
```

This must be triggered by a user click because browsers block audio playback until the user interacts with the page (autoplay policy).

### 5.3 The WebSocket Client

```javascript
function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws`);
    ws.binaryType = 'arraybuffer';  // Receive binary data as ArrayBuffer

    ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
            // Binary frame: PCM audio -> send to AudioWorklet
            workletNode.port.postMessage(event.data, [event.data]);
        } else {
            // Text frame: JSON -> update UI and visualization
            const msg = JSON.parse(event.data);
            // Handle init, paused, or tick messages...
        }
    };
}
```

### 5.4 The Rendering Loop

The `animate()` function runs via `requestAnimationFrame` (the browser's equivalent of a game loop -- typically 60fps):

```javascript
function animate() {
    if (vizState && !isPaused) {
        if (vizState.type === 'atmosphere') renderAtmosphere(vizState);
        else if (vizState.type === 'pulse') renderPulse(vizState);
        // ...
    }
    requestAnimationFrame(animate);  // Schedule next frame
}
```

The `vizState` variable is updated by WebSocket messages. The render loop reads it and draws the appropriate visualization.

---

## 6. How to Add a New Lens

Follow these steps to create a new lens. We will use a "Seismic" lens as an example.

### Step 1: Create the Lens File

Create `lenses/seismic.py`:

```python
"""Seismic lens: earthquake data -> music + waveform visualization."""

from __future__ import annotations

import math
import random

from lenses.base import ControlState, Lens


class SeismicLens(Lens):
    # Required class attributes
    name = "seismic"
    description = "Earthquake tremors as sound"
    tick_hz = 5.0  # Updates per second

    # User-adjustable parameters (shown as sliders in the sidebar)
    parameters = [
        {
            "name": "magnitude",
            "label": "Magnitude (Richter)",
            "min": 0,
            "max": 9,
            "step": 0.1,
            "default": 3.0,
            "effects": [
                "-> BPM: 60 + magnitude * 15 (stronger = faster)",
                "-> Density: magnitude / 9 (stronger = denser)",
            ],
        },
        {
            "name": "depth",
            "label": "Depth (km)",
            "min": 0,
            "max": 700,
            "step": 10,
            "default": 100.0,
            "effects": [
                "-> Brightness: 1.0 - depth/700 (shallow = bright, deep = dark)",
            ],
        },
    ]

    def tick(self, t: float) -> dict:
        """Generate seismic data. Called every 1/tick_hz seconds."""
        mag = self._params["magnitude"]
        depth = self._params["depth"]

        # Add some simulated variation
        tremor = mag + random.gauss(0, 0.2)
        tremor = max(0, min(9, tremor))

        return {
            "magnitude": tremor,
            "depth": depth,
            "wave_value": math.sin(t * (1 + mag * 0.5)) * (mag / 9),
        }

    def map(self, data: dict) -> ControlState:
        """Map seismic data to ControlState. This is deterministic."""
        mag = data["magnitude"]
        depth = data["depth"]

        # Use self._ema() for smooth transitions
        bpm = int(self._ema("bpm", 60 + mag * 15))
        density = self._ema("density", mag / 9)
        brightness = self._ema("brightness", 1.0 - depth / 700)

        # Build prompts based on conditions
        if mag < 3:
            prompts = [{"text": "Ambient, minimal, sub bass", "weight": 1.0}]
        elif mag < 6:
            prompts = [{"text": "Rumbling bass, tension, building", "weight": 1.0}]
        else:
            prompts = [{"text": "Massive impacts, distortion, chaos", "weight": 1.0}]

        return ControlState(
            bpm=bpm,
            density=density,
            brightness=brightness,
            guidance=3.0 + mag * 0.3,
            prompts=prompts,
        )

    def viz_state(self, data: dict) -> dict:
        """Produce JSON for the browser Canvas renderer."""
        mag = data["magnitude"]
        return {
            "type": "seismic",
            "wave_value": data["wave_value"],
            "magnitude": mag,
            "color": {
                "r": min(255, int(mag * 28)),
                "g": max(0, int(200 - mag * 22)),
                "b": 100,
            },
            "data": {
                "magnitude": round(mag, 1),
                "depth": round(data["depth"], 0),
            },
        }
```

### Step 2: Register the Lens

Edit `lenses/__init__.py`:

```python
from .base import Lens, ControlState
from .atmosphere import AtmosphereLens
from .pulse import PulseLens
from .lattice import LatticeLens
from .flow import FlowLens
from .seismic import SeismicLens  # ADD THIS

LENSES: dict[str, type[Lens]] = {
    "atmosphere": AtmosphereLens,
    "pulse": PulseLens,
    "lattice": LatticeLens,
    "flow": FlowLens,
    "seismic": SeismicLens,  # ADD THIS
}
```

### Step 3: Add a Canvas Renderer

In `static/index.html`, add a rendering function and update the `animate()` function:

```javascript
// Add this function alongside the existing renderers:
function renderSeismic(state) {
    const w = canvas.width / devicePixelRatio;
    const h = canvas.height / devicePixelRatio;
    const c = state.color || { r: 200, g: 100, b: 100 };

    // Clear with fade
    ctx.fillStyle = 'rgba(10, 10, 15, 0.1)';
    ctx.fillRect(0, 0, w, h);

    // Draw seismograph line
    const waveY = h / 2 + state.wave_value * h * 0.3;
    ctx.beginPath();
    ctx.arc(w / 2, waveY, 5, 0, Math.PI * 2);
    ctx.fillStyle = `rgb(${c.r}, ${c.g}, ${c.b})`;
    ctx.fill();

    renderDataOverlay(state.data);
}

// In the animate() function, add:
else if (type === 'seismic') renderSeismic(vizState);
```

Also add an icon for the lens button in the `buildLensButtons()` function:

```javascript
const icons = {
    atmosphere: '\u2601',
    pulse: '\u2665',
    lattice: '\u2227',
    flow: '\u21c4',
    seismic: '\u2248',  // ADD THIS (the "approximately equal" symbol)
};
```

### Step 4: Test It

Restart the server (`python server.py`) and refresh the browser. You should see "Seismic" in the lens list.

---

## 7. How to Add a New Audio Backend

If you want to add a new audio generation backend (e.g., a local synthesizer or another API), follow these steps:

### Step 1: Create the Bridge File

Create `mybridge.py`:

```python
"""My custom audio bridge."""

from __future__ import annotations

import asyncio
from lenses.base import ControlState
from lyria_bridge import MockAudioGenerator


class MyBridge:
    """Custom audio bridge. Must implement the same interface as LyriaBridge."""

    def __init__(self) -> None:
        self._connected = False
        self._mock = MockAudioGenerator()  # Fallback

    @property
    def is_mock(self) -> bool:
        return False  # Return True if falling back to mock

    async def connect(self) -> None:
        """Called once at startup. Initialize your audio engine here."""
        self._connected = True

    async def update(self, controls: ControlState) -> None:
        """Called every tick with new control values."""
        # Translate ControlState into your engine's parameters
        pass

    async def get_audio_chunk(self) -> bytes | None:
        """Called ~20 times/second. Return 9600 bytes of PCM or None."""
        # Must return: 2400 frames * 2 channels * 2 bytes = 9600 bytes
        # Format: 16-bit signed little-endian, 48kHz, stereo
        return self._mock.generate_chunk(num_samples=2400)

    async def reset(self) -> None:
        """Called when the user switches lenses."""
        pass

    async def disconnect(self) -> None:
        """Called at shutdown. Clean up resources."""
        self._connected = False
```

### Step 2: Add it to the Bridge Factory

In `server.py`, modify `create_bridge()`:

```python
def create_bridge():
    if os.environ.get("MY_CUSTOM_KEY"):
        from mybridge import MyBridge
        return MyBridge()
    elif os.environ.get("GOOGLE_API_KEY"):
        return LyriaBridge()
    # ... rest of the cascade
```

---

## 8. How to Add a New Parameter to a Lens

To add a new user-adjustable slider to an existing lens:

### Step 1: Add it to the `parameters` list

In the lens file (e.g., `lenses/atmosphere.py`):

```python
parameters = [
    # ... existing parameters ...
    {
        "name": "cloud_cover",
        "label": "Cloud Cover (%)",
        "min": 0,
        "max": 100,
        "step": 5,
        "default": 30.0,
        "effects": [
            "-> Temperature: reduces temperature effect on brightness",
        ],
    },
]
```

### Step 2: Use it in `tick()` and/or `map()`

```python
def tick(self, t: float) -> dict:
    return {
        # ... existing fields ...
        "cloud_cover": self._params["cloud_cover"],
    }

def map(self, data: dict) -> ControlState:
    cloud = data["cloud_cover"]
    # Use cloud_cover to modify your mappings
    # ...
```

The frontend automatically creates a slider for any parameter in the `parameters` list. No frontend changes needed.

---

## 9. Debugging Techniques

### 9.1 Server-Side Debugging

**Add print statements:** The server prints to the terminal. Add `print()` calls anywhere:

```python
# In a lens's map() method:
def map(self, data: dict) -> ControlState:
    print(f"[DEBUG] wind={data['wind_speed']}, computed BPM={bpm}")
    # ...
```

**Watch WebSocket messages:** The server already prints client connect/disconnect events. Add more logging in the WebSocket handler:

```python
# In server.py websocket_endpoint:
print(f"[WS] Received: {data}")
```

### 9.2 Frontend Debugging

**Browser Developer Tools:** Press F12 in your browser to open DevTools.

- **Console tab:** Shows JavaScript errors and `console.log()` output.
- **Network tab:** Shows WebSocket frames (filter by "WS").
- **Elements tab:** Inspect the DOM and CSS.

**Add console.log():**

```javascript
// In the onmessage handler:
ws.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
        console.log('Audio chunk:', event.data.byteLength, 'bytes');
    } else {
        console.log('Message:', JSON.parse(event.data));
    }
};
```

### 9.3 Inspecting Audio

To verify audio data is correct, add a check in the AudioWorklet:

```javascript
// In worklet.js, inside _writeFromPCM16:
if (numSamples > 0) {
    const first = view.getInt16(0, true);
    // Can't use console.log in AudioWorklet, but you can
    // post messages back to the main thread:
    this.port.postMessage({ type: 'debug', firstSample: first, count: numSamples });
}
```

---

## 10. Common Pitfalls and Solutions

### 10.1 "No Sound After Clicking Start"

**Cause:** Browser autoplay policy. The AudioContext starts in "suspended" state.

**Solution:** The code already handles this (`audioCtx.resume()`). If it still does not work, click directly on the page (not just the button) to satisfy the browser's user-gesture requirement.

### 10.2 "ModuleNotFoundError: No module named 'google'"

**Cause:** Dependencies not installed.

**Solution:** Run `pip install -r requirements.txt`.

### 10.3 "Address already in use"

**Cause:** Another process is using port 8000.

**Solution:** Either stop the other process or use a different port:

```bash
PORT=8001 python server.py
```

### 10.4 "WebSocket closes immediately"

**Cause:** The server may be crashing. Check the terminal for error messages.

**Solution:** Look at the server's terminal output. Common causes include missing environment variables or import errors.

### 10.5 "EMA values not updating"

**Cause:** The EMA smoothing factor (alpha=0.15) means values change slowly.

**Solution:** For debugging, temporarily increase alpha in the lens:

```python
self._ema_alpha = 0.5  # Faster response (default is 0.15)
```

### 10.6 "Canvas is Black"

**Cause:** The canvas might not be sized correctly, or `vizState` might be None.

**Solution:** Check that `resizeCanvas()` is called and that the WebSocket is connected and sending messages.

---

## 11. Testing Strategies

The project currently has no automated tests. Here are strategies for testing your changes:

### 11.1 Manual Testing Checklist

When making changes, verify:

1. Server starts without errors
2. Browser connects (badge shows "Connected" or backend name)
3. Each lens can be selected (click all four buttons)
4. Sliders move and affect the visualization
5. Audio plays (you hear something)
6. Play/Pause works
7. Data overlay shows reasonable values
8. Live Weather toggle works (Atmosphere lens only)

### 11.2 Testing a New Lens

1. Start the server, open the browser
2. Click your new lens button
3. Verify the data overlay shows your data fields
4. Move each slider and verify the visualization changes
5. Check the "Lyria Controls" bars -- do BPM, density, brightness, guidance change as expected?
6. Check the "Active Prompts" section -- do prompts change based on your conditions?
7. Listen to the audio -- does it change when you move sliders?

### 11.3 Testing Audio Changes

1. Start with mock audio (no API keys)
2. Move the BPM slider -- does the rhythmic pulse speed up?
3. Change brightness -- does the pitch change?
4. Change density -- does the harmonic richness change?
5. If you have an API key, test with the real backend too

### 11.4 Writing Unit Tests (Future Work)

The lens `map()` functions are pure functions (input data -> ControlState). They are ideal for unit testing:

```python
# Example test (using pytest):
def test_atmosphere_bpm_mapping():
    lens = AtmosphereLens()
    data = {
        "wind_speed": 0,
        "temperature": 20,
        "humidity": 50,
        "rain_probability": 0,
        "pressure": 1013,
    }
    controls = lens.map(data)
    assert 60 <= controls.bpm <= 200
    assert controls.bpm == 70  # wind=0 -> bpm=70
```

---

## 12. Code Style and Conventions

### 12.1 Python

- Use type hints for function signatures (e.g., `def tick(self, t: float) -> dict:`)
- Use `from __future__ import annotations` at the top of every file (allows forward references in type hints)
- Prefix private methods and attributes with underscore (e.g., `_ema_state`, `_build_prompt()`)
- Use print statements prefixed with `[ModuleName]` for logging (e.g., `print("[LyriaBridge] Connected")`)

### 12.2 JavaScript

- All JavaScript is in `static/index.html` (no modules, no build step)
- Global variables are declared at the top of the `<script>` block
- Functions are named in camelCase
- The rendering functions follow a common pattern: clear/fade, draw, overlay

### 12.3 Naming Conventions

- Lens names: lowercase, single word (e.g., "atmosphere", "pulse")
- ControlState fields: snake_case (e.g., `mute_bass`, `mute_drums`)
- WebSocket message types: snake_case (e.g., `switch_lens`, `set_param`)
- CSS classes: kebab-case (e.g., `lens-btn`, `param-group`)

### 12.4 File Organization Rules

- Lenses go in `lenses/` directory, one file per lens
- Audio bridges go in the project root (alongside `server.py`)
- Data sources and simulators go in `data_sources/`
- All frontend code stays in `static/index.html` and `static/worklet.js`
- No build step, no transpilation, no bundling

---

## Quick Reference: Where to Find Things

| I want to...                        | Look in...                           |
|-------------------------------------|--------------------------------------|
| Change how data maps to music       | `lenses/<lens_name>.py`, `map()` method |
| Change the visualization            | `static/index.html`, `render<Lens>()` function |
| Change audio generation             | `lyria_bridge.py` or `elevenlabs_bridge.py` |
| Change the UI layout                | `static/index.html`, `<style>` section |
| Add a new slider parameter          | Lens's `parameters` list + `tick()`/`map()` |
| Change tick rate                    | Lens's `tick_hz` class attribute     |
| Change EMA smoothing speed          | `lenses/base.py:83`, `_ema_alpha`    |
| Change audio chunk size             | `lyria_bridge.py:124`, `num_samples` |
| Change server port                  | `PORT` env var or `server.py:296`    |
| Understand the math                 | `SCIENCE.md`                         |
| Understand the architecture          | `docs/ARCHITECTURE.md`               |
| Run the test suite                  | `python -m pytest tests/ -v`         |

---

## 13. Development History: Parallel Agent Workflow

The frontend redesign, test suite, and this documentation were all developed simultaneously using three Claude Code agents running in parallel, each in an isolated git worktree. This section documents the process for future reference.

### 13.1 What Are Git Worktrees?

Git worktrees allow multiple working directories to share the same repository. Each worktree checks out a different branch, so multiple agents can modify files without interfering with each other. Think of it like having three separate copies of the project that all share the same git history.

### 13.2 The Three Agents

Three agents were launched from a single Claude Code session, each with `isolation: "worktree"`:

**Agent 1: Frontend Redesign**
- Task: Redesign `static/index.html` using the `frontend-design` skill
- Constraint: Preserve all 16 existing features (WebSocket protocol, Canvas visualizers, AudioWorklet, lens switching, sliders, controls readout, backend badge, etc.)
- Result: Industrial-scientific laboratory aesthetic with phosphor green accents, CRT scanline overlay on the canvas viewport, DM Mono typography, segmented meter bars, 2x2 lens grid layout
- Files changed: `static/index.html` only (680 insertions, 202 deletions)
- No Python files were modified

**Agent 2: TDD Test Suite**
- Task: Add a comprehensive pytest test suite covering all modules
- Constraint: Zero modifications to existing source code -- tests validate existing behavior as-is
- Result: 272 tests across 7 test files, all passing in 1.22 seconds
- Files created: `tests/__init__.py`, `tests/conftest.py`, `tests/test_control_state.py`, `tests/test_lenses.py`, `tests/test_simulators.py`, `tests/test_mock_audio.py`, `tests/test_elevenlabs_bridge.py`, `tests/test_server.py`
- Files modified: `requirements.txt` (added pytest, pytest-asyncio), `pyproject.toml` (added dev dependencies and pytest config)

Test breakdown:

| Module | Tests | Coverage |
|--------|-------|----------|
| `test_control_state.py` | 58 | All 9 default field values, `clamped()` enforcement for every field at boundary and extreme values, `diff()` dead-zone thresholds (0.01 for continuous, exact for discrete) |
| `test_lenses.py` | 72 | All 4 lenses: monotone mapping invariants (higher input = higher output), EMA smoothing convergence, prompt generation for all conditions, scale selection by parameter value, `update()` output clamping |
| `test_simulators.py` | 47 | All simulators: expected output keys, value ranges over 500 ticks, seed determinism, Lorenz chaos metric boundaries, Poisson variate correctness (including Gaussian fallback for large lambda), burst logic |
| `test_mock_audio.py` | 22 | PCM format (9600 bytes/chunk, 16-bit signed range), scale quantization to all 4 Lyria scales, all 8 ControlState field mappings (brightness->frequency, density->harmonics, etc.), deterministic output with same seed |
| `test_elevenlabs_bridge.py` | 39 | `_build_prompt()` threshold behavior for BPM (<80/110/140), density (<0.3/>0.7), brightness (<0.3/>0.7), all 4 scale-to-mood mappings, mute flags, temperature thresholds, prompt weight sorting, mono-to-stereo conversion |
| `test_server.py` | 17 | HTTP GET endpoints, WebSocket init message structure, lens switching, parameter setting, pause/play broadcasts, toggle_live, invalid lens handling |

**Agent 3: Documentation**
- Task: Create comprehensive documentation for developers and users
- Constraint: No Python or JavaScript source files modified -- documentation only
- Result: 6 documentation files totaling 3,814 lines
- Files created: `docs/ARCHITECTURE.md` (1,072 lines), `docs/DEVELOPER_GUIDE.md` (980 lines), `docs/USER_GUIDE.md` (585 lines), `docs/API_REFERENCE.md` (763 lines), `CLAUDE.md` (152 lines)
- Files modified: `README.md` (replaced with comprehensive version)

### 13.3 Merge Process

After all three agents completed, their worktree branches were merged into main one at a time:

1. Frontend branch merged cleanly (only touched `static/index.html`)
2. TDD branch merged cleanly (only touched `tests/`, `requirements.txt`, `pyproject.toml`)
3. Documentation branch had a merge conflict in `CLAUDE.md` (both the earlier manual commit and the docs agent created this file). Resolved by taking the docs agent's more comprehensive version and adding the test command.

All worktrees and temporary branches were cleaned up after merging.

### 13.4 Why the Demo Video Shows the Old UI

The demo video in the repository was recorded before the frontend redesign agent ran. The current application uses the new industrial-scientific design, but the video still shows the original layout. All functionality is identical -- only the visual presentation changed.
