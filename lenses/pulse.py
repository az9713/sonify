"""Pulse lens: cardiac data -> music + ECG visualization."""

from __future__ import annotations

import math
import random

from lenses.base import ControlState, Lens


class PulseLens(Lens):
    name = "pulse"
    description = "Your heartbeat becomes a symphony"
    tick_hz = 10.0

    parameters = [
        {
            "name": "heart_rate", "label": "Heart Rate (bpm)",
            "min": 40, "max": 200, "step": 1, "default": 72.0,
            "effects": [
                "\u2192 BPM: 1:1 mapping \u2014 music beats with the heart",
            ],
        },
        {
            "name": "hrv", "label": "HRV (variability)",
            "min": 0, "max": 1, "step": 0.05, "default": 0.5,
            "effects": [
                "\u2192 Density: hrv / 80 (high variability = richer texture)",
            ],
        },
        {
            "name": "stress", "label": "Stress Level",
            "min": 0, "max": 1, "step": 0.05, "default": 0.2,
            "effects": [
                "\u2192 Brightness: 0.3 + stress \u00d7 0.6 (higher stress = brighter)",
                "\u2192 Scale: < 0.5 C Major (calm); > 0.5 Ab minor (tense)",
                "\u2192 Prompts: low = 'meditation ambient'; high = 'tense, ominous drone'",
            ],
        },
        {
            "name": "arrhythmia_chance", "label": "Arrhythmia Chance",
            "min": 0, "max": 0.2, "step": 0.01, "default": 0.0,
            "effects": [
                "\u2192 Prompts: adds 'glitchy effects, weird noises' on arrhythmia events",
            ],
        },
    ]

    def __init__(self) -> None:
        super().__init__()
        self._ecg_history: list[float] = []
        self._max_ecg_history = 300
        self._t = 0.0

    def tick(self, t: float) -> dict:
        self._t = t
        hr = self._params["heart_rate"]
        hrv = self._params["hrv"]
        stress = self._params["stress"]

        rr_interval = 60.0 / hr
        hrv_sdnn = hrv * 80  # 0-80 ms

        # Generate ECG waveform from heart rate
        ecg_value = self._ecg_waveform(t, rr_interval)
        self._ecg_history.append(ecg_value)
        if len(self._ecg_history) > self._max_ecg_history:
            self._ecg_history.pop(0)

        # Random arrhythmia events
        arrhythmia = random.random() < self._params["arrhythmia_chance"]

        return {
            "heart_rate": hr,
            "hrv_sdnn_ms": hrv_sdnn,
            "stress": stress,
            "exercise_level": max(0, (hr - 72) / 128),  # derive from HR for display
            "ecg_value": ecg_value,
            "ecg_history": list(self._ecg_history),
            "arrhythmia": arrhythmia,
        }

    def _ecg_waveform(self, t: float, rr_interval: float) -> float:
        phase = (t % rr_interval) / rr_interval
        if 0.1 < phase < 0.2:
            return 0.15 * math.sin((phase - 0.1) / 0.1 * math.pi)
        if 0.25 < phase < 0.28:
            return -0.1 * ((phase - 0.25) / 0.03)
        if 0.28 < phase < 0.30:
            return -0.1 + 1.2 * ((phase - 0.28) / 0.02)
        if 0.30 < phase < 0.35:
            return 1.1 - 1.3 * ((phase - 0.30) / 0.05)
        if 0.45 < phase < 0.60:
            return 0.25 * math.sin((phase - 0.45) / 0.15 * math.pi)
        return 0.0

    def map(self, data: dict) -> ControlState:
        hr = data["heart_rate"]
        hrv = data["hrv_sdnn_ms"]
        stress = data["stress"]
        arrhythmia = data["arrhythmia"]

        # Heart rate -> BPM (1:1)
        bpm = int(self._ema("bpm", max(60, min(200, hr))))

        # HRV -> Density
        density = self._ema("density", min(1.0, hrv / 80))

        # Stress -> Brightness
        brightness = self._ema("brightness", 0.3 + stress * 0.6)

        prompts = []
        if hr < 80 and stress < 0.3:
            prompts.append({"text": "Meditation, chill, ambient, smooth pianos", "weight": 1.0})
        elif hr > 140:
            prompts.append({"text": "EDM, upbeat, danceable, fat beats", "weight": 1.0})
            prompts.append({"text": "Tight groove, energy", "weight": 0.6})
        elif stress > 0.6:
            prompts.append({"text": "Tense, ominous drone, unsettling", "weight": 1.0})
            prompts.append({"text": "Drum & Bass, dark", "weight": 0.4})
        else:
            prompts.append({"text": "Lo-fi hip hop, chill, warm", "weight": 1.0})

        if arrhythmia:
            prompts.append({"text": "Glitchy effects, weird noises", "weight": 0.7})

        scale = "A_FLAT_MAJOR_F_MINOR" if stress > 0.5 else "C_MAJOR_A_MINOR"

        return ControlState(
            bpm=bpm,
            density=density,
            brightness=brightness,
            guidance=3.5 + stress * 1.5,
            scale=scale,
            prompts=prompts,
        )

    def viz_state(self, data: dict) -> dict:
        hr = data["heart_rate"]
        ecg = data["ecg_value"]

        pulse_size = 0.5 + ecg * 0.5 if ecg > 0.3 else 0.5

        if hr < 100:
            color = {"r": 80, "g": 220, "b": 120}
        elif hr < 140:
            color = {"r": 255, "g": 200, "b": 50}
        else:
            color = {"r": 255, "g": 80, "b": 80}

        return {
            "type": "pulse",
            "ecg_history": data["ecg_history"][-200:],
            "ecg_current": ecg,
            "pulse_size": pulse_size,
            "color": color,
            "arrhythmia": data["arrhythmia"],
            "data": {
                "heart_rate": round(hr, 1),
                "hrv_sdnn_ms": round(data["hrv_sdnn_ms"], 1),
                "stress": round(data["stress"], 2),
            },
        }
