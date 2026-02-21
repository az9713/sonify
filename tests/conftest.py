"""Shared fixtures for the Sonify test suite."""

from __future__ import annotations

import pytest

from lenses.base import ControlState
from lenses.atmosphere import AtmosphereLens
from lenses.pulse import PulseLens
from lenses.lattice import LatticeLens
from lenses.flow import FlowLens
from lyria_bridge import MockAudioGenerator
from data_sources.simulators import (
    WeatherSimulator,
    CardiacSimulator,
    LorenzAttractor,
    MathSimulator,
    NetworkSimulator,
)


# ── ControlState fixtures ───────────────────────────────────────────────


@pytest.fixture
def default_controls() -> ControlState:
    """ControlState with all default values."""
    return ControlState()


@pytest.fixture
def extreme_low_controls() -> ControlState:
    """ControlState with values far below valid ranges."""
    return ControlState(
        bpm=0,
        density=-1.0,
        brightness=-1.0,
        guidance=-1.0,
        temperature=-1.0,
    )


@pytest.fixture
def extreme_high_controls() -> ControlState:
    """ControlState with values far above valid ranges."""
    return ControlState(
        bpm=999,
        density=5.0,
        brightness=5.0,
        guidance=99.0,
        temperature=99.0,
    )


# ── Lens fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def atmosphere_lens() -> AtmosphereLens:
    return AtmosphereLens()


@pytest.fixture
def pulse_lens() -> PulseLens:
    return PulseLens()


@pytest.fixture
def lattice_lens() -> LatticeLens:
    return LatticeLens()


@pytest.fixture
def flow_lens() -> FlowLens:
    return FlowLens()


# ── Simulator fixtures ──────────────────────────────────────────────────


@pytest.fixture
def weather_sim() -> WeatherSimulator:
    return WeatherSimulator(seed=42)


@pytest.fixture
def cardiac_sim() -> CardiacSimulator:
    return CardiacSimulator(resting_hr=72.0)


@pytest.fixture
def lorenz() -> LorenzAttractor:
    return LorenzAttractor()


@pytest.fixture
def math_sim() -> MathSimulator:
    return MathSimulator()


@pytest.fixture
def network_sim() -> NetworkSimulator:
    return NetworkSimulator(base_rate=50.0)


# ── Audio fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def mock_audio() -> MockAudioGenerator:
    return MockAudioGenerator(sample_rate=48000, channels=2)
