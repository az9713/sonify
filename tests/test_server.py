"""Tests for the FastAPI server: WebSocket endpoint, lens switching, parameter setting."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient


# ── Module-level setup ──────────────────────────────────────────────────

# We need to ensure no API keys are set so the server uses mock audio.
# Also, we must import the app only after ensuring clean env.


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no API keys are set during testing."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI TestClient."""
    # Import here to pick up monkeypatched env
    from server import app
    return TestClient(app)


# ── HTTP endpoints ──────────────────────────────────────────────────────


class TestHTTPEndpoints:
    """Test non-WebSocket HTTP endpoints."""

    def test_index_returns_html(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200

    def test_api_lenses_returns_all_four(self, client: TestClient) -> None:
        resp = client.get("/api/lenses")
        assert resp.status_code == 200
        data = resp.json()
        assert "atmosphere" in data
        assert "pulse" in data
        assert "lattice" in data
        assert "flow" in data

    def test_api_lenses_have_description(self, client: TestClient) -> None:
        resp = client.get("/api/lenses")
        data = resp.json()
        for name, info in data.items():
            assert "description" in info
            assert isinstance(info["description"], str)
            assert len(info["description"]) > 0

    def test_api_lenses_have_parameters(self, client: TestClient) -> None:
        resp = client.get("/api/lenses")
        data = resp.json()
        for name, info in data.items():
            assert "parameters" in info
            assert isinstance(info["parameters"], list)


# ── WebSocket endpoint ──────────────────────────────────────────────────


class TestWebSocket:
    """Test the /ws WebSocket endpoint."""

    def test_connect_receives_init(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_text()
            data = json.loads(msg)
            assert data["type"] == "init"
            assert "lens" in data
            assert "lenses" in data
            assert "backend" in data

    def test_init_message_has_lenses_list(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_text()
            data = json.loads(msg)
            lenses = data["lenses"]
            assert "atmosphere" in lenses
            assert "pulse" in lenses
            assert "lattice" in lenses
            assert "flow" in lenses

    def test_init_message_has_backend(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_text()
            data = json.loads(msg)
            assert data["backend"] in ("mock", "lyria", "elevenlabs")

    def test_init_message_has_paused_state(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_text()
            data = json.loads(msg)
            assert "paused" in data
            assert isinstance(data["paused"], bool)

    def test_switch_lens(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            # Read init message
            ws.receive_text()
            # Send switch_lens
            ws.send_text(json.dumps({
                "type": "switch_lens",
                "lens": "pulse",
            }))
            # The server processes the switch internally; no direct response expected
            # but it should not error out

    def test_set_param(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_text(json.dumps({
                "type": "set_param",
                "name": "wind_speed",
                "value": 15.0,
            }))
            # Should not error out

    def test_pause_and_play(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()

            # Pause
            ws.send_text(json.dumps({"type": "pause"}))
            # Should receive paused broadcast
            msg = ws.receive_text()
            data = json.loads(msg)
            assert data["type"] == "paused"
            assert data["paused"] is True

            # Play
            ws.send_text(json.dumps({"type": "play"}))
            msg = ws.receive_text()
            data = json.loads(msg)
            assert data["type"] == "paused"
            assert data["paused"] is False

    def test_toggle_live_weather(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_text(json.dumps({
                "type": "toggle_live",
                "enabled": True,
            }))
            # Should not error out

    def test_switch_to_invalid_lens_no_crash(self, client: TestClient) -> None:
        """Switching to a non-existent lens should not crash."""
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_text(json.dumps({
                "type": "switch_lens",
                "lens": "nonexistent_lens",
            }))
            # Should not error out; lens stays the same


# ── Server helpers ──────────────────────────────────────────────────────


class TestServerHelpers:
    """Test module-level helpers."""

    def test_create_lens_valid(self) -> None:
        from server import create_lens
        lens = create_lens("atmosphere")
        assert lens.name == "atmosphere"

    def test_create_lens_invalid_falls_back(self) -> None:
        from server import create_lens
        lens = create_lens("nonexistent")
        assert lens.name == "atmosphere"  # defaults to atmosphere

    def test_create_bridge_no_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        from server import create_bridge
        bridge = create_bridge()
        # Without keys, should create LyriaBridge (which falls back to mock)
        from lyria_bridge import LyriaBridge
        assert isinstance(bridge, LyriaBridge)

    def test_get_backend_name_mock(self) -> None:
        from server import get_backend_name
        # The module-level bridge is mock without API keys
        name = get_backend_name()
        assert name in ("mock", "lyria", "elevenlabs")
