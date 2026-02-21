"""Tests for MockAudioGenerator: PCM format, scale quantization, control mapping."""

from __future__ import annotations

import math
import struct

import pytest

from lenses.base import ControlState
from lyria_bridge import MockAudioGenerator


# ── PCM output format ──────────────────────────────────────────────────


class TestMockAudioPCMFormat:
    """Verify PCM output meets the documented spec."""

    def test_chunk_size_bytes(self, mock_audio: MockAudioGenerator) -> None:
        """Default chunk: 2400 frames * 2 channels * 2 bytes = 9600 bytes."""
        chunk = mock_audio.generate_chunk(num_samples=2400)
        assert len(chunk) == 9600

    def test_chunk_size_custom(self, mock_audio: MockAudioGenerator) -> None:
        """Custom frame count should produce proportional bytes."""
        chunk = mock_audio.generate_chunk(num_samples=1200)
        # 1200 frames * 2 channels * 2 bytes = 4800
        assert len(chunk) == 4800

    def test_samples_16bit_signed(self, mock_audio: MockAudioGenerator) -> None:
        """All samples must be valid 16-bit signed integers."""
        chunk = mock_audio.generate_chunk(num_samples=2400)
        n_samples = len(chunk) // 2
        samples = struct.unpack(f"<{n_samples}h", chunk)
        for s in samples:
            assert -32768 <= s <= 32767

    def test_samples_within_clamp_range(self, mock_audio: MockAudioGenerator) -> None:
        """Samples should be clamped to [-32767, 32767] (the code uses max(-32767, min(32767, ...)))."""
        chunk = mock_audio.generate_chunk(num_samples=2400)
        n_samples = len(chunk) // 2
        samples = struct.unpack(f"<{n_samples}h", chunk)
        for s in samples:
            assert -32767 <= s <= 32767

    def test_stereo_pairs(self, mock_audio: MockAudioGenerator) -> None:
        """Left and right channels should have identical samples (mono signal duplicated)."""
        chunk = mock_audio.generate_chunk(num_samples=100)
        n_samples = len(chunk) // 2
        samples = struct.unpack(f"<{n_samples}h", chunk)
        # Samples come in L, R pairs
        for i in range(0, len(samples), 2):
            assert samples[i] == samples[i + 1]

    def test_mono_generator(self) -> None:
        """Single-channel generator should produce half the bytes."""
        gen = MockAudioGenerator(channels=1)
        chunk = gen.generate_chunk(num_samples=2400)
        # 2400 frames * 1 channel * 2 bytes = 4800
        assert len(chunk) == 4800

    def test_not_silent(self, mock_audio: MockAudioGenerator) -> None:
        """Default generator should produce audible output (not all zeros)."""
        chunk = mock_audio.generate_chunk(num_samples=2400)
        n_samples = len(chunk) // 2
        samples = struct.unpack(f"<{n_samples}h", chunk)
        assert any(s != 0 for s in samples)

    def test_multiple_chunks_no_error(self, mock_audio: MockAudioGenerator) -> None:
        """Generating many chunks should not raise errors."""
        for _ in range(100):
            chunk = mock_audio.generate_chunk(num_samples=2400)
            assert len(chunk) == 9600


# ── Scale quantization ─────────────────────────────────────────────────


class TestScaleQuantization:
    """Verify frequencies snap to the correct pitch classes."""

    def _midi_to_freq(self, midi: int) -> float:
        return 440.0 * (2.0 ** ((midi - 69) / 12.0))

    def _freq_to_pitch_class(self, freq: float) -> int:
        midi = 69.0 + 12.0 * math.log2(freq / 440.0)
        return round(midi) % 12

    def test_quantize_c_major_snaps_correctly(self, mock_audio: MockAudioGenerator) -> None:
        """Frequencies quantized to C Major should have pitch classes in {0,2,4,5,7,9,11}."""
        c_major = {0, 2, 4, 5, 7, 9, 11}
        # Test a range of frequencies
        for midi in range(48, 84):
            freq = self._midi_to_freq(midi)
            quantized = mock_audio._quantize_to_scale(freq, c_major)
            pc = self._freq_to_pitch_class(quantized)
            assert pc in c_major, f"MIDI {midi} -> freq {freq} -> quantized {quantized} -> PC {pc} not in C Major"

    def test_quantize_d_major_snaps_correctly(self, mock_audio: MockAudioGenerator) -> None:
        """Frequencies quantized to D Major should have correct pitch classes."""
        d_major = {1, 2, 4, 6, 7, 9, 11}
        for midi in range(48, 84):
            freq = self._midi_to_freq(midi)
            quantized = mock_audio._quantize_to_scale(freq, d_major)
            pc = self._freq_to_pitch_class(quantized)
            assert pc in d_major, f"MIDI {midi} -> PC {pc} not in D Major"

    def test_quantize_ab_major_snaps_correctly(self, mock_audio: MockAudioGenerator) -> None:
        """Ab Major scale quantization."""
        ab_major = {0, 1, 3, 5, 7, 8, 10}
        for midi in range(48, 84):
            freq = self._midi_to_freq(midi)
            quantized = mock_audio._quantize_to_scale(freq, ab_major)
            pc = self._freq_to_pitch_class(quantized)
            assert pc in ab_major, f"MIDI {midi} -> PC {pc} not in Ab Major"

    def test_quantize_gb_major_snaps_correctly(self, mock_audio: MockAudioGenerator) -> None:
        """Gb Major scale quantization."""
        gb_major = {1, 3, 5, 6, 8, 10, 11}
        for midi in range(48, 84):
            freq = self._midi_to_freq(midi)
            quantized = mock_audio._quantize_to_scale(freq, gb_major)
            pc = self._freq_to_pitch_class(quantized)
            assert pc in gb_major, f"MIDI {midi} -> PC {pc} not in Gb Major"

    def test_quantize_no_scale_passthrough(self, mock_audio: MockAudioGenerator) -> None:
        """With no scale (None), frequency should pass through unchanged."""
        freq = 261.63  # middle C
        result = mock_audio._quantize_to_scale(freq, None)
        assert result == freq

    def test_quantize_zero_freq(self, mock_audio: MockAudioGenerator) -> None:
        """Zero frequency should pass through unchanged."""
        result = mock_audio._quantize_to_scale(0, {0, 2, 4, 5, 7, 9, 11})
        assert result == 0

    def test_quantize_negative_freq(self, mock_audio: MockAudioGenerator) -> None:
        """Negative frequency should pass through unchanged."""
        result = mock_audio._quantize_to_scale(-100, {0, 2, 4, 5, 7, 9, 11})
        assert result == -100

    def test_quantize_a440_in_c_major(self, mock_audio: MockAudioGenerator) -> None:
        """A440 (pitch class 9) is in C Major; should stay at 440."""
        c_major = {0, 2, 4, 5, 7, 9, 11}
        result = mock_audio._quantize_to_scale(440.0, c_major)
        assert abs(result - 440.0) < 0.01


# ── update_from_controls applies all 8 fields ──────────────────────────


class TestUpdateFromControls:
    """Verify that update_from_controls maps all 8 relevant ControlState fields."""

    def test_brightness_affects_frequency(self, mock_audio: MockAudioGenerator) -> None:
        """Higher brightness -> higher target frequency."""
        mock_audio.update_from_controls(ControlState(brightness=0.0, scale="SCALE_UNSPECIFIED"))
        low_freq = mock_audio._target_freq

        mock2 = MockAudioGenerator()
        mock2.update_from_controls(ControlState(brightness=1.0, scale="SCALE_UNSPECIFIED"))
        high_freq = mock2._target_freq

        assert high_freq > low_freq

    def test_density_affects_harmonics(self, mock_audio: MockAudioGenerator) -> None:
        """Higher density -> more harmonics."""
        mock_audio.update_from_controls(ControlState(density=0.0))
        low_harmonics = len(mock_audio._harmonics)

        mock2 = MockAudioGenerator()
        mock2.update_from_controls(ControlState(density=1.0))
        high_harmonics = len(mock2._harmonics)

        assert high_harmonics >= low_harmonics

    def test_bpm_affects_lfo_rate(self, mock_audio: MockAudioGenerator) -> None:
        """BPM maps to LFO rate = bpm / 60."""
        mock_audio.update_from_controls(ControlState(bpm=120))
        assert abs(mock_audio._lfo_rate - 2.0) < 0.01

        mock_audio.update_from_controls(ControlState(bpm=60))
        assert abs(mock_audio._lfo_rate - 1.0) < 0.01

    def test_guidance_affects_lfo_depth(self, mock_audio: MockAudioGenerator) -> None:
        """Higher guidance -> deeper LFO."""
        mock_audio.update_from_controls(ControlState(guidance=0.0))
        low_depth = mock_audio._lfo_depth

        mock2 = MockAudioGenerator()
        mock2.update_from_controls(ControlState(guidance=6.0))
        high_depth = mock2._lfo_depth

        assert high_depth >= low_depth

    def test_temperature_affects_noise(self, mock_audio: MockAudioGenerator) -> None:
        """Higher temperature -> higher noise level."""
        mock_audio.update_from_controls(ControlState(temperature=0.0))
        low_noise = mock_audio._noise_level

        mock2 = MockAudioGenerator()
        mock2.update_from_controls(ControlState(temperature=3.0))
        high_noise = mock2._noise_level

        assert high_noise > low_noise

    def test_temperature_zero_means_no_noise(self, mock_audio: MockAudioGenerator) -> None:
        mock_audio.update_from_controls(ControlState(temperature=0.0))
        assert mock_audio._noise_level == 0.0

    def test_mute_bass_removes_harmonics(self, mock_audio: MockAudioGenerator) -> None:
        """Muting bass should remove fundamental + 2nd harmonic."""
        mock_audio.update_from_controls(ControlState(density=1.0, mute_bass=False))
        normal_count = len(mock_audio._harmonics)

        mock2 = MockAudioGenerator()
        mock2.update_from_controls(ControlState(density=1.0, mute_bass=True))
        muted_count = len(mock2._harmonics)

        assert muted_count < normal_count
        assert muted_count == normal_count - 2

    def test_mute_drums_suppresses_lfo(self, mock_audio: MockAudioGenerator) -> None:
        """Muting drums should set _mute_drums flag."""
        mock_audio.update_from_controls(ControlState(mute_drums=True))
        assert mock_audio._mute_drums is True

        mock_audio.update_from_controls(ControlState(mute_drums=False))
        assert mock_audio._mute_drums is False

    def test_scale_quantization_applied(self, mock_audio: MockAudioGenerator) -> None:
        """Scale should quantize the target frequency."""
        mock_audio.update_from_controls(ControlState(
            brightness=0.5, scale="C_MAJOR_A_MINOR",
        ))
        freq = mock_audio._target_freq
        # Should be quantized to a C Major pitch class
        midi = 69.0 + 12.0 * math.log2(freq / 440.0)
        pc = round(midi) % 12
        assert pc in {0, 2, 4, 5, 7, 9, 11}

    def test_unknown_scale_no_quantization(self, mock_audio: MockAudioGenerator) -> None:
        """Unknown scale should not quantize (passthrough)."""
        mock_audio.update_from_controls(ControlState(
            brightness=0.5, scale="SCALE_UNSPECIFIED",
        ))
        # raw_freq = 110 + 0.5 * 330 = 275
        expected_raw = 110 + 0.5 * 330
        assert abs(mock_audio._target_freq - expected_raw) < 0.01

    def test_output_changes_after_update(self, mock_audio: MockAudioGenerator) -> None:
        """Output should differ after changing controls."""
        chunk1 = mock_audio.generate_chunk(num_samples=100)
        mock_audio.update_from_controls(ControlState(brightness=1.0, bpm=200, density=1.0))
        # Generate a couple chunks for the frequency glide to take effect
        mock_audio.generate_chunk(num_samples=2400)
        chunk2 = mock_audio.generate_chunk(num_samples=100)
        assert chunk1 != chunk2


# ── Deterministic seeded RNG ────────────────────────────────────────────


class TestMockAudioDeterminism:
    """Verify that the RNG seed produces deterministic output."""

    def test_same_seed_same_output(self) -> None:
        gen1 = MockAudioGenerator()
        gen2 = MockAudioGenerator()
        # Both seeded with 42 by default
        chunk1 = gen1.generate_chunk(num_samples=2400)
        chunk2 = gen2.generate_chunk(num_samples=2400)
        assert chunk1 == chunk2
