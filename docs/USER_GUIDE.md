# Sonify User Guide

Welcome to Sonify -- a platform that turns abstract data into music and visualizations. This guide will walk you through everything you need to get started, from installation to exploring all of Sonify's features through hands-on exercises.

---

## Table of Contents

1. [What is Sonify?](#1-what-is-sonify)
2. [Installation](#2-installation)
3. [First Launch](#3-first-launch)
4. [Understanding the Interface](#4-understanding-the-interface)
5. [The Four Lenses](#5-the-four-lenses)
6. [Quick Start: 10 Educational Use Cases](#6-quick-start-10-educational-use-cases)
7. [Working with API Keys (Advanced Audio)](#7-working-with-api-keys-advanced-audio)
8. [Live Weather Mode](#8-live-weather-mode)
9. [Troubleshooting](#9-troubleshooting)
10. [Glossary](#10-glossary)

---

## 1. What is Sonify?

Sonify converts data into music. It takes numbers -- like temperature, heart rate, mathematical equations, or network traffic -- and translates them into sound and visuals in real time. This process is called **sonification**.

Every slider you move changes the underlying data, which changes the music and the visuals simultaneously. The connection between data and sound is always deterministic: the same data always produces the same sound.

**Why is this useful?**
- You can "hear" patterns in data that might be hard to see in a graph
- It makes abstract concepts (like chaos theory or network congestion) tangible
- It is a different way to explore and understand data

**Three Audio Modes:**
1. **Lyria RealTime** -- Google's AI music model (requires API key). Best quality, real-time response.
2. **ElevenLabs Music** -- AI-generated music from text descriptions (requires API key). Good quality, slight delay on changes.
3. **Mock (sine wave)** -- Built-in synthesizer. No API key needed. Works immediately. Still responds to 8 out of 9 control parameters.

---

## 2. Installation

### Step 1: Install Python

Download Python 3.10 or later from https://www.python.org/downloads/.

**Important for Windows users:** During installation, check the box that says **"Add Python to PATH"**.

Verify the installation by opening a terminal (Command Prompt, PowerShell, or Terminal) and typing:

```
python --version
```

You should see something like `Python 3.10.12` or higher.

### Step 2: Download Sonify

If you received Sonify as a zip file, extract it to a folder. If using git:

```
git clone <repository-url>
```

### Step 3: Open a Terminal in the Sonify Folder

Navigate to the Sonify folder:

```
cd path/to/sonify
```

### Step 4: Install Dependencies

```
pip install -r requirements.txt
```

This downloads and installs all the Python packages Sonify needs. It may take a minute.

### Step 5: Start Sonify

```
python server.py
```

You should see:

```
  Sonify running at http://localhost:8000
  Audio mode: Mock (sine wave)
```

### Step 6: Open the Browser

Open your web browser (Chrome, Firefox, or Edge) and go to:

```
http://localhost:8000
```

You should see the Sonify interface with a "Start Experience" button in the center.

---

## 3. First Launch

When you first open Sonify, you will see a dark screen with the text "Sonify" and a purple "Start Experience" button.

**Click the "Start Experience" button.** This is required because browsers do not allow web pages to play audio until you interact with them.

After clicking, you will see:
- A **sidebar** on the left with controls
- A **visualization** in the center (colored particles moving across a dark background)
- A **data overlay** in the top-right corner showing real-time values
- A **status badge** in the top-right showing your audio mode (e.g., "Mock Audio")

You should hear a tone. If you do not hear anything, check that your computer's volume is up and that the badge says "Mock Audio" (or another mode).

---

## 4. Understanding the Interface

```
+--------------------------------------------------------------+
| Son[ify]                               [Play/Pause] [Badge]  |
+------+-------------------------------------------------+-----+
|      |                                                 |     |
| LENS |                                                 | data|
|      |          VISUALIZATION                          | over|
| [A]  |          (Canvas)                               | lay |
| [P]  |                                                 |     |
| [L]  |                                                 |     |
| [F]  |                                                 |     |
|      |                                                 |     |
+------+                                                 +-----+
|      |                                                       |
| PARA-|                                                       |
| METERS                                                       |
| [===]|                                                       |
| [===]|                                                       |
| [===]|                                                       |
+------+                                                       |
|      |                                                       |
| LYRIA|                                                       |
| CTRL |                                                       |
| BPM  |                                                       |
| Dens |                                                       |
| Brght|                                                       |
| Guide|                                                       |
+------+                                                       |
| PROMPT                                                       |
| [tag]|                                                       |
+------+-------------------------------------------------------+
```

### Header Bar

- **Sonify** -- the application title
- **Play/Pause button** (circle icon) -- stops or resumes the sonification
- **Status badge** -- shows the active audio backend:
  - Green "Lyria RealTime" -- using Google's AI model
  - Blue "ElevenLabs Music" -- using ElevenLabs' AI model
  - Yellow "Mock Audio" -- using the built-in synthesizer

### Sidebar Sections

1. **Lens** -- Four buttons to switch between data domains:
   - **Atmosphere** -- weather data
   - **Pulse** -- cardiac/heart data
   - **Lattice** -- mathematical attractors
   - **Flow** -- network traffic

2. **Parameters** -- Sliders specific to the active lens. Each slider shows:
   - Its name and current value
   - A description of what it affects (shown below the slider)

3. **Lyria Controls** -- Real-time readout of the audio control parameters:
   - **BPM** -- beats per minute (tempo)
   - **Density** -- how many musical layers play simultaneously
   - **Brightness** -- timbral brightness (dark vs. bright tone)
   - **Guidance** -- how tightly the AI follows its instructions

4. **Active Prompts** -- Text descriptions sent to the AI audio engine. These change based on the data. In mock mode, prompts have no audible effect.

### Visualization Area

The large central area shows a real-time visualization that is synchronized with the audio. Each lens has a different visualization:
- **Atmosphere** -- colored particles flowing across the screen
- **Pulse** -- an ECG (heart monitor) trace with a pulsing circle
- **Lattice** -- animated mathematical curves (Lorenz attractor, logistic map, or sine waves)
- **Flow** -- a network graph with nodes and animated packet flows

### Data Overlay

The top-right corner shows raw data values from the current simulation, updated in real time.

---

## 5. The Four Lenses

### Atmosphere Lens

**What it does:** Converts weather conditions into music. Wind drives tempo, temperature drives timbral brightness, humidity drives textural density, and rain adds piano arpeggios.

**Parameters:**
- **Wind Speed (m/s)** -- 0 to 30. Higher wind = faster tempo.
- **Temperature (C)** -- -10 to 40. Cold = dark tone, hot = bright tone.
- **Humidity (%)** -- 0 to 100. Dry = sparse music, humid = dense layers.
- **Rain Intensity** -- 0 to 1. Above 0.3, piano arpeggios appear.
- **Pressure (hPa)** -- 980 to 1040. Affects visualization only.

**Special feature:** A "Live Weather" toggle that fetches real weather data from Paris, France via the Open-Meteo API (free, no key needed).

### Pulse Lens

**What it does:** Converts cardiac data into music. The music literally beats with the simulated heart. This lens updates at 10 Hz (the fastest) to capture the ECG waveform detail.

**Parameters:**
- **Heart Rate (bpm)** -- 40 to 200. Directly maps to musical BPM (1:1).
- **HRV (variability)** -- 0 to 1. Higher variability = richer musical texture.
- **Stress Level** -- 0 to 1. Above 0.5, the musical key shifts to a darker mode.
- **Arrhythmia Chance** -- 0 to 0.2. Probability of irregular heartbeats, which trigger glitch effects.

### Lattice Lens

**What it does:** Converts mathematical systems into music. The default mode shows the Lorenz attractor, a chaotic system that produces the famous "butterfly" pattern. As chaos increases, the music becomes more complex and experimental.

**Parameters:**
- **Chaos (rho)** -- 0 to 1. Controls the main bifurcation parameter. Low = orderly piano, high = experimental glitch.
- **Sigma** -- 1 to 30. A Lorenz system parameter affecting attractor shape.
- **Beta** -- 0.5 to 8. Another Lorenz parameter affecting attractor shape.
- **Speed** -- 0.1 to 3. How fast the attractor animates.
- **Mode** -- 0 = Lorenz attractor, 0.5 = Logistic map, 1 = Sine wave superposition.

### Flow Lens

**What it does:** Converts network traffic into music. Packet rates drive density, latency drives brightness (inverse), and traffic bursts cause tempo spikes.

**Parameters:**
- **Packet Rate (/s)** -- 1 to 200. Higher rate = denser music.
- **Latency (ms)** -- 1 to 200. Higher latency = darker, muddier tone.
- **Burst Active** -- 0 or 1. Triggers a traffic burst (tempo spike + distortion).
- **Error Rate** -- 0 to 0.2. Above 0.05, glitch effects appear.
- **Node Count** -- 3 to 16. Number of nodes in the network visualization.

---

## 6. Quick Start: 10 Educational Use Cases

These exercises are designed to give you quick wins and build your understanding of how data maps to sound. Each exercise takes 2-5 minutes.

---

### Use Case 1: "Hear the Wind"

**Goal:** Understand how a single parameter (wind speed) controls musical tempo.

**Steps:**
1. Make sure you are on the **Atmosphere** lens (click it in the sidebar if not)
2. Set all sliders to their defaults (or leave them as they are)
3. Slowly drag the **Wind Speed** slider from 0 to 30
4. Watch the **BPM** bar in the "Lyria Controls" section
5. Listen to how the rhythmic pulse speeds up as wind increases

**What you learn:** Wind speed of 0 gives a slow 70 BPM. Wind speed of 30 gives a fast 180 BPM. The relationship is linear: every 1 m/s of wind adds about 3.7 BPM. You can hear the tempo change gradually because of the smoothing filter.

---

### Use Case 2: "Hot and Cold"

**Goal:** Understand how temperature maps to timbral brightness.

**Steps:**
1. Stay on the **Atmosphere** lens
2. Set Wind Speed to about 5 (so you have a gentle rhythm)
3. Drag the **Temperature** slider from -10 to 40
4. Watch the **Brightness** bar change
5. Listen for the tone shifting from dark/muffled to bright/sharp
6. Notice the visualization color changing from blue (cold) to warm orange (hot)

**What you learn:** At -10 C, brightness is 0 (dark tone). At 40 C, brightness is 1.0 (bright tone). Cold temperatures produce muffled, warm-sounding tones. Hot temperatures produce sharp, bright tones. The particles on screen also change color from blue to orange, driven by the same temperature data.

---

### Use Case 3: "Storm Builder"

**Goal:** See how multiple parameters combine to create compound musical effects.

**Steps:**
1. Stay on the **Atmosphere** lens
2. Start with calm conditions: Wind=5, Temperature=20, Humidity=30, Rain=0
3. Slowly increase **Rain Intensity** past 0.3. Watch the "Active Prompts" section -- "Piano arpeggios" appears
4. Increase **Wind Speed** to 20. Watch the prompts -- "Spacey synths, wind" appears
5. With Wind > 20 and Rain > 0.5, a third prompt appears: "Dirty synths, crunchy distortion, ominous drone"
6. Meanwhile, increase **Humidity** to 80. The music becomes denser (more layers)

**What you learn:** Each parameter independently affects a different musical dimension. But some effects are compound -- the "storm" prompt only appears when BOTH wind > 20 AND rain > 0.5. This mirrors real weather: a storm is not just wind or rain alone, but both together.

---

### Use Case 4: "Your Heartbeat in Music"

**Goal:** Experience the 1:1 mapping between heart rate and musical tempo.

**Steps:**
1. Switch to the **Pulse** lens
2. Set **Heart Rate** to 72 (a typical resting heart rate)
3. Listen to the rhythm -- it pulses at 72 beats per minute
4. Watch the ECG trace on screen -- it sweeps from left to right
5. Slowly increase Heart Rate to 120 (moderate exercise)
6. Listen to the tempo increase -- the music speeds up in lockstep
7. Push Heart Rate to 180 (intense exercise). The music becomes fast and energetic
8. Watch the ECG trace speed up at the same rate

**What you learn:** This is the most direct mapping in Sonify. Musical BPM equals Heart Rate BPM. The music literally beats with the simulated heart. The ECG visualization and the audio tempo are driven by the exact same data.

---

### Use Case 5: "Stress and Musical Mood"

**Goal:** Hear how stress changes musical key (major vs. minor) and mood.

**Steps:**
1. Stay on the **Pulse** lens
2. Set Heart Rate to 72, HRV to 0.5, and **Stress Level** to 0
3. Note the prompt: "Meditation, chill, ambient" and the scale indicator
4. Slowly increase **Stress Level** past 0.5
5. Listen for the musical key change -- the tonality shifts to a darker mode (Ab Major / F minor)
6. Watch the Brightness bar increase as stress rises
7. Push Stress to 1.0 -- the prompt changes to "Tense, ominous drone"
8. Notice how the visualization color shifts from green (calm) to red (stressed)

**What you learn:** Stress below 0.5 produces C Major (bright, uplifting). Stress above 0.5 shifts to Ab Major / F minor (dark, tense). This is a discrete transition -- a threshold crossing, not a gradual shift. The musical mood reflects the stress state.

---

### Use Case 6: "Chaos Theory in Sound"

**Goal:** Hear the transition from order to chaos in the Lorenz system.

**Steps:**
1. Switch to the **Lattice** lens
2. Make sure Mode is at 0 (Lorenz attractor)
3. Set **Chaos** to 0.1 (very low). Watch the attractor visualization -- it traces a simple, repeating path
4. Listen -- the music is calm, orderly piano with slow tempo
5. Slowly increase **Chaos** to 0.5. The attractor becomes more complex, the music gets faster and jazzier
6. Push **Chaos** to 0.9. The attractor becomes a wild, space-filling butterfly pattern
7. Listen -- the music is now fast, glitchy, and experimental. The key has shifted to Gb Major (the most distant key from C)

**What you learn:** The chaos slider controls the Lorenz system's rho parameter (rho = 10 + 35 * chaos). Around chaos = 0.4-0.5, the system transitions from periodic orbits to genuine mathematical chaos. You can HEAR this transition: orderly piano becomes frantic glitch. The transition mirrors the mathematical bifurcation.

---

### Use Case 7: "The Three Mathematical Modes"

**Goal:** Compare three different mathematical systems and their sounds.

**Steps:**
1. Stay on the **Lattice** lens
2. Set Chaos to 0.7 (moderately chaotic)
3. The Mode slider has three positions: 0 (Lorenz), 0.5 (Logistic), 1.0 (Sine)
4. Start at **Mode = 0** (Lorenz). You see the butterfly attractor, hear atmospheric chaos
5. Move to **Mode = 0.5** (Logistic map). You see the iteration graph. The prompt adds "Minimal techno, precise, electronic"
6. Move to **Mode = 1.0** (Sine superposition). You see overlapping sine waves. The prompt adds "Ambient, dreamy, sine tones"
7. In each mode, try moving the Chaos slider and notice how the chaos metric and the sound change differently

**What you learn:** Different mathematical systems produce different kinds of chaos. The Lorenz system is a continuous flow with sudden lobe switches. The logistic map is a discrete iteration with period-doubling. The sine superposition is always smooth but becomes complex with many incommensurate frequencies. Each produces a different musical texture despite using the same ControlState mapping.

---

### Use Case 8: "Network Under Load"

**Goal:** Understand how network conditions map to musical characteristics.

**Steps:**
1. Switch to the **Flow** lens
2. Start with **Packet Rate** at 10 (light traffic). The music is sparse, ambient
3. Increase Packet Rate to 100. Watch the density bar rise. The music becomes fuller
4. Push Packet Rate to 200 (maximum). The music is dense and energetic ("Drum & Bass, intense")
5. Now increase **Latency** from 10 to 200. Watch brightness drop. The tone becomes dark and muddy
6. Reset Latency to 50 and set **Error Rate** above 0.05. "Glitchy effects, metallic twang" appears in the prompts
7. Watch the network graph visualization -- more connections appear at higher packet rates

**What you learn:** Network traffic maps intuitively to music: more traffic = more musical density, higher latency = darker sound (sluggish network = muddy audio), errors = glitches. The visualization shows the network topology with animated packet flows.

---

### Use Case 9: "The Burst Effect"

**Goal:** Experience the dramatic musical impact of a network traffic burst.

**Steps:**
1. Stay on the **Flow** lens
2. Set Packet Rate to 50, Latency to 30, Error Rate to 0.02 (normal conditions)
3. Note the BPM (should be around 90-100)
4. Toggle **Burst Active** from 0 to 1
5. Watch what happens:
   - BPM jumps by 50 (tempo spike)
   - The prompt gains "Huge drop, intense, crunchy distortion"
   - The visualization turns red
   - The node graph pulses more intensely
6. Toggle Burst back to 0 and notice the gradual recovery (EMA smoothing)

**What you learn:** A burst is a compound event: it simultaneously affects tempo (+50 BPM), prompts (distortion), and visuals (red alert). Notice that turning OFF the burst does not snap the BPM back instantly -- the EMA smoothing causes a gradual 2-3 second recovery. This is intentional: sudden audio changes are jarring, so the system absorbs them over time.

---

### Use Case 10: "Arrhythmia Detection"

**Goal:** Hear cardiac arrhythmias as musical glitch events.

**Steps:**
1. Switch to the **Pulse** lens
2. Set Heart Rate to 72, HRV to 0.5, Stress to 0.2 (calm baseline)
3. Set **Arrhythmia Chance** to 0 -- listen to the steady rhythm
4. Increase Arrhythmia Chance to 0.05 (5% chance per tick)
5. Watch the ECG trace -- occasional irregular beats appear (the screen briefly flashes red)
6. Listen for occasional "glitch" sounds in the audio (when using Lyria or ElevenLabs)
7. Watch the "Active Prompts" -- "Glitchy effects, weird noises" appears intermittently
8. Increase to 0.15 -- arrhythmias become frequent and the music becomes unstable
9. Set back to 0 and notice the rhythm stabilizes

**What you learn:** Arrhythmias are modeled as random events. Each tick has a probability (set by the slider) of triggering an arrhythmia. When one occurs, a glitch prompt is injected. In mock mode, the prompt has no effect on the audio, but the ECG visualization still shows the irregular beat. With Lyria or ElevenLabs, you hear actual glitch effects.

---

## 7. Working with API Keys (Advanced Audio)

The mock audio (sine wave synthesizer) responds to 8 of 9 ControlState fields. For the full experience including AI-generated music that responds to text prompts ("piano arpeggios", "glitchy effects", etc.), you need an API key.

### Getting a Google API Key (for Lyria RealTime)

1. Go to https://aistudio.google.com/apikey
2. Sign in with your Google account
3. Click "Create API key"
4. Copy the key

### Getting an ElevenLabs API Key

1. Go to https://elevenlabs.io
2. Create an account (free tier available)
3. Navigate to your Profile > API Keys
4. Copy the key

### Setting Up Your Keys

1. In the Sonify folder, copy `.env.example` to `.env`:

```
cp .env.example .env
```

2. Open `.env` in a text editor and replace the placeholder values:

```
GOOGLE_API_KEY=your-actual-google-key
ELEVENLABS_API_KEY=your-actual-elevenlabs-key
```

3. Restart the server:

```
python server.py
```

The status badge in the browser will show which backend is active:
- Green "Lyria RealTime" -- best quality
- Blue "ElevenLabs Music" -- good quality with text-prompt responsiveness
- Yellow "Mock Audio" -- no key needed

### Priority Order

The server tries backends in this order:
1. If `GOOGLE_API_KEY` is set, try Lyria first
2. If Lyria fails (e.g., no Vertex AI access), try ElevenLabs (if key is set)
3. If neither works, fall back to the mock synthesizer

### Cost Note

Both Lyria and ElevenLabs APIs may incur costs depending on your usage and plan. The mock synthesizer is completely free and still responds meaningfully to most ControlState parameters.

---

## 8. Live Weather Mode

The Atmosphere lens can fetch real weather data from the internet instead of using the sliders.

### How to Enable

1. Switch to the **Atmosphere** lens
2. In the Parameters section, find the **Live Weather** toggle at the bottom
3. Turn it on

When enabled:
- The sliders become overridden by real weather data from Paris, France
- Data is fetched from the Open-Meteo API (free, no key required)
- Data updates every 5 minutes (cached to avoid excessive API calls)
- The data overlay shows actual current weather values

When you turn it off, the sliders resume control.

### What You Hear

With live weather, the music reflects actual current conditions:
- A windy day in Paris produces faster tempo
- A cold day produces darker tones
- Rain produces piano arpeggios
- High humidity produces denser musical texture

---

## 9. Troubleshooting

### "I don't hear any sound"

1. Make sure you clicked "Start Experience" (browser autoplay policy)
2. Check your computer's volume
3. Check the status badge -- does it say "Connected" or show a backend name?
4. Try clicking anywhere on the page, then pressing Play

### "The server won't start"

1. Check that Python 3.10+ is installed: `python --version`
2. Check that dependencies are installed: `pip install -r requirements.txt`
3. Check that port 8000 is not in use. Try: `PORT=8001 python server.py`

### "The badge says 'Disconnected'"

The WebSocket connection to the server has dropped. This can happen if:
- The server was stopped
- There was a network issue

The client automatically tries to reconnect every 2 seconds. If the server is running, it should reconnect.

### "I set my API key but it still shows Mock Audio"

1. Make sure the key is in a file named `.env` (not `.env.example`)
2. Make sure the variable names are exactly `GOOGLE_API_KEY` or `ELEVENLABS_API_KEY`
3. Restart the server after changing `.env`
4. Check the server's terminal output for error messages

### "ElevenLabs audio has a delay"

This is normal. The ElevenLabs backend generates 30-second audio segments. The first segment takes 5-15 seconds to generate. After that, segments are generated in the background for gapless playback.

When you move sliders, prompt changes are debounced (delayed 2 seconds) to avoid overwhelming the API. The current segment always finishes playing before the new one starts.

### "The audio stutters or has gaps"

This can happen if:
- Your internet connection is slow (for API-based backends)
- The server is under heavy CPU load
- Multiple browser tabs are connected to the same server

Try closing other tabs or reducing the browser's load.

---

## 10. Glossary

| Term | Meaning |
|------|---------|
| **Sonification** | The process of converting data into sound |
| **Lens** | A Sonify module that maps a specific data domain (weather, cardiac, etc.) to music |
| **ControlState** | The set of 9 parameters that control the audio engine (BPM, density, brightness, etc.) |
| **BPM** | Beats Per Minute -- the tempo of the music |
| **Density** | How many simultaneous musical voices/layers are playing (0=sparse, 1=rich) |
| **Brightness** | The timbral quality of the sound (0=dark/muffled, 1=bright/sharp) |
| **Guidance** | How closely the AI follows its text prompts (0=creative freedom, 6=strict adherence) |
| **Scale** | The musical key/mode (e.g., C Major, Ab Major) |
| **Prompts** | Text descriptions sent to the AI audio engine (e.g., "Piano arpeggios, gentle") |
| **Temperature** | How random/experimental the AI's output is (0=predictable, 3=wild) |
| **EMA** | Exponential Moving Average -- a smoothing filter that prevents jarring audio changes |
| **PCM** | Pulse Code Modulation -- raw digital audio data (no compression) |
| **WebSocket** | A persistent network connection between the browser and server |
| **AudioWorklet** | A browser API for real-time audio processing |
| **Mock Audio** | The built-in sine-wave synthesizer used when no API keys are configured |
| **Lyria RealTime** | Google's AI music generation model |
| **ElevenLabs Music** | ElevenLabs' AI music generation API |
| **Lorenz Attractor** | A mathematical system that produces chaotic, butterfly-shaped trajectories |
| **Logistic Map** | A simple equation that produces chaos through period-doubling |
| **Poisson Process** | A mathematical model for random events (used for network traffic simulation) |
| **HRV** | Heart Rate Variability -- the beat-to-beat variation in heart rhythm |
| **ECG** | Electrocardiogram -- the electrical signal of the heart |
| **Arrhythmia** | An irregular heartbeat |
