"""Lattice lens: mathematical functions -> music + animated plots."""

from __future__ import annotations

import math

from data_sources.simulators import LorenzAttractor, MathSimulator
from lenses.base import ControlState, Lens


class LatticeLens(Lens):
    name = "lattice"
    description = "Mathematics made audible"
    tick_hz = 8.0

    parameters = [
        {
            "name": "chaos", "label": "Chaos (rho)",
            "min": 0, "max": 1, "step": 0.02, "default": 0.7,
            "effects": [
                "\u2192 BPM: 80 + chaos \u00d7 80 (ordered = 80, chaotic = 160)",
                "\u2192 Density: direct mapping (periodic = sparse, chaotic = dense)",
                "\u2192 Scale: < 0.3 C Major; 0.3\u20130.6 D Major; > 0.6 Gb Major",
                "\u2192 Temperature: 0.8 + chaos (more chaos = more AI randomness)",
                "\u2192 Prompts: low = 'piano, classical'; mid = 'jazz fusion'; high = 'glitchy, experimental'",
            ],
        },
        {
            "name": "sigma", "label": "Sigma",
            "min": 1, "max": 30, "step": 0.5, "default": 10.0,
            "effects": [
                "\u2192 Attractor shape (affects chaos_level indirectly)",
            ],
        },
        {
            "name": "beta", "label": "Beta",
            "min": 0.5, "max": 8, "step": 0.1, "default": 2.67,
            "effects": [
                "\u2192 Attractor shape (affects chaos_level indirectly)",
            ],
        },
        {
            "name": "speed", "label": "Speed",
            "min": 0.1, "max": 3, "step": 0.1, "default": 1.0,
            "effects": [
                "\u2192 Visualization speed (attractor traversal rate)",
            ],
        },
        {
            "name": "mode", "label": "Mode (0=Lorenz, 0.5=Logistic, 1=Sine)",
            "min": 0, "max": 1, "step": 0.5, "default": 0.0,
            "effects": [
                "\u2192 Generator type: 0 = Lorenz attractor, 0.5 = Logistic map, 1 = Sine wave",
                "\u2192 Prompts: adds mode-specific flavor (atmospheric / techno / ambient)",
            ],
        },
    ]

    def __init__(self) -> None:
        super().__init__()
        self._sim = MathSimulator()
        self._lorenz = LorenzAttractor()

    def _get_mode(self) -> str:
        m = self._params.get("mode", 0)
        if m < 0.25:
            return "lorenz"
        elif m < 0.75:
            return "logistic"
        else:
            return "sine"

    def tick(self, t: float) -> dict:
        mode = self._get_mode()

        if mode == "lorenz":
            # Apply user-controlled Lorenz parameters
            self._lorenz.sigma = self._params["sigma"]
            self._lorenz.beta = self._params["beta"]
            self._lorenz.rho = 10.0 + 35.0 * self._params["chaos"]

            # Step multiple times per tick, scaled by speed
            steps = max(1, int(10 * self._params["speed"]))
            for _ in range(steps):
                self._lorenz.step()

            x, y, z = self._lorenz.x, self._lorenz.y, self._lorenz.z
            amplitude = min(1.0, math.sqrt(x*x + y*y + z*z) / 50.0)
            chaos_level = self._lorenz.chaos_metric

            return {
                "mode": "lorenz",
                "x": round(x, 3),
                "y": round(y, 3),
                "z": round(z, 3),
                "amplitude": round(amplitude, 3),
                "chaos_level": round(chaos_level, 3),
                "trail": [(round(p[0], 2), round(p[1], 2), round(p[2], 2))
                          for p in self._lorenz._trail[-100:]],
            }
        else:
            return self._sim.tick(
                t * self._params["speed"],
                chaos_param=self._params["chaos"],
                mode=mode,
            )

    def map(self, data: dict) -> ControlState:
        amplitude = data["amplitude"]
        chaos_level = data["chaos_level"]
        mode = data["mode"]

        brightness = self._ema("brightness", amplitude)
        density = self._ema("density", chaos_level)
        bpm = int(self._ema("bpm", 80 + chaos_level * 80))

        if chaos_level < 0.3:
            scale = "C_MAJOR_A_MINOR"
            prompts = [
                {"text": "Piano, melodic, classical, ordered", "weight": 1.0},
                {"text": "Sustained chords, harmonic", "weight": 0.5},
            ]
        elif chaos_level < 0.6:
            scale = "D_MAJOR_B_MINOR"
            prompts = [
                {"text": "Jazz fusion, complex, experimental", "weight": 1.0},
                {"text": "Rhodes piano, synth pads", "weight": 0.6},
            ]
        else:
            scale = "G_FLAT_MAJOR_E_FLAT_MINOR"
            prompts = [
                {"text": "Glitchy effects, experimental, weird noises", "weight": 1.0},
                {"text": "Psychedelic, echo, distortion", "weight": 0.7},
            ]

        if mode == "lorenz":
            prompts.append({"text": "Spacey synths, atmospheric", "weight": 0.4})
        elif mode == "logistic":
            prompts.append({"text": "Minimal techno, precise, electronic", "weight": 0.4})
        else:
            prompts.append({"text": "Ambient, dreamy, sine tones", "weight": 0.4})

        return ControlState(
            bpm=bpm,
            density=density,
            brightness=brightness,
            guidance=3.0 + chaos_level * 2.0,
            scale=scale,
            prompts=prompts,
            temperature=0.8 + chaos_level * 1.0,
        )

    def viz_state(self, data: dict) -> dict:
        mode = data["mode"]
        chaos = data["chaos_level"]
        color = {
            "r": int(80 + chaos * 175),
            "g": int(120 - chaos * 80),
            "b": int(255 - chaos * 155),
        }

        base = {
            "type": "lattice",
            "mode": mode,
            "chaos_level": chaos,
            "amplitude": data["amplitude"],
            "color": color,
            "glow_intensity": 0.3 + chaos * 0.7,
        }

        if mode == "lorenz":
            base["trail"] = data.get("trail", [])
            base["current"] = {"x": data["x"], "y": data["y"]}
            base["data"] = {
                "x": round(data["x"], 2),
                "y": round(data["y"], 2),
                "z": round(data["z"], 2),
                "chaos": round(chaos, 2),
                "sigma": self._params["sigma"],
                "beta": round(self._params["beta"], 2),
                "rho": round(10 + 35 * self._params["chaos"], 1),
            }
        elif mode == "logistic":
            base["iterations"] = data.get("iterations", [])
            base["r"] = data.get("r", 3.0)
            base["data"] = {
                "x": data["x"],
                "r": data.get("r", 3.0),
                "chaos": round(chaos, 2),
            }
        else:
            base["components"] = data.get("components", [])
            base["value"] = data.get("value", 0)
            base["data"] = {
                "value": round(data.get("value", 0), 3),
                "n_waves": data.get("n_waves", 3),
                "chaos": round(chaos, 2),
            }

        return base
