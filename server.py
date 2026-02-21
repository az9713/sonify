"""Sonify — FastAPI server with WebSocket hub and tick loop.

Run: python server.py
Open: http://localhost:8000
"""

from __future__ import annotations

import asyncio
import json
import os
import time

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from lenses import LENSES, Lens
from lyria_bridge import LyriaBridge
from elevenlabs_bridge import ElevenLabsBridge
from data_sources.live_weather import LiveWeatherFetcher


def create_bridge():
    """Select the best available audio backend: Lyria > ElevenLabs > Mock."""
    if os.environ.get("GOOGLE_API_KEY"):
        return LyriaBridge()
    elif os.environ.get("ELEVENLABS_API_KEY"):
        return ElevenLabsBridge()
    else:
        return LyriaBridge()  # falls back to mock internally


@asynccontextmanager
async def lifespan(app: FastAPI):
    global tick_task, audio_task, active_lens, bridge
    active_lens = create_lens(active_lens_name)
    await bridge.connect()

    # Cascade: if Lyria failed to mock but an ElevenLabs key exists, try that
    if (bridge.is_mock
            and isinstance(bridge, LyriaBridge)
            and os.environ.get("ELEVENLABS_API_KEY")):
        print("[Startup] Lyria unavailable, trying ElevenLabs...")
        await bridge.disconnect()
        bridge = ElevenLabsBridge()
        await bridge.connect()

    tick_task = asyncio.create_task(tick_loop())
    audio_task = asyncio.create_task(audio_loop())
    if bridge.is_mock:
        mode = "Mock (sine wave)"
    elif isinstance(bridge, ElevenLabsBridge):
        mode = "ElevenLabs Music"
    else:
        mode = "Lyria RealTime"
    print(f"\n  Sonify running at http://localhost:8000")
    print(f"  Audio mode: {mode}\n")
    yield
    if tick_task:
        tick_task.cancel()
    if audio_task:
        audio_task.cancel()
    await bridge.disconnect()


app = FastAPI(title="Sonify", lifespan=lifespan)

# Global state
bridge = create_bridge()
active_lens: Lens | None = None
active_lens_name: str = "atmosphere"
connected_clients: list[WebSocket] = []
weather_fetcher = LiveWeatherFetcher()
tick_task: asyncio.Task | None = None
audio_task: asyncio.Task | None = None
use_live_weather: bool = False
paused: bool = False


def get_backend_name() -> str:
    """Return a short backend identifier for the frontend."""
    if bridge.is_mock:
        return "mock"
    elif isinstance(bridge, ElevenLabsBridge):
        return "elevenlabs"
    else:
        return "lyria"


def create_lens(name: str) -> Lens:
    """Create a lens instance by name."""
    cls = LENSES.get(name)
    if cls is None:
        cls = LENSES["atmosphere"]
    return cls()


async def broadcast_text(data: dict) -> None:
    """Send JSON text frame to all connected clients."""
    msg = json.dumps(data)
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)


async def broadcast_binary(data: bytes) -> None:
    """Send binary frame (PCM audio) to all connected clients."""
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_bytes(data)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)


async def tick_loop() -> None:
    """Main tick loop: updates lens, sends controls + viz to clients."""
    global active_lens, use_live_weather, paused
    t0 = time.time()

    while True:
        if active_lens is None or not connected_clients or paused:
            await asyncio.sleep(0.1)
            continue

        t = time.time() - t0
        hz = active_lens.tick_hz
        interval = 1.0 / hz

        try:
            # Fetch live weather if enabled for atmosphere lens
            if (active_lens.name == "atmosphere" and use_live_weather):
                live_data = await weather_fetcher.fetch()
                if live_data:
                    active_lens.set_live_data(live_data)

            # Tick the lens
            controls, viz = active_lens.update(t)

            # Send controls to Lyria bridge
            await bridge.update(controls)

            # Build control readout for UI
            controls_readout = {
                "bpm": controls.bpm,
                "density": round(controls.density, 2),
                "brightness": round(controls.brightness, 2),
                "guidance": round(controls.guidance, 2),
                "scale": controls.scale,
                "prompts": controls.prompts,
                "mute_bass": controls.mute_bass,
                "mute_drums": controls.mute_drums,
            }

            # Send text frame with viz + controls
            await broadcast_text({
                "viz": viz,
                "controls": controls_readout,
                "lens": active_lens.name,
                "is_mock": bridge.is_mock,
                "backend": get_backend_name(),
            })

        except Exception as e:
            print(f"[TickLoop] Error: {e}")

        await asyncio.sleep(interval)


async def audio_loop() -> None:
    """Audio streaming loop: gets audio from bridge, sends to clients."""
    global paused
    while True:
        if not connected_clients or paused:
            await asyncio.sleep(0.1)
            continue

        try:
            chunk = await bridge.get_audio_chunk()
            if chunk:
                await broadcast_binary(chunk)
        except Exception as e:
            print(f"[AudioLoop] Error: {e}")

        # ~50ms chunks for smooth streaming
        if bridge.is_mock:
            await asyncio.sleep(0.05)
        else:
            await asyncio.sleep(0.01)


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/api/lenses")
async def get_lenses():
    """Return available lenses and their parameters."""
    result = {}
    for name, cls in LENSES.items():
        lens = cls()
        result[name] = {
            "name": name,
            "description": lens.description,
            "parameters": lens.parameters,
        }
    return result


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global active_lens, active_lens_name, use_live_weather, paused

    await ws.accept()
    connected_clients.append(ws)
    print(f"[WS] Client connected. Total: {len(connected_clients)}")

    # Send initial state
    await ws.send_text(json.dumps({
        "type": "init",
        "lens": active_lens_name,
        "lenses": {
            name: {"description": cls().description, "parameters": cls().parameters}
            for name, cls in LENSES.items()
        },
        "is_mock": bridge.is_mock,
        "backend": get_backend_name(),
        "paused": paused,
    }))

    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            if data.get("type") == "switch_lens":
                new_lens = data.get("lens", "atmosphere")
                if new_lens in LENSES and new_lens != active_lens_name:
                    active_lens_name = new_lens
                    active_lens = create_lens(new_lens)
                    await bridge.reset()
                    print(f"[WS] Switched to lens: {new_lens}")

            elif data.get("type") == "set_param":
                name = data.get("name")
                value = data.get("value")
                if active_lens and name is not None and value is not None:
                    active_lens.set_param(name, float(value))

            elif data.get("type") == "pause":
                paused = True
                await broadcast_text({"type": "paused", "paused": True})
                print("[WS] Paused")

            elif data.get("type") == "play":
                paused = False
                await broadcast_text({"type": "paused", "paused": False})
                print("[WS] Playing")

            elif data.get("type") == "toggle_live":
                use_live_weather = data.get("enabled", False)
                if not use_live_weather and active_lens and active_lens.name == "atmosphere":
                    active_lens.set_live_data(None)
                print(f"[WS] Live weather: {use_live_weather}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        if ws in connected_clients:
            connected_clients.remove(ws)
        print(f"[WS] Client disconnected. Total: {len(connected_clients)}")


def main():
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
