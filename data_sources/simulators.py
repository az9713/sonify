"""Pure-Python simulators for all 4 lenses. Zero external dependencies."""

from __future__ import annotations

import math
import random
import time


class WeatherSimulator:
    """Generates realistic weather data using layered sinusoids + noise.

    Simulates: temperature, wind_speed, humidity, pressure, rain_probability.
    """

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)
        self._base_temp = 15.0 + self._rng.uniform(-5, 5)
        self._base_wind = 10.0
        self._noise_phase = self._rng.uniform(0, math.tau)

    def tick(self, t: float) -> dict:
        # Temperature: slow diurnal cycle (-5 to 35 C)
        temp = self._base_temp + 10 * math.sin(t * 0.02) + 3 * math.sin(t * 0.13)
        temp += self._rng.gauss(0, 0.5)
        temp = max(-10, min(40, temp))

        # Wind speed: medium oscillation (0-100 km/h)
        wind = self._base_wind + 15 * abs(math.sin(t * 0.05)) + 10 * abs(math.sin(t * 0.17))
        wind += self._rng.gauss(0, 2)
        wind = max(0, min(100, wind))

        # Humidity: slow oscillation inversely correlated with temp (0-100%)
        humidity = 70 - (temp - 15) * 1.5 + 10 * math.sin(t * 0.03)
        humidity += self._rng.gauss(0, 3)
        humidity = max(0, min(100, humidity))

        # Pressure: very slow oscillation (990-1030 hPa)
        pressure = 1013 + 15 * math.sin(t * 0.008 + self._noise_phase)
        pressure += self._rng.gauss(0, 1)
        pressure = max(990, min(1030, pressure))

        # Rain probability: spikes with low pressure + high humidity
        rain_raw = (1030 - pressure) / 40 * 0.5 + humidity / 100 * 0.5
        rain_prob = max(0, min(1, rain_raw + self._rng.gauss(0, 0.05)))

        return {
            "temperature": round(temp, 1),
            "wind_speed": round(wind, 1),
            "humidity": round(humidity, 1),
            "pressure": round(pressure, 1),
            "rain_probability": round(rain_prob, 3),
        }


class CardiacSimulator:
    """Simulates cardiac R-R intervals with configurable heart rate and variability."""

    def __init__(self, resting_hr: float = 72.0) -> None:
        self._resting_hr = resting_hr
        self._rng = random.Random(99)
        self._ecg_buffer: list[float] = []
        self._last_beat_t = 0.0
        self._rr_interval = 60.0 / resting_hr

    def tick(self, t: float, exercise_level: float = 0.0, stress: float = 0.0) -> dict:
        """Generate cardiac data.

        exercise_level: 0.0 (rest) to 1.0 (max exertion)
        stress: 0.0 (calm) to 1.0 (high stress)
        """
        # Heart rate increases with exercise and stress
        target_hr = self._resting_hr + exercise_level * 100 + stress * 30
        target_hr = max(40, min(200, target_hr))

        # R-R interval with HRV (heart rate variability)
        base_rr = 60.0 / target_hr
        # HRV decreases with higher HR (realistic)
        hrv_amplitude = 0.05 * (1.0 - exercise_level * 0.7)
        rr_noise = self._rng.gauss(0, hrv_amplitude * base_rr)
        self._rr_interval = max(0.3, base_rr + rr_noise)

        current_hr = 60.0 / self._rr_interval

        # SDNN (standard deviation of R-R intervals) - simplified
        sdnn = hrv_amplitude * base_rr * 1000  # in ms

        # Generate ECG-like waveform points
        ecg_value = self._ecg_waveform(t)

        # Occasional arrhythmia (PVC-like)
        arrhythmia = False
        if self._rng.random() < 0.005 * (1 + stress):
            arrhythmia = True

        return {
            "heart_rate": round(current_hr, 1),
            "rr_interval_ms": round(self._rr_interval * 1000, 1),
            "hrv_sdnn_ms": round(sdnn, 1),
            "ecg_value": round(ecg_value, 3),
            "arrhythmia": arrhythmia,
            "stress": round(stress, 2),
            "exercise_level": round(exercise_level, 2),
        }

    def _ecg_waveform(self, t: float) -> float:
        """Generate a simplified ECG-like waveform."""
        phase = (t % self._rr_interval) / self._rr_interval
        # P wave
        if 0.0 < phase < 0.1:
            return 0.15 * math.sin(phase / 0.1 * math.pi)
        # QRS complex
        if 0.15 < phase < 0.2:
            sub = (phase - 0.15) / 0.05
            if sub < 0.3:
                return -0.1 * math.sin(sub / 0.3 * math.pi)
            elif sub < 0.6:
                return 1.0 * math.sin((sub - 0.3) / 0.3 * math.pi)
            else:
                return -0.2 * math.sin((sub - 0.6) / 0.4 * math.pi)
        # T wave
        if 0.25 < phase < 0.4:
            return 0.2 * math.sin((phase - 0.25) / 0.15 * math.pi)
        return 0.0


class LorenzAttractor:
    """Lorenz system integrator using Euler method."""

    def __init__(self, sigma: float = 10.0, rho: float = 28.0, beta: float = 8 / 3,
                 dt: float = 0.005) -> None:
        self.sigma = sigma
        self.rho = rho
        self.beta = beta
        self.dt = dt
        self.x = 1.0
        self.y = 1.0
        self.z = 1.0
        self._trail: list[tuple[float, float, float]] = []
        self._max_trail = 500

    def step(self) -> tuple[float, float, float]:
        dx = self.sigma * (self.y - self.x)
        dy = self.x * (self.rho - self.z) - self.y
        dz = self.x * self.y - self.beta * self.z
        self.x += dx * self.dt
        self.y += dy * self.dt
        self.z += dz * self.dt
        self._trail.append((self.x, self.y, self.z))
        if len(self._trail) > self._max_trail:
            self._trail.pop(0)
        return self.x, self.y, self.z

    @property
    def chaos_metric(self) -> float:
        """0..1 estimate of how chaotic the current trajectory is."""
        if len(self._trail) < 10:
            return 0.5
        recent = self._trail[-10:]
        diffs = [
            math.sqrt((b[0]-a[0])**2 + (b[1]-a[1])**2 + (b[2]-a[2])**2)
            for a, b in zip(recent, recent[1:])
        ]
        mean = sum(diffs) / len(diffs)
        variance = sum((d - mean) ** 2 for d in diffs) / len(diffs)
        return min(1.0, variance / 5.0)


class MathSimulator:
    """Generates data from mathematical systems: Lorenz, logistic map, sine superposition."""

    def __init__(self) -> None:
        self._lorenz = LorenzAttractor()
        self._logistic_x = 0.5
        self._rng = random.Random(77)

    def tick(self, t: float, chaos_param: float = 0.7, mode: str = "lorenz") -> dict:
        """
        chaos_param: 0.0 to 1.0, maps to relevant parameter per mode.
        mode: "lorenz", "logistic", "sine"
        """
        if mode == "lorenz":
            # chaos_param controls rho (20-30 range: periodic to chaotic)
            self._lorenz.rho = 20 + chaos_param * 10
            # Step multiple times per tick for smooth animation
            for _ in range(10):
                x, y, z = self._lorenz.step()

            amplitude = math.sqrt(x * x + y * y + z * z) / 50.0  # normalize ~0-1
            # Estimate "chaos" via variance of recent trajectory
            trail = self._lorenz._trail
            if len(trail) > 20:
                recent_x = [p[0] for p in trail[-20:]]
                variance = sum((v - sum(recent_x) / len(recent_x)) ** 2 for v in recent_x) / len(recent_x)
                chaos_level = min(1.0, variance / 200.0)
            else:
                chaos_level = 0.5

            return {
                "mode": "lorenz",
                "x": round(x, 3),
                "y": round(y, 3),
                "z": round(z, 3),
                "amplitude": round(min(1.0, amplitude), 3),
                "chaos_level": round(chaos_level, 3),
                "trail": [(round(p[0], 1), round(p[1], 1)) for p in trail[-200:]],
            }

        elif mode == "logistic":
            # Logistic map: x_{n+1} = r * x_n * (1 - x_n)
            # r from 2.5 (stable) to 4.0 (chaotic)
            r = 2.5 + chaos_param * 1.5
            iterations = []
            x = self._logistic_x
            for _ in range(50):
                x = r * x * (1 - x)
                iterations.append(round(x, 4))
            self._logistic_x = x

            # Chaos detection: unique values in last N iterations
            recent = iterations[-20:]
            unique_ratio = len(set(round(v, 2) for v in recent)) / len(recent)

            return {
                "mode": "logistic",
                "x": round(x, 4),
                "r": round(r, 3),
                "amplitude": round(x, 3),
                "chaos_level": round(unique_ratio, 3),
                "iterations": iterations,
            }

        else:  # sine superposition
            # Superposition of sine waves with varying frequencies
            n_waves = 3 + int(chaos_param * 5)
            value = 0.0
            components = []
            for i in range(n_waves):
                freq = 0.5 + i * 0.7 + chaos_param * i * 0.3
                amp = 1.0 / (i + 1)
                v = amp * math.sin(t * freq)
                value += v
                components.append({"freq": round(freq, 2), "amp": round(amp, 3)})

            # Normalize
            max_amp = sum(1.0 / (i + 1) for i in range(n_waves))
            normalized = (value / max_amp + 1) / 2  # 0-1 range

            return {
                "mode": "sine",
                "value": round(value, 3),
                "amplitude": round(normalized, 3),
                "chaos_level": round(min(1.0, chaos_param * 0.8), 3),
                "n_waves": n_waves,
                "components": components,
                "t": round(t, 2),
            }


class NetworkSimulator:
    """Simulates network traffic using Poisson process with burst events."""

    def __init__(self, base_rate: float = 50.0) -> None:
        self._base_rate = base_rate  # packets per second
        self._rng = random.Random(123)
        self._nodes: list[dict] = [
            {"id": i, "x": self._rng.uniform(0, 1), "y": self._rng.uniform(0, 1)}
            for i in range(8)
        ]
        self._edges: list[dict] = []
        self._burst_until = 0.0
        self._last_t = 0.0

    def tick(self, t: float, load_level: float = 0.5) -> dict:
        """
        load_level: 0.0 (idle) to 1.0 (heavy traffic)
        """
        dt = max(0.001, t - self._last_t)
        self._last_t = t

        # Effective rate with load level
        rate = self._base_rate * (0.1 + load_level * 1.5)

        # Random bursts
        if t > self._burst_until and self._rng.random() < 0.01:
            self._burst_until = t + self._rng.uniform(1, 5)
            rate *= 3

        is_burst = t < self._burst_until

        # Poisson-distributed packet count in this tick interval
        expected = rate * dt
        packet_count = self._poisson(expected)

        # Latency: base + load-dependent + burst spike
        base_latency = 5.0  # ms
        latency = base_latency + load_level * 50 + (30 if is_burst else 0)
        latency += self._rng.gauss(0, 3)
        latency = max(1, latency)

        # Error rate increases with load
        error_rate = 0.001 + load_level * 0.05 + (0.1 if is_burst else 0)
        errors = sum(1 for _ in range(packet_count) if self._rng.random() < error_rate)

        # Active edges (random subset, more during bursts)
        n_active = min(len(self._nodes), 2 + int(load_level * 4) + (3 if is_burst else 0))
        active_pairs = []
        for _ in range(min(n_active, 6)):
            src = self._rng.randint(0, len(self._nodes) - 1)
            dst = self._rng.randint(0, len(self._nodes) - 1)
            if src != dst:
                active_pairs.append({"src": src, "dst": dst, "packets": self._rng.randint(1, 5)})

        # Throughput (simplified MB/s)
        throughput = packet_count * 1.5 / 1000  # rough KB->MB

        return {
            "packet_rate": round(rate, 1),
            "packet_count": packet_count,
            "latency_ms": round(latency, 1),
            "error_rate": round(error_rate, 4),
            "errors": errors,
            "is_burst": is_burst,
            "throughput_mbps": round(throughput, 3),
            "active_edges": active_pairs,
            "nodes": self._nodes,
            "load_level": round(load_level, 2),
        }

    def _poisson(self, lam: float) -> int:
        """Simple Poisson random variate via Knuth's algorithm."""
        if lam <= 0:
            return 0
        if lam > 500:
            # Approximate with Gaussian for large lambda
            return max(0, int(self._rng.gauss(lam, math.sqrt(lam))))
        L = math.exp(-lam)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= self._rng.random()
        return k - 1
