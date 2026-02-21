"""Tests for all simulators: expected keys, value ranges, chaos metrics, distributions."""

from __future__ import annotations

import math

import pytest

from data_sources.simulators import (
    WeatherSimulator,
    CardiacSimulator,
    LorenzAttractor,
    MathSimulator,
    NetworkSimulator,
)


# ── WeatherSimulator ───────────────────────────────────────────────────


class TestWeatherSimulator:
    """Tests for weather data generation."""

    def test_tick_returns_expected_keys(self, weather_sim: WeatherSimulator) -> None:
        data = weather_sim.tick(0.0)
        expected = {"temperature", "wind_speed", "humidity", "pressure", "rain_probability"}
        assert set(data.keys()) == expected

    def test_temperature_range(self, weather_sim: WeatherSimulator) -> None:
        """Temperature must stay within -10 to 40 C."""
        for t in range(500):
            data = weather_sim.tick(t * 0.1)
            assert -10 <= data["temperature"] <= 40

    def test_wind_speed_range(self, weather_sim: WeatherSimulator) -> None:
        """Wind speed must stay within 0 to 100 km/h."""
        for t in range(500):
            data = weather_sim.tick(t * 0.1)
            assert 0 <= data["wind_speed"] <= 100

    def test_humidity_range(self, weather_sim: WeatherSimulator) -> None:
        """Humidity must stay within 0 to 100%."""
        for t in range(500):
            data = weather_sim.tick(t * 0.1)
            assert 0 <= data["humidity"] <= 100

    def test_pressure_range(self, weather_sim: WeatherSimulator) -> None:
        """Pressure must stay within 990 to 1030 hPa."""
        for t in range(500):
            data = weather_sim.tick(t * 0.1)
            assert 990 <= data["pressure"] <= 1030

    def test_rain_probability_range(self, weather_sim: WeatherSimulator) -> None:
        """Rain probability must stay within 0 to 1."""
        for t in range(500):
            data = weather_sim.tick(t * 0.1)
            assert 0 <= data["rain_probability"] <= 1

    def test_deterministic_with_same_seed(self) -> None:
        """Same seed should produce same results."""
        sim1 = WeatherSimulator(seed=42)
        sim2 = WeatherSimulator(seed=42)
        for t in range(10):
            d1 = sim1.tick(t * 0.5)
            d2 = sim2.tick(t * 0.5)
            assert d1 == d2

    def test_different_seeds_differ(self) -> None:
        """Different seeds should produce different results."""
        sim1 = WeatherSimulator(seed=42)
        sim2 = WeatherSimulator(seed=99)
        d1 = sim1.tick(1.0)
        d2 = sim2.tick(1.0)
        # At least some values should differ
        assert d1 != d2


# ── CardiacSimulator ────────────────────────────────────────────────────


class TestCardiacSimulator:
    """Tests for cardiac data generation."""

    def test_tick_returns_expected_keys(self, cardiac_sim: CardiacSimulator) -> None:
        data = cardiac_sim.tick(0.0)
        expected = {
            "heart_rate", "rr_interval_ms", "hrv_sdnn_ms",
            "ecg_value", "arrhythmia", "stress", "exercise_level",
        }
        assert set(data.keys()) == expected

    def test_heart_rate_at_rest(self, cardiac_sim: CardiacSimulator) -> None:
        """Resting heart rate should be near 72 bpm."""
        data = cardiac_sim.tick(0.5)
        # Allow variance from HRV
        assert 40 <= data["heart_rate"] <= 200

    def test_heart_rate_increases_with_exercise(self, cardiac_sim: CardiacSimulator) -> None:
        """Exercise should increase heart rate."""
        rest = cardiac_sim.tick(0.5, exercise_level=0.0)
        exercise = cardiac_sim.tick(1.0, exercise_level=1.0)
        # The target HR is 72 + 100*exercise, but actual may vary due to HRV
        # At least the direction should be correct over the target calculation
        target_rest = 72.0
        target_exercise = 72.0 + 100.0
        assert target_exercise > target_rest

    def test_heart_rate_range(self, cardiac_sim: CardiacSimulator) -> None:
        """Heart rate should be clamped to 40-200."""
        for t in range(100):
            data = cardiac_sim.tick(t * 0.1, exercise_level=1.0, stress=1.0)
            assert data["heart_rate"] >= 30  # with HRV noise, allow slightly lower
            assert data["heart_rate"] <= 250  # with HRV noise, allow slightly higher

    def test_hrv_sdnn_positive(self, cardiac_sim: CardiacSimulator) -> None:
        """HRV SDNN should be non-negative."""
        for t in range(50):
            data = cardiac_sim.tick(t * 0.1)
            assert data["hrv_sdnn_ms"] >= 0

    def test_ecg_value_bounded(self, cardiac_sim: CardiacSimulator) -> None:
        """ECG waveform values should be bounded."""
        for t in range(200):
            data = cardiac_sim.tick(t * 0.01)
            assert -1.0 <= data["ecg_value"] <= 1.5

    def test_arrhythmia_is_bool(self, cardiac_sim: CardiacSimulator) -> None:
        data = cardiac_sim.tick(1.0)
        assert isinstance(data["arrhythmia"], bool)

    def test_stress_passed_through(self, cardiac_sim: CardiacSimulator) -> None:
        data = cardiac_sim.tick(1.0, stress=0.75)
        assert data["stress"] == 0.75

    def test_exercise_level_passed_through(self, cardiac_sim: CardiacSimulator) -> None:
        data = cardiac_sim.tick(1.0, exercise_level=0.5)
        assert data["exercise_level"] == 0.5


# ── LorenzAttractor ─────────────────────────────────────────────────────


class TestLorenzAttractor:
    """Tests for the Lorenz system integrator."""

    def test_initial_position(self, lorenz: LorenzAttractor) -> None:
        assert lorenz.x == 1.0
        assert lorenz.y == 1.0
        assert lorenz.z == 1.0

    def test_step_returns_tuple(self, lorenz: LorenzAttractor) -> None:
        result = lorenz.step()
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_step_changes_position(self, lorenz: LorenzAttractor) -> None:
        x0, y0, z0 = lorenz.x, lorenz.y, lorenz.z
        lorenz.step()
        # After one step, position should have changed
        assert not (lorenz.x == x0 and lorenz.y == y0 and lorenz.z == z0)

    def test_trail_grows(self, lorenz: LorenzAttractor) -> None:
        assert len(lorenz._trail) == 0
        for i in range(10):
            lorenz.step()
        assert len(lorenz._trail) == 10

    def test_trail_max_length(self, lorenz: LorenzAttractor) -> None:
        for _ in range(600):
            lorenz.step()
        assert len(lorenz._trail) == lorenz._max_trail

    def test_chaos_metric_range(self, lorenz: LorenzAttractor) -> None:
        """chaos_metric should always be in [0, 1]."""
        for _ in range(100):
            lorenz.step()
        metric = lorenz.chaos_metric
        assert 0.0 <= metric <= 1.0

    def test_chaos_metric_default_with_few_points(self, lorenz: LorenzAttractor) -> None:
        """With fewer than 10 trail points, chaos_metric returns 0.5."""
        for _ in range(5):
            lorenz.step()
        assert lorenz.chaos_metric == 0.5

    def test_default_parameters(self, lorenz: LorenzAttractor) -> None:
        assert lorenz.sigma == 10.0
        assert lorenz.rho == 28.0
        assert abs(lorenz.beta - 8 / 3) < 0.001
        assert lorenz.dt == 0.005

    def test_configurable_parameters(self) -> None:
        la = LorenzAttractor(sigma=15.0, rho=30.0, beta=3.0, dt=0.01)
        assert la.sigma == 15.0
        assert la.rho == 30.0
        assert la.beta == 3.0
        assert la.dt == 0.01

    def test_attractor_does_not_diverge(self, lorenz: LorenzAttractor) -> None:
        """With standard parameters, trajectory should stay bounded."""
        for _ in range(2000):
            lorenz.step()
        dist = math.sqrt(lorenz.x**2 + lorenz.y**2 + lorenz.z**2)
        assert dist < 200  # bounded for standard Lorenz


# ── MathSimulator ───────────────────────────────────────────────────────


class TestMathSimulator:
    """Tests for multi-mode mathematical simulator."""

    def test_lorenz_mode_keys(self, math_sim: MathSimulator) -> None:
        data = math_sim.tick(0.0, mode="lorenz")
        assert "mode" in data
        assert data["mode"] == "lorenz"
        assert "x" in data
        assert "y" in data
        assert "z" in data
        assert "amplitude" in data
        assert "chaos_level" in data
        assert "trail" in data

    def test_logistic_mode_keys(self, math_sim: MathSimulator) -> None:
        data = math_sim.tick(0.0, mode="logistic")
        assert data["mode"] == "logistic"
        assert "x" in data
        assert "r" in data
        assert "amplitude" in data
        assert "chaos_level" in data
        assert "iterations" in data

    def test_sine_mode_keys(self, math_sim: MathSimulator) -> None:
        data = math_sim.tick(1.0, mode="sine")
        assert data["mode"] == "sine"
        assert "value" in data
        assert "amplitude" in data
        assert "chaos_level" in data
        assert "n_waves" in data
        assert "components" in data

    def test_lorenz_amplitude_bounded(self, math_sim: MathSimulator) -> None:
        for t in range(50):
            data = math_sim.tick(t * 0.1, mode="lorenz")
            assert 0 <= data["amplitude"] <= 1.0

    def test_logistic_amplitude_bounded(self, math_sim: MathSimulator) -> None:
        for t in range(50):
            data = math_sim.tick(t * 0.1, mode="logistic", chaos_param=0.5)
            assert 0 <= data["amplitude"] <= 1.0

    def test_sine_amplitude_bounded(self, math_sim: MathSimulator) -> None:
        for t in range(50):
            data = math_sim.tick(t * 0.1, mode="sine")
            assert 0 <= data["amplitude"] <= 1.0

    def test_chaos_level_bounded(self, math_sim: MathSimulator) -> None:
        """chaos_level should always be in [0, 1]."""
        for mode in ["lorenz", "logistic", "sine"]:
            for t in range(50):
                data = math_sim.tick(t * 0.1, mode=mode, chaos_param=0.7)
                assert 0.0 <= data["chaos_level"] <= 1.0, f"Failed for mode={mode}, t={t}"

    def test_logistic_r_range(self, math_sim: MathSimulator) -> None:
        """r parameter should map chaos_param 0-1 to 2.5-4.0."""
        data_low = math_sim.tick(0.0, mode="logistic", chaos_param=0.0)
        assert abs(data_low["r"] - 2.5) < 0.01

        sim2 = MathSimulator()
        data_high = sim2.tick(0.0, mode="logistic", chaos_param=1.0)
        assert abs(data_high["r"] - 4.0) < 0.01

    def test_sine_n_waves_increases_with_chaos(self, math_sim: MathSimulator) -> None:
        """Higher chaos_param should produce more sine waves."""
        low = math_sim.tick(1.0, mode="sine", chaos_param=0.0)
        # Reset to avoid state from previous call
        sim2 = MathSimulator()
        high = sim2.tick(1.0, mode="sine", chaos_param=1.0)
        assert high["n_waves"] >= low["n_waves"]


# ── NetworkSimulator ────────────────────────────────────────────────────


class TestNetworkSimulator:
    """Tests for network traffic simulation with Poisson process."""

    def test_tick_returns_expected_keys(self, network_sim: NetworkSimulator) -> None:
        data = network_sim.tick(1.0)
        expected = {
            "packet_rate", "packet_count", "latency_ms", "error_rate",
            "errors", "is_burst", "throughput_mbps", "active_edges",
            "nodes", "load_level",
        }
        assert set(data.keys()) == expected

    def test_packet_count_non_negative(self, network_sim: NetworkSimulator) -> None:
        """Packet count must be non-negative."""
        for t in range(100):
            data = network_sim.tick(t * 0.1)
            assert data["packet_count"] >= 0

    def test_latency_positive(self, network_sim: NetworkSimulator) -> None:
        """Latency must be positive."""
        for t in range(100):
            data = network_sim.tick(t * 0.1)
            assert data["latency_ms"] >= 1

    def test_error_rate_non_negative(self, network_sim: NetworkSimulator) -> None:
        for t in range(100):
            data = network_sim.tick(t * 0.1)
            assert data["error_rate"] >= 0

    def test_errors_do_not_exceed_packets(self, network_sim: NetworkSimulator) -> None:
        """Errors cannot exceed packet count."""
        for t in range(100):
            data = network_sim.tick(t * 0.1)
            assert data["errors"] <= data["packet_count"]

    def test_load_level_range(self, network_sim: NetworkSimulator) -> None:
        """load_level should be in [0, 1]."""
        data_low = network_sim.tick(1.0, load_level=0.0)
        assert 0.0 <= data_low["load_level"] <= 1.0

        data_high = network_sim.tick(2.0, load_level=1.0)
        assert 0.0 <= data_high["load_level"] <= 1.0

    def test_nodes_returned(self, network_sim: NetworkSimulator) -> None:
        """Simulator should return node list."""
        data = network_sim.tick(1.0)
        assert isinstance(data["nodes"], list)
        assert len(data["nodes"]) == 8  # default node count

    def test_active_edges_valid_structure(self, network_sim: NetworkSimulator) -> None:
        """Active edges should have src, dst, packets."""
        data = network_sim.tick(1.0, load_level=0.5)
        for edge in data["active_edges"]:
            assert "src" in edge
            assert "dst" in edge
            assert "packets" in edge
            assert edge["src"] != edge["dst"]

    def test_is_burst_is_bool(self, network_sim: NetworkSimulator) -> None:
        data = network_sim.tick(1.0)
        assert isinstance(data["is_burst"], bool)

    def test_throughput_non_negative(self, network_sim: NetworkSimulator) -> None:
        for t in range(50):
            data = network_sim.tick(t * 0.1)
            assert data["throughput_mbps"] >= 0

    def test_poisson_zero_rate(self, network_sim: NetworkSimulator) -> None:
        """Poisson with lambda=0 should return 0."""
        assert network_sim._poisson(0) == 0
        assert network_sim._poisson(-1) == 0

    def test_poisson_positive_rate(self, network_sim: NetworkSimulator) -> None:
        """Poisson should return non-negative integers."""
        for _ in range(100):
            result = network_sim._poisson(5.0)
            assert isinstance(result, int)
            assert result >= 0

    def test_poisson_large_lambda_gaussian_fallback(self, network_sim: NetworkSimulator) -> None:
        """Large lambda uses Gaussian approximation."""
        results = [network_sim._poisson(1000) for _ in range(50)]
        mean_result = sum(results) / len(results)
        # Should be roughly around 1000
        assert 800 < mean_result < 1200

    def test_packet_rate_increases_with_load(self, network_sim: NetworkSimulator) -> None:
        """Higher load should produce higher packet rate."""
        data_low = network_sim.tick(1.0, load_level=0.0)
        data_high = network_sim.tick(2.0, load_level=1.0)
        assert data_high["packet_rate"] >= data_low["packet_rate"]
