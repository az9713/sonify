"""Tests for all four lenses: map(), EMA smoothing, monotone mappings, update()."""

from __future__ import annotations

import pytest

from lenses.base import ControlState, Lens
from lenses.atmosphere import AtmosphereLens
from lenses.pulse import PulseLens
from lenses.lattice import LatticeLens
from lenses.flow import FlowLens
from lenses import LENSES


# ── LENSES registry ────────────────────────────────────────────────────


class TestLensesRegistry:
    """Verify LENSES dict has all four lenses registered."""

    def test_four_lenses_registered(self) -> None:
        assert len(LENSES) == 4

    def test_atmosphere_registered(self) -> None:
        assert "atmosphere" in LENSES
        assert LENSES["atmosphere"] is AtmosphereLens

    def test_pulse_registered(self) -> None:
        assert "pulse" in LENSES
        assert LENSES["pulse"] is PulseLens

    def test_lattice_registered(self) -> None:
        assert "lattice" in LENSES
        assert LENSES["lattice"] is LatticeLens

    def test_flow_registered(self) -> None:
        assert "flow" in LENSES
        assert LENSES["flow"] is FlowLens


# ── EMA smoothing ───────────────────────────────────────────────────────


class TestEMASmoothing:
    """Verify EMA convergence behavior (alpha=0.15)."""

    def test_first_value_passes_through(self, atmosphere_lens: AtmosphereLens) -> None:
        result = atmosphere_lens._ema("test_key", 100.0)
        assert result == 100.0

    def test_ema_smooths_toward_target(self, atmosphere_lens: AtmosphereLens) -> None:
        atmosphere_lens._ema("key", 0.0)
        # After applying EMA with target=1.0, value should move toward 1.0
        result = atmosphere_lens._ema("key", 1.0)
        assert 0.0 < result < 1.0
        # With alpha=0.15, second call should give 0.15
        assert abs(result - 0.15) < 0.001

    def test_ema_converges_over_many_steps(self, atmosphere_lens: AtmosphereLens) -> None:
        atmosphere_lens._ema("conv", 0.0)
        for _ in range(200):
            val = atmosphere_lens._ema("conv", 1.0)
        # After 200 steps with alpha=0.15, should be very close to 1.0
        assert val > 0.99

    def test_ema_alpha_is_015(self, atmosphere_lens: AtmosphereLens) -> None:
        assert atmosphere_lens._ema_alpha == 0.15

    def test_ema_independent_keys(self, atmosphere_lens: AtmosphereLens) -> None:
        atmosphere_lens._ema("a", 10.0)
        atmosphere_lens._ema("b", 20.0)
        assert abs(atmosphere_lens._ema_state["a"] - 10.0) < 0.001
        assert abs(atmosphere_lens._ema_state["b"] - 20.0) < 0.001


# ── AtmosphereLens ──────────────────────────────────────────────────────


class TestAtmosphereLens:
    """Tests for the weather sonification lens."""

    def test_name(self, atmosphere_lens: AtmosphereLens) -> None:
        assert atmosphere_lens.name == "atmosphere"

    def test_tick_hz(self, atmosphere_lens: AtmosphereLens) -> None:
        assert atmosphere_lens.tick_hz == 4.0

    def test_tick_returns_expected_keys(self, atmosphere_lens: AtmosphereLens) -> None:
        data = atmosphere_lens.tick(0.0)
        expected_keys = {"wind_speed", "temperature", "humidity", "rain_probability", "pressure"}
        assert set(data.keys()) == expected_keys

    def test_map_returns_control_state(self, atmosphere_lens: AtmosphereLens) -> None:
        data = atmosphere_lens.tick(0.0)
        result = atmosphere_lens.map(data)
        assert isinstance(result, ControlState)

    def test_map_wind_to_bpm_monotone(self, atmosphere_lens: AtmosphereLens) -> None:
        """Higher wind should produce higher or equal BPM."""
        low_data = {
            "wind_speed": 0, "temperature": 20,
            "humidity": 50, "rain_probability": 0, "pressure": 1013,
        }
        high_data = {
            "wind_speed": 30, "temperature": 20,
            "humidity": 50, "rain_probability": 0, "pressure": 1013,
        }
        # Reset EMA state between tests
        lens1 = AtmosphereLens()
        lens2 = AtmosphereLens()
        low_result = lens1.map(low_data)
        high_result = lens2.map(high_data)
        assert high_result.bpm >= low_result.bpm

    def test_map_temperature_to_brightness_monotone(self) -> None:
        """Higher temperature should produce higher or equal brightness."""
        cold_data = {
            "wind_speed": 10, "temperature": -10,
            "humidity": 50, "rain_probability": 0, "pressure": 1013,
        }
        hot_data = {
            "wind_speed": 10, "temperature": 40,
            "humidity": 50, "rain_probability": 0, "pressure": 1013,
        }
        lens1 = AtmosphereLens()
        lens2 = AtmosphereLens()
        cold_result = lens1.map(cold_data)
        hot_result = lens2.map(hot_data)
        assert hot_result.brightness >= cold_result.brightness

    def test_map_humidity_to_density_monotone(self) -> None:
        """Higher humidity should produce higher or equal density."""
        dry_data = {
            "wind_speed": 10, "temperature": 20,
            "humidity": 0, "rain_probability": 0, "pressure": 1013,
        }
        humid_data = {
            "wind_speed": 10, "temperature": 20,
            "humidity": 100, "rain_probability": 0, "pressure": 1013,
        }
        lens1 = AtmosphereLens()
        lens2 = AtmosphereLens()
        dry_result = lens1.map(dry_data)
        humid_result = lens2.map(humid_data)
        assert humid_result.density >= dry_result.density

    def test_map_rain_to_guidance_monotone(self) -> None:
        """Higher rain should produce higher or equal guidance."""
        no_rain_data = {
            "wind_speed": 10, "temperature": 20,
            "humidity": 50, "rain_probability": 0.0, "pressure": 1013,
        }
        heavy_rain_data = {
            "wind_speed": 10, "temperature": 20,
            "humidity": 50, "rain_probability": 1.0, "pressure": 1013,
        }
        lens1 = AtmosphereLens()
        lens2 = AtmosphereLens()
        no_rain_result = lens1.map(no_rain_data)
        heavy_rain_result = lens2.map(heavy_rain_data)
        assert heavy_rain_result.guidance >= no_rain_result.guidance

    def test_map_prompts_cold(self) -> None:
        """Cold temperature (<5) should produce ethereal prompts."""
        data = {
            "wind_speed": 5, "temperature": 0,
            "humidity": 50, "rain_probability": 0, "pressure": 1013,
        }
        lens = AtmosphereLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert any("cold" in t for t in texts)

    def test_map_prompts_hot(self) -> None:
        """Hot temperature (>30) should produce warm prompts."""
        data = {
            "wind_speed": 5, "temperature": 35,
            "humidity": 50, "rain_probability": 0, "pressure": 1013,
        }
        lens = AtmosphereLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert any("warm" in t for t in texts)

    def test_map_prompts_rain(self) -> None:
        """Rain > 0.3 should add piano arpeggio prompt."""
        data = {
            "wind_speed": 5, "temperature": 20,
            "humidity": 50, "rain_probability": 0.5, "pressure": 1013,
        }
        lens = AtmosphereLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert any("piano" in t or "arpeggio" in t for t in texts)

    def test_map_prompts_high_wind(self) -> None:
        """Wind > 15 should add sweeping synths prompt."""
        data = {
            "wind_speed": 20, "temperature": 20,
            "humidity": 50, "rain_probability": 0, "pressure": 1013,
        }
        lens = AtmosphereLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert any("synth" in t or "sweep" in t or "wind" in t for t in texts)

    def test_map_prompts_storm(self) -> None:
        """Wind > 20 AND rain > 0.5 should add distortion drone prompt."""
        data = {
            "wind_speed": 25, "temperature": 20,
            "humidity": 50, "rain_probability": 0.7, "pressure": 1013,
        }
        lens = AtmosphereLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert any("distortion" in t or "drone" in t for t in texts)

    def test_viz_state_returns_dict(self, atmosphere_lens: AtmosphereLens) -> None:
        data = atmosphere_lens.tick(0.0)
        viz = atmosphere_lens.viz_state(data)
        assert isinstance(viz, dict)
        assert viz["type"] == "atmosphere"

    def test_update_returns_clamped_controls(self, atmosphere_lens: AtmosphereLens) -> None:
        controls, viz = atmosphere_lens.update(0.0)
        assert isinstance(controls, ControlState)
        assert 60 <= controls.bpm <= 200
        assert 0.0 <= controls.density <= 1.0
        assert 0.0 <= controls.brightness <= 1.0
        assert 0.0 <= controls.guidance <= 6.0
        assert 0.0 <= controls.temperature <= 3.0

    def test_live_data_injection(self, atmosphere_lens: AtmosphereLens) -> None:
        live = {
            "wind_speed": 25, "temperature": 30,
            "humidity": 80, "rain_probability": 0.6, "pressure": 1000,
        }
        atmosphere_lens.set_live_data(live)
        data = atmosphere_lens.tick(0.0)
        assert data["wind_speed"] == 25
        assert data["temperature"] == 30

    def test_set_param(self, atmosphere_lens: AtmosphereLens) -> None:
        atmosphere_lens.set_param("wind_speed", 20.0)
        assert atmosphere_lens._params["wind_speed"] == 20.0


# ── PulseLens ───────────────────────────────────────────────────────────


class TestPulseLens:
    """Tests for the cardiac sonification lens."""

    def test_name(self, pulse_lens: PulseLens) -> None:
        assert pulse_lens.name == "pulse"

    def test_tick_hz(self, pulse_lens: PulseLens) -> None:
        assert pulse_lens.tick_hz == 10.0

    def test_tick_returns_expected_keys(self, pulse_lens: PulseLens) -> None:
        data = pulse_lens.tick(0.0)
        expected_keys = {
            "heart_rate", "hrv_sdnn_ms", "stress",
            "exercise_level", "ecg_value", "ecg_history", "arrhythmia",
        }
        assert set(data.keys()) == expected_keys

    def test_map_returns_control_state(self, pulse_lens: PulseLens) -> None:
        data = pulse_lens.tick(0.0)
        result = pulse_lens.map(data)
        assert isinstance(result, ControlState)

    def test_map_hr_to_bpm_monotone(self) -> None:
        """Higher heart rate should produce higher or equal BPM."""
        low_data = {
            "heart_rate": 60, "hrv_sdnn_ms": 40,
            "stress": 0.2, "arrhythmia": False,
        }
        high_data = {
            "heart_rate": 180, "hrv_sdnn_ms": 40,
            "stress": 0.2, "arrhythmia": False,
        }
        lens1 = PulseLens()
        lens2 = PulseLens()
        low_result = lens1.map(low_data)
        high_result = lens2.map(high_data)
        assert high_result.bpm >= low_result.bpm

    def test_map_stress_to_brightness_monotone(self) -> None:
        """Higher stress should produce higher or equal brightness."""
        calm_data = {
            "heart_rate": 72, "hrv_sdnn_ms": 40,
            "stress": 0.0, "arrhythmia": False,
        }
        stressed_data = {
            "heart_rate": 72, "hrv_sdnn_ms": 40,
            "stress": 1.0, "arrhythmia": False,
        }
        lens1 = PulseLens()
        lens2 = PulseLens()
        calm_result = lens1.map(calm_data)
        stressed_result = lens2.map(stressed_data)
        assert stressed_result.brightness >= calm_result.brightness

    def test_map_hrv_to_density_monotone(self) -> None:
        """Higher HRV should produce higher or equal density."""
        low_hrv_data = {
            "heart_rate": 72, "hrv_sdnn_ms": 0,
            "stress": 0.3, "arrhythmia": False,
        }
        high_hrv_data = {
            "heart_rate": 72, "hrv_sdnn_ms": 80,
            "stress": 0.3, "arrhythmia": False,
        }
        lens1 = PulseLens()
        lens2 = PulseLens()
        low_result = lens1.map(low_hrv_data)
        high_result = lens2.map(high_hrv_data)
        assert high_result.density >= low_result.density

    def test_map_low_stress_scale(self) -> None:
        """Low stress (< 0.5) should use C major scale."""
        data = {
            "heart_rate": 72, "hrv_sdnn_ms": 40,
            "stress": 0.2, "arrhythmia": False,
        }
        lens = PulseLens()
        result = lens.map(data)
        assert result.scale == "C_MAJOR_A_MINOR"

    def test_map_high_stress_scale(self) -> None:
        """High stress (> 0.5) should use Ab minor scale."""
        data = {
            "heart_rate": 72, "hrv_sdnn_ms": 40,
            "stress": 0.8, "arrhythmia": False,
        }
        lens = PulseLens()
        result = lens.map(data)
        assert result.scale == "A_FLAT_MAJOR_F_MINOR"

    def test_map_arrhythmia_adds_glitch_prompt(self) -> None:
        """Arrhythmia event should add glitchy effects prompt."""
        data = {
            "heart_rate": 72, "hrv_sdnn_ms": 40,
            "stress": 0.3, "arrhythmia": True,
        }
        lens = PulseLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert any("glitch" in t for t in texts)

    def test_update_returns_clamped(self, pulse_lens: PulseLens) -> None:
        controls, viz = pulse_lens.update(0.0)
        assert 60 <= controls.bpm <= 200
        assert 0.0 <= controls.density <= 1.0
        assert 0.0 <= controls.brightness <= 1.0

    def test_viz_state_type(self, pulse_lens: PulseLens) -> None:
        data = pulse_lens.tick(0.5)
        viz = pulse_lens.viz_state(data)
        assert viz["type"] == "pulse"
        assert "ecg_history" in viz


# ── LatticeLens ─────────────────────────────────────────────────────────


class TestLatticeLens:
    """Tests for the mathematical attractor sonification lens."""

    def test_name(self, lattice_lens: LatticeLens) -> None:
        assert lattice_lens.name == "lattice"

    def test_tick_hz(self, lattice_lens: LatticeLens) -> None:
        assert lattice_lens.tick_hz == 8.0

    def test_tick_lorenz_returns_expected_keys(self, lattice_lens: LatticeLens) -> None:
        lattice_lens.set_param("mode", 0.0)  # lorenz
        data = lattice_lens.tick(0.0)
        expected_keys = {"mode", "x", "y", "z", "amplitude", "chaos_level", "trail"}
        assert set(data.keys()) == expected_keys

    def test_tick_logistic_returns_expected_keys(self) -> None:
        lens = LatticeLens()
        lens.set_param("mode", 0.5)  # logistic
        data = lens.tick(1.0)
        expected_keys = {"mode", "x", "r", "amplitude", "chaos_level", "iterations"}
        assert set(data.keys()) == expected_keys

    def test_tick_sine_returns_expected_keys(self) -> None:
        lens = LatticeLens()
        lens.set_param("mode", 1.0)  # sine
        data = lens.tick(1.0)
        expected_keys = {"mode", "value", "amplitude", "chaos_level", "n_waves", "components", "t"}
        assert set(data.keys()) == expected_keys

    def test_map_returns_control_state(self, lattice_lens: LatticeLens) -> None:
        data = lattice_lens.tick(0.0)
        result = lattice_lens.map(data)
        assert isinstance(result, ControlState)

    def test_map_chaos_to_bpm_monotone(self) -> None:
        """Higher chaos should produce higher or equal BPM."""
        low_data = {"amplitude": 0.5, "chaos_level": 0.0, "mode": "lorenz"}
        high_data = {"amplitude": 0.5, "chaos_level": 1.0, "mode": "lorenz"}
        lens1 = LatticeLens()
        lens2 = LatticeLens()
        low_result = lens1.map(low_data)
        high_result = lens2.map(high_data)
        assert high_result.bpm >= low_result.bpm

    def test_map_chaos_to_density_monotone(self) -> None:
        """Higher chaos should produce higher or equal density."""
        low_data = {"amplitude": 0.5, "chaos_level": 0.0, "mode": "lorenz"}
        high_data = {"amplitude": 0.5, "chaos_level": 1.0, "mode": "lorenz"}
        lens1 = LatticeLens()
        lens2 = LatticeLens()
        low_result = lens1.map(low_data)
        high_result = lens2.map(high_data)
        assert high_result.density >= low_result.density

    def test_map_chaos_to_temperature_monotone(self) -> None:
        """Higher chaos should produce higher or equal temperature."""
        low_data = {"amplitude": 0.5, "chaos_level": 0.0, "mode": "lorenz"}
        high_data = {"amplitude": 0.5, "chaos_level": 1.0, "mode": "lorenz"}
        lens1 = LatticeLens()
        lens2 = LatticeLens()
        low_result = lens1.map(low_data)
        high_result = lens2.map(high_data)
        assert high_result.temperature >= low_result.temperature

    def test_map_low_chaos_scale(self) -> None:
        data = {"amplitude": 0.5, "chaos_level": 0.1, "mode": "lorenz"}
        lens = LatticeLens()
        result = lens.map(data)
        assert result.scale == "C_MAJOR_A_MINOR"

    def test_map_mid_chaos_scale(self) -> None:
        data = {"amplitude": 0.5, "chaos_level": 0.5, "mode": "lorenz"}
        lens = LatticeLens()
        result = lens.map(data)
        assert result.scale == "D_MAJOR_B_MINOR"

    def test_map_high_chaos_scale(self) -> None:
        data = {"amplitude": 0.5, "chaos_level": 0.8, "mode": "lorenz"}
        lens = LatticeLens()
        result = lens.map(data)
        assert result.scale == "G_FLAT_MAJOR_E_FLAT_MINOR"

    def test_map_mode_specific_prompt_lorenz(self) -> None:
        data = {"amplitude": 0.5, "chaos_level": 0.1, "mode": "lorenz"}
        lens = LatticeLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert any("atmospheric" in t or "spacey" in t for t in texts)

    def test_map_mode_specific_prompt_logistic(self) -> None:
        data = {"amplitude": 0.5, "chaos_level": 0.1, "mode": "logistic"}
        lens = LatticeLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert any("techno" in t or "electronic" in t for t in texts)

    def test_map_mode_specific_prompt_sine(self) -> None:
        data = {"amplitude": 0.5, "chaos_level": 0.1, "mode": "sine"}
        lens = LatticeLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert any("ambient" in t or "sine" in t or "dreamy" in t for t in texts)

    def test_update_returns_clamped(self, lattice_lens: LatticeLens) -> None:
        controls, viz = lattice_lens.update(0.0)
        assert 60 <= controls.bpm <= 200
        assert 0.0 <= controls.density <= 1.0
        assert 0.0 <= controls.brightness <= 1.0
        assert 0.0 <= controls.temperature <= 3.0


# ── FlowLens ────────────────────────────────────────────────────────────


class TestFlowLens:
    """Tests for the network traffic sonification lens."""

    def test_name(self, flow_lens: FlowLens) -> None:
        assert flow_lens.name == "flow"

    def test_tick_hz(self, flow_lens: FlowLens) -> None:
        assert flow_lens.tick_hz == 5.0

    def test_tick_returns_expected_keys(self, flow_lens: FlowLens) -> None:
        data = flow_lens.tick(0.0)
        expected_keys = {
            "packet_rate", "packet_count", "latency_ms", "error_rate",
            "errors", "is_burst", "throughput_mbps", "active_edges",
            "nodes", "node_activity", "load_level",
        }
        assert set(data.keys()) == expected_keys

    def test_map_returns_control_state(self, flow_lens: FlowLens) -> None:
        data = flow_lens.tick(0.0)
        result = flow_lens.map(data)
        assert isinstance(result, ControlState)

    def test_map_packet_rate_to_density_monotone(self) -> None:
        """Higher packet rate should produce higher or equal density."""
        low_data = {
            "packet_rate": 10, "latency_ms": 50,
            "is_burst": False, "error_rate": 0.01, "load_level": 0.05,
        }
        high_data = {
            "packet_rate": 200, "latency_ms": 50,
            "is_burst": False, "error_rate": 0.01, "load_level": 1.0,
        }
        lens1 = FlowLens()
        lens2 = FlowLens()
        low_result = lens1.map(low_data)
        high_result = lens2.map(high_data)
        assert high_result.density >= low_result.density

    def test_map_latency_to_brightness_inverse_monotone(self) -> None:
        """Higher latency should produce lower or equal brightness (inverse)."""
        low_lat_data = {
            "packet_rate": 50, "latency_ms": 10,
            "is_burst": False, "error_rate": 0.01, "load_level": 0.25,
        }
        high_lat_data = {
            "packet_rate": 50, "latency_ms": 190,
            "is_burst": False, "error_rate": 0.01, "load_level": 0.25,
        }
        lens1 = FlowLens()
        lens2 = FlowLens()
        low_lat_result = lens1.map(low_lat_data)
        high_lat_result = lens2.map(high_lat_data)
        assert low_lat_result.brightness >= high_lat_result.brightness

    def test_map_burst_increases_bpm(self) -> None:
        """Burst mode should increase BPM."""
        no_burst_data = {
            "packet_rate": 100, "latency_ms": 50,
            "is_burst": False, "error_rate": 0.01, "load_level": 0.5,
        }
        burst_data = {
            "packet_rate": 100, "latency_ms": 50,
            "is_burst": True, "error_rate": 0.01, "load_level": 0.5,
        }
        lens1 = FlowLens()
        lens2 = FlowLens()
        no_burst_result = lens1.map(no_burst_data)
        burst_result = lens2.map(burst_data)
        assert burst_result.bpm >= no_burst_result.bpm

    def test_map_burst_adds_prompt(self) -> None:
        """Burst should add intense/distortion prompt."""
        data = {
            "packet_rate": 100, "latency_ms": 50,
            "is_burst": True, "error_rate": 0.01, "load_level": 0.5,
        }
        lens = FlowLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert any("drop" in t or "intense" in t or "distortion" in t for t in texts)

    def test_map_high_error_adds_glitch_prompt(self) -> None:
        """Error rate > 0.05 should add glitchy prompt."""
        data = {
            "packet_rate": 100, "latency_ms": 50,
            "is_burst": False, "error_rate": 0.1, "load_level": 0.5,
        }
        lens = FlowLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert any("glitch" in t for t in texts)

    def test_map_low_error_no_glitch_prompt(self) -> None:
        """Error rate < 0.05 should not add glitchy prompt."""
        data = {
            "packet_rate": 100, "latency_ms": 50,
            "is_burst": False, "error_rate": 0.01, "load_level": 0.5,
        }
        lens = FlowLens()
        result = lens.map(data)
        texts = [p["text"].lower() for p in result.prompts]
        assert not any("glitch" in t for t in texts)

    def test_update_returns_clamped(self, flow_lens: FlowLens) -> None:
        controls, viz = flow_lens.update(0.0)
        assert 60 <= controls.bpm <= 200
        assert 0.0 <= controls.density <= 1.0
        assert 0.0 <= controls.brightness <= 1.0

    def test_viz_state_type(self, flow_lens: FlowLens) -> None:
        data = flow_lens.tick(0.0)
        viz = flow_lens.viz_state(data)
        assert viz["type"] == "flow"
        assert "nodes" in viz
        assert "active_edges" in viz


# ── All lenses: update() produces valid ranges ─────────────────────────


class TestAllLensesUpdate:
    """Run update() on each lens and verify clamped output."""

    @pytest.mark.parametrize("lens_name", ["atmosphere", "pulse", "lattice", "flow"])
    def test_update_produces_clamped_values(self, lens_name: str) -> None:
        lens = LENSES[lens_name]()
        controls, viz = lens.update(1.0)

        assert isinstance(controls, ControlState)
        assert 60 <= controls.bpm <= 200
        assert 0.0 <= controls.density <= 1.0
        assert 0.0 <= controls.brightness <= 1.0
        assert 0.0 <= controls.guidance <= 6.0
        assert 0.0 <= controls.temperature <= 3.0
        assert isinstance(controls.mute_bass, bool)
        assert isinstance(controls.mute_drums, bool)
        assert isinstance(controls.prompts, list)
        assert len(controls.prompts) > 0

    @pytest.mark.parametrize("lens_name", ["atmosphere", "pulse", "lattice", "flow"])
    def test_update_viz_is_dict(self, lens_name: str) -> None:
        lens = LENSES[lens_name]()
        _controls, viz = lens.update(1.0)
        assert isinstance(viz, dict)
        assert "type" in viz

    @pytest.mark.parametrize("lens_name", ["atmosphere", "pulse", "lattice", "flow"])
    def test_lens_has_parameters(self, lens_name: str) -> None:
        lens = LENSES[lens_name]()
        assert isinstance(lens.parameters, list)
        for p in lens.parameters:
            assert "name" in p
            assert "default" in p

    @pytest.mark.parametrize("lens_name", ["atmosphere", "pulse", "lattice", "flow"])
    def test_lens_has_description(self, lens_name: str) -> None:
        lens = LENSES[lens_name]()
        assert isinstance(lens.description, str)
        assert len(lens.description) > 0
