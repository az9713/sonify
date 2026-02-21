"""Tests for ElevenLabsBridge: _build_prompt(), debounce logic, prompt thresholds."""

from __future__ import annotations

import pytest

from lenses.base import ControlState
from elevenlabs_bridge import ElevenLabsBridge


# ── _build_prompt() ────────────────────────────────────────────────────


class TestBuildPrompt:
    """Verify _build_prompt() converts ControlState to correct text."""

    def test_returns_string(self) -> None:
        result = ElevenLabsBridge._build_prompt(ControlState())
        assert isinstance(result, str)

    def test_includes_prompts_text(self) -> None:
        cs = ControlState(prompts=[{"text": "chill lo-fi", "weight": 1.0}])
        result = ElevenLabsBridge._build_prompt(cs)
        assert "chill lo-fi" in result

    def test_prompts_sorted_by_weight_desc(self) -> None:
        cs = ControlState(prompts=[
            {"text": "low weight", "weight": 0.3},
            {"text": "high weight", "weight": 1.0},
        ])
        result = ElevenLabsBridge._build_prompt(cs)
        # high weight should come before low weight
        assert result.index("high weight") < result.index("low weight")

    def test_always_ends_with_instrumental(self) -> None:
        result = ElevenLabsBridge._build_prompt(ControlState())
        assert result.endswith("instrumental")

    # ── BPM thresholds ──────────────────────────────────────────────

    def test_slow_tempo_below_80(self) -> None:
        cs = ControlState(bpm=70)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "slow tempo" in result

    def test_moderate_tempo_80_to_110(self) -> None:
        cs = ControlState(bpm=90)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "moderate tempo" in result

    def test_upbeat_tempo_110_to_140(self) -> None:
        cs = ControlState(bpm=125)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "upbeat tempo" in result

    def test_fast_tempo_above_140(self) -> None:
        cs = ControlState(bpm=160)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "fast energetic tempo" in result

    # ── Density thresholds ──────────────────────────────────────────

    def test_sparse_arrangement_low_density(self) -> None:
        cs = ControlState(density=0.1)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "sparse minimal arrangement" in result

    def test_dense_arrangement_high_density(self) -> None:
        cs = ControlState(density=0.8)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "dense layered arrangement" in result

    def test_no_arrangement_mid_density(self) -> None:
        cs = ControlState(density=0.5)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "sparse" not in result
        assert "dense" not in result

    # ── Brightness thresholds ───────────────────────────────────────

    def test_dark_tones_low_brightness(self) -> None:
        cs = ControlState(brightness=0.1)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "dark muted tones" in result

    def test_bright_tones_high_brightness(self) -> None:
        cs = ControlState(brightness=0.9)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "bright shimmering tones" in result

    def test_no_tone_descriptor_mid_brightness(self) -> None:
        cs = ControlState(brightness=0.5)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "dark muted" not in result
        assert "bright shimmering" not in result

    # ── Scale mapping ───────────────────────────────────────────────

    def test_c_major_mood(self) -> None:
        cs = ControlState(scale="C_MAJOR_A_MINOR")
        result = ElevenLabsBridge._build_prompt(cs)
        assert "C major" in result
        assert "uplifting" in result

    def test_d_major_mood(self) -> None:
        cs = ControlState(scale="D_MAJOR_B_MINOR")
        result = ElevenLabsBridge._build_prompt(cs)
        assert "D major" in result

    def test_ab_major_mood(self) -> None:
        cs = ControlState(scale="A_FLAT_MAJOR_F_MINOR")
        result = ElevenLabsBridge._build_prompt(cs)
        assert "F minor" in result
        assert "melancholic" in result

    def test_gb_major_mood(self) -> None:
        cs = ControlState(scale="G_FLAT_MAJOR_E_FLAT_MINOR")
        result = ElevenLabsBridge._build_prompt(cs)
        assert "E-flat minor" in result
        assert "brooding" in result

    def test_unspecified_scale_no_mood(self) -> None:
        cs = ControlState(scale="SCALE_UNSPECIFIED")
        result = ElevenLabsBridge._build_prompt(cs)
        assert "major" not in result.lower() or "minor" not in result.lower()

    # ── Mute flags ──────────────────────────────────────────────────

    def test_mute_bass_prompt(self) -> None:
        cs = ControlState(mute_bass=True)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "no bass" in result

    def test_no_mute_bass_prompt(self) -> None:
        cs = ControlState(mute_bass=False)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "no bass" not in result

    def test_mute_drums_prompt(self) -> None:
        cs = ControlState(mute_drums=True)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "no drums" in result

    def test_no_mute_drums_prompt(self) -> None:
        cs = ControlState(mute_drums=False)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "no drums" not in result

    # ── Temperature thresholds ──────────────────────────────────────

    def test_experimental_high_temperature(self) -> None:
        cs = ControlState(temperature=2.5)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "experimental" in result

    def test_structured_low_temperature(self) -> None:
        cs = ControlState(temperature=0.3)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "structured" in result

    def test_no_temperature_descriptor_mid(self) -> None:
        cs = ControlState(temperature=1.0)
        result = ElevenLabsBridge._build_prompt(cs)
        assert "experimental" not in result
        assert "structured" not in result

    # ── Prompt combination ──────────────────────────────────────────

    def test_all_thresholds_combined(self) -> None:
        """All extreme values should produce all descriptors."""
        cs = ControlState(
            bpm=180,
            density=0.1,
            brightness=0.9,
            scale="C_MAJOR_A_MINOR",
            mute_bass=True,
            mute_drums=True,
            temperature=2.5,
            prompts=[{"text": "test prompt", "weight": 1.0}],
        )
        result = ElevenLabsBridge._build_prompt(cs)
        assert "test prompt" in result
        assert "fast energetic tempo" in result
        assert "sparse minimal arrangement" in result
        assert "bright shimmering tones" in result
        assert "C major" in result
        assert "no bass" in result
        assert "no drums" in result
        assert "experimental" in result
        assert "instrumental" in result

    def test_empty_prompts(self) -> None:
        """Empty prompts list should still produce a valid string."""
        cs = ControlState(prompts=[])
        result = ElevenLabsBridge._build_prompt(cs)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_prompt_with_missing_weight(self) -> None:
        """Prompts without a weight key should still work."""
        cs = ControlState(prompts=[{"text": "test"}])
        result = ElevenLabsBridge._build_prompt(cs)
        assert "test" in result


# ── Debounce constants ──────────────────────────────────────────────────


class TestElevenLabsBridgeDebounce:
    """Verify debounce configuration."""

    def test_debounce_seconds_is_2(self) -> None:
        assert ElevenLabsBridge._DEBOUNCE_SECONDS == 2.0

    def test_chunk_bytes_is_9600(self) -> None:
        assert ElevenLabsBridge._CHUNK_BYTES == 9600

    def test_frames_per_chunk_is_2400(self) -> None:
        assert ElevenLabsBridge._FRAMES_PER_CHUNK == 2400


# ── Mono-to-stereo conversion ──────────────────────────────────────────


class TestMonoToStereo:
    """Verify mono-to-stereo PCM conversion."""

    def test_doubles_sample_count(self) -> None:
        import struct
        mono = struct.pack("<3h", 100, -200, 300)
        stereo = ElevenLabsBridge._mono_to_stereo(mono)
        assert len(stereo) == len(mono) * 2

    def test_duplicates_channels(self) -> None:
        import struct
        mono = struct.pack("<3h", 100, -200, 300)
        stereo = ElevenLabsBridge._mono_to_stereo(mono)
        samples = struct.unpack(f"<{len(stereo) // 2}h", stereo)
        # Should be (100, 100, -200, -200, 300, 300)
        assert samples == (100, 100, -200, -200, 300, 300)


# ── Bridge initialization without API key ──────────────────────────────


class TestElevenLabsBridgeInit:
    """Verify bridge falls back to mock without API key."""

    def test_no_api_key_uses_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        bridge = ElevenLabsBridge()
        assert bridge.is_mock is True
        assert bridge._mock is not None

    def test_gen_id_starts_at_zero(self) -> None:
        bridge = ElevenLabsBridge()
        assert bridge._gen_id == 0

    def test_initial_prompts_empty(self) -> None:
        bridge = ElevenLabsBridge()
        assert bridge._current_prompt == ""
        assert bridge._committed_prompt == ""
        assert bridge._pending_prompt == ""
