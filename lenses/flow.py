"""Flow lens: network traffic -> music + force-directed graph visualization."""

from __future__ import annotations

import math
import random

from lenses.base import ControlState, Lens


class FlowLens(Lens):
    name = "flow"
    description = "Network traffic as rhythm and light"
    tick_hz = 5.0

    parameters = [
        {
            "name": "packet_rate", "label": "Packet Rate (/s)",
            "min": 1, "max": 200, "step": 1, "default": 30.0,
            "effects": [
                "\u2192 Density: rate / 200 (idle = thin, saturated = dense)",
                "\u2192 BPM: 80 + load \u00d7 40 (higher load = faster tempo)",
            ],
        },
        {
            "name": "latency", "label": "Latency (ms)",
            "min": 1, "max": 200, "step": 1, "default": 50.0,
            "effects": [
                "\u2192 Brightness: 1.0 \u2212 latency / 200 (low latency = bright, high = dark)",
            ],
        },
        {
            "name": "burst", "label": "Burst Active",
            "min": 0, "max": 1, "step": 1, "default": 0.0,
            "effects": [
                "\u2192 BPM: adds +50 during burst (sudden tempo spike)",
                "\u2192 Prompts: adds 'huge drop, intense, crunchy distortion'",
            ],
        },
        {
            "name": "error_rate", "label": "Error Rate",
            "min": 0, "max": 0.2, "step": 0.01, "default": 0.01,
            "effects": [
                "\u2192 Prompts: adds 'glitchy effects, metallic twang' when > 0.05",
            ],
        },
        {
            "name": "num_nodes", "label": "Node Count",
            "min": 3, "max": 16, "step": 1, "default": 8.0,
            "effects": [
                "\u2192 Visualization only (number of nodes in network graph)",
            ],
        },
    ]

    def __init__(self) -> None:
        super().__init__()
        self._node_positions: list[dict] | None = None
        self._node_activity: list[float] = []

    def _ensure_nodes(self, n: int) -> None:
        if self._node_positions is None or len(self._node_positions) != n:
            rng = random.Random(42)
            self._node_positions = [
                {"id": i, "x": rng.uniform(0.1, 0.9), "y": rng.uniform(0.1, 0.9)}
                for i in range(n)
            ]
            self._node_activity = [0.0] * n

    def tick(self, t: float) -> dict:
        packet_rate = self._params["packet_rate"]
        latency = self._params["latency"]
        is_burst = self._params["burst"] >= 0.5
        error_rate = self._params["error_rate"]
        n = int(self._params["num_nodes"])

        self._ensure_nodes(n)

        # Derive packet count from rate
        packet_count = max(0, int(random.gauss(packet_rate * 0.2, packet_rate * 0.05)))

        # Errors from error rate
        errors = sum(1 for _ in range(packet_count) if random.random() < error_rate)

        # Throughput
        throughput = packet_count * 1.5 / 1000

        # Update per-node activity
        load = min(1.0, packet_rate / 200)
        for i in range(n):
            activity = random.random() * load * (3.0 if is_burst else 1.0)
            self._node_activity[i] = 0.7 * self._node_activity[i] + 0.3 * min(1.0, activity)

        # Generate edges
        active_edges = []
        n_edges = min(20, int(packet_rate * 0.1) + (5 if is_burst else 0))
        for _ in range(n_edges):
            src = random.randint(0, n - 1)
            dst = random.randint(0, n - 1)
            if src != dst:
                active_edges.append({"src": src, "dst": dst, "packets": random.randint(1, 5)})

        return {
            "packet_rate": packet_rate,
            "packet_count": packet_count,
            "latency_ms": latency,
            "error_rate": error_rate,
            "errors": errors,
            "is_burst": is_burst,
            "throughput_mbps": round(throughput, 3),
            "active_edges": active_edges,
            "nodes": self._node_positions,
            "node_activity": self._node_activity[:n],
            "load_level": load,
        }

    def map(self, data: dict) -> ControlState:
        packet_rate = data["packet_rate"]
        latency = data["latency_ms"]
        is_burst = data["is_burst"]
        error_rate = data["error_rate"]
        load = data["load_level"]

        # Packet rate -> Density
        density = self._ema("density", min(1.0, packet_rate / 200))

        # Latency -> inverse Brightness
        brightness = self._ema("brightness", max(0, 1.0 - latency / 200))

        # Burst -> BPM spike
        base_bpm = 80 + load * 40
        if is_burst:
            bpm = int(self._ema("bpm", min(200, base_bpm + 50)))
        else:
            bpm = int(self._ema("bpm", base_bpm))

        prompts = []
        if load < 0.3:
            prompts.append({"text": "Ambient, minimal, spacey synths", "weight": 1.0})
        elif load < 0.7:
            prompts.append({"text": "Chiptune, electronic, steady", "weight": 1.0})
            prompts.append({"text": "Synth pads, digital", "weight": 0.5})
        else:
            prompts.append({"text": "Drum & Bass, intense, fast", "weight": 1.0})
            prompts.append({"text": "808 Hip Hop Beat, heavy", "weight": 0.6})

        if is_burst:
            prompts.append({"text": "Huge drop, intense, crunchy distortion", "weight": 0.8})

        if error_rate > 0.05:
            prompts.append({"text": "Glitchy effects, metallic twang", "weight": error_rate * 5})

        return ControlState(
            bpm=bpm,
            density=density,
            brightness=brightness,
            guidance=3.5 + load * 1.5,
            prompts=prompts,
            temperature=1.0 + load * 0.5,
        )

    def viz_state(self, data: dict) -> dict:
        load = data["load_level"]
        is_burst = data["is_burst"]

        if is_burst:
            color = {"r": 255, "g": 60, "b": 60}
        elif load > 0.6:
            color = {"r": 255, "g": 200, "b": 50}
        else:
            color = {"r": 50, "g": 200, "b": 200}

        nodes = [
            {"id": n["id"], "x": n["x"], "y": n["y"]}
            for n in data["nodes"]
        ]

        return {
            "type": "flow",
            "nodes": nodes,
            "active_edges": data["active_edges"],
            "is_burst": is_burst,
            "pulse_intensity": min(1.0, data["packet_count"] / 50),
            "color": color,
            "node_glow": 0.3 + load * 0.7,
            "data": {
                "packet_rate": round(data["packet_rate"], 1),
                "latency_ms": round(data["latency_ms"], 1),
                "errors": data["errors"],
                "throughput": data["throughput_mbps"],
                "load": round(load, 2),
            },
        }
