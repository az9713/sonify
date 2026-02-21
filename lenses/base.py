"""Base abstractions for lenses and Lyria control state."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class ControlState:
    """Deterministic mapping output that drives Lyria + visuals.

    All numeric fields are clamped to Lyria-valid ranges.
    """

    bpm: int = 120                    # 60-200
    density: float = 0.5              # 0.0-1.0
    brightness: float = 0.5           # 0.0-1.0
    guidance: float = 4.0             # 0.0-6.0
    scale: str = "SCALE_UNSPECIFIED"  # Scale enum string
    prompts: list[dict] = field(default_factory=lambda: [{"text": "ambient", "weight": 1.0}])
    mute_bass: bool = False
    mute_drums: bool = False
    temperature: float = 1.1          # 0.0-3.0

    def clamped(self) -> ControlState:
        """Return a copy with all values clamped to valid Lyria ranges."""
        return ControlState(
            bpm=max(60, min(200, int(self.bpm))),
            density=max(0.0, min(1.0, self.density)),
            brightness=max(0.0, min(1.0, self.brightness)),
            guidance=max(0.0, min(6.0, self.guidance)),
            scale=self.scale,
            prompts=self.prompts,
            mute_bass=self.mute_bass,
            mute_drums=self.mute_drums,
            temperature=max(0.0, min(3.0, self.temperature)),
        )

    def diff(self, other: ControlState) -> dict:
        """Return dict of fields that changed between self and other."""
        changes = {}
        if self.bpm != other.bpm:
            changes["bpm"] = self.bpm
        if abs(self.density - other.density) > 0.01:
            changes["density"] = self.density
        if abs(self.brightness - other.brightness) > 0.01:
            changes["brightness"] = self.brightness
        if abs(self.guidance - other.guidance) > 0.01:
            changes["guidance"] = self.guidance
        if self.scale != other.scale:
            changes["scale"] = self.scale
        if self.prompts != other.prompts:
            changes["prompts"] = self.prompts
        if self.mute_bass != other.mute_bass:
            changes["mute_bass"] = self.mute_bass
        if self.mute_drums != other.mute_drums:
            changes["mute_drums"] = self.mute_drums
        if abs(self.temperature - other.temperature) > 0.01:
            changes["temperature"] = self.temperature
        return changes


class Lens(abc.ABC):
    """Abstract base for all sonification lenses.

    A lens takes domain-specific data, maps it to ControlState (for Lyria)
    and viz_state (for the Canvas renderer).
    """

    name: str = "base"
    description: str = ""
    tick_hz: float = 5.0  # How often to update (Hz)

    # Per-lens adjustable parameters: list of {name, label, min, max, step, default}
    parameters: list[dict] = []

    def __init__(self) -> None:
        self._params: dict[str, float] = {
            p["name"]: p["default"] for p in self.parameters
        }
        self._ema_state: dict[str, float] = {}
        self._ema_alpha: float = 0.15  # Smoothing factor

    def set_param(self, name: str, value: float) -> None:
        self._params[name] = value

    def get_params(self) -> dict[str, float]:
        return dict(self._params)

    def _ema(self, key: str, value: float) -> float:
        """Exponential moving average for perceptual stability."""
        if key not in self._ema_state:
            self._ema_state[key] = value
        else:
            self._ema_state[key] = (
                self._ema_alpha * value + (1 - self._ema_alpha) * self._ema_state[key]
            )
        return self._ema_state[key]

    @abc.abstractmethod
    def tick(self, t: float) -> dict:
        """Generate domain data at time t. Returns raw domain dict."""
        ...

    @abc.abstractmethod
    def map(self, data: dict) -> ControlState:
        """Map domain data to Lyria ControlState."""
        ...

    @abc.abstractmethod
    def viz_state(self, data: dict) -> dict:
        """Map domain data to visualization JSON for the browser Canvas."""
        ...

    def update(self, t: float) -> tuple[ControlState, dict]:
        """Full tick: generate data, map to controls + viz."""
        data = self.tick(t)
        controls = self.map(data).clamped()
        viz = self.viz_state(data)
        return controls, viz
