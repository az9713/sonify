"""Atmosphere lens: weather data -> music + particle field visualization."""

from __future__ import annotations

from data_sources.simulators import WeatherSimulator
from lenses.base import ControlState, Lens


class AtmosphereLens(Lens):
    name = "atmosphere"
    description = "Weather patterns become sound and light"
    tick_hz = 4.0

    parameters = [
        {
            "name": "wind_speed", "label": "Wind Speed (m/s)",
            "min": 0, "max": 30, "step": 0.5, "default": 5.0,
            "effects": [
                "\u2192 BPM: 70 + wind \u00d7 3.67 (faster wind = faster tempo)",
                "\u2192 Prompts: adds 'sweeping synths' when > 15 m/s",
                "\u2192 Prompts: adds 'distorted drone' when > 20 m/s AND rain > 0.5",
            ],
        },
        {
            "name": "temperature", "label": "Temperature (C)",
            "min": -10, "max": 40, "step": 1, "default": 20.0,
            "effects": [
                "\u2192 Brightness: (temp + 10) / 50 (cold = dim, hot = bright)",
                "\u2192 Prompts: < 5\u00b0C 'ethereal, cold chords'; > 30\u00b0C 'warm acoustic guitar'",
            ],
        },
        {
            "name": "humidity", "label": "Humidity (%)",
            "min": 0, "max": 100, "step": 1, "default": 50.0,
            "effects": [
                "\u2192 Density: humidity / 100 (dry = sparse, humid = thick layers)",
            ],
        },
        {
            "name": "rain", "label": "Rain Intensity",
            "min": 0, "max": 1, "step": 0.05, "default": 0.0,
            "effects": [
                "\u2192 Guidance: 3.0 + rain \u00d7 2.0 (more rain = tighter AI control)",
                "\u2192 Prompts: adds 'piano arpeggios' when > 0.3",
            ],
        },
        {
            "name": "pressure", "label": "Pressure (hPa)",
            "min": 980, "max": 1040, "step": 1, "default": 1013.0,
            "effects": [
                "\u2192 Visualization only (sky color gradient)",
            ],
        },
    ]

    def __init__(self) -> None:
        super().__init__()
        self._live_data: dict | None = None

    def set_live_data(self, data: dict) -> None:
        """Inject live weather data from Open-Meteo."""
        self._live_data = data

    def tick(self, t: float) -> dict:
        if self._live_data:
            return dict(self._live_data)

        # All values come directly from user sliders
        return {
            "wind_speed": self._params["wind_speed"],
            "temperature": self._params["temperature"],
            "humidity": self._params["humidity"],
            "rain_probability": self._params["rain"],
            "pressure": self._params["pressure"],
        }

    def map(self, data: dict) -> ControlState:
        wind = data["wind_speed"]          # 0-30
        temp = data["temperature"]         # -10 to 40
        humidity = data["humidity"]        # 0-100
        rain = data["rain_probability"]    # 0-1

        # Wind -> BPM (0 m/s -> 70 bpm, 30 m/s -> 180 bpm)
        bpm = int(self._ema("bpm", 70 + wind * 3.67))

        # Temperature -> Brightness (cold=dim, hot=bright)
        brightness = self._ema("brightness", (temp + 10) / 50)

        # Humidity -> Density (dry=sparse, humid=dense)
        density = self._ema("density", humidity / 100)

        # Build prompts based on conditions
        prompts = []

        if temp < 5:
            prompts.append({"text": "Ethereal Ambience, cold, sustained chords", "weight": 1.0})
        elif temp > 30:
            prompts.append({"text": "Warm acoustic guitar, bright tones, upbeat", "weight": 1.0})
        else:
            prompts.append({"text": "Ambient, smooth pianos, dreamy", "weight": 1.0})

        if rain > 0.3:
            prompts.append({"text": "Piano arpeggios, rain, gentle", "weight": rain})

        if wind > 15:
            prompts.append({"text": "Spacey synths, wind, sweeping", "weight": wind / 30})

        if wind > 20 and rain > 0.5:
            prompts.append({"text": "Dirty synths, crunchy distortion, ominous drone", "weight": 0.8})

        if not prompts:
            prompts = [{"text": "Ambient, chill", "weight": 1.0}]

        guidance = 3.0 + rain * 2.0

        return ControlState(
            bpm=bpm,
            density=density,
            brightness=brightness,
            guidance=guidance,
            prompts=prompts,
        )

    def viz_state(self, data: dict) -> dict:
        wind = data["wind_speed"]
        temp = data["temperature"]
        humidity = data["humidity"]
        rain = data["rain_probability"]

        if temp < 0:
            color = {"r": 100, "g": 150, "b": 255}
        elif temp < 15:
            color = {"r": 150, "g": 200, "b": 230}
        elif temp < 25:
            color = {"r": 255, "g": 220, "b": 100}
        else:
            color = {"r": 255, "g": 120, "b": 50}

        return {
            "type": "atmosphere",
            "particle_velocity": wind / 30,
            "particle_count": int(50 + humidity * 2),
            "particle_size": 2 + rain * 4,
            "color": color,
            "wind_angle": (wind * 0.07) % 6.28,
            "rain_drops": rain > 0.4,
            "lightning": wind > 25 and rain > 0.6,
            "data": {
                "temperature": round(temp, 1),
                "wind_speed": round(wind, 1),
                "humidity": round(humidity, 1),
                "pressure": round(data["pressure"], 1),
                "rain": round(rain, 2),
            },
        }
