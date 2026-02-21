"""Tests for ControlState dataclass: clamped(), diff(), and defaults."""

from __future__ import annotations

import pytest

from lenses.base import ControlState


# ── Default values ──────────────────────────────────────────────────────


class TestControlStateDefaults:
    """Verify ControlState defaults match documented values."""

    def test_default_bpm(self, default_controls: ControlState) -> None:
        assert default_controls.bpm == 120

    def test_default_density(self, default_controls: ControlState) -> None:
        assert default_controls.density == 0.5

    def test_default_brightness(self, default_controls: ControlState) -> None:
        assert default_controls.brightness == 0.5

    def test_default_guidance(self, default_controls: ControlState) -> None:
        assert default_controls.guidance == 4.0

    def test_default_scale(self, default_controls: ControlState) -> None:
        assert default_controls.scale == "SCALE_UNSPECIFIED"

    def test_default_prompts(self, default_controls: ControlState) -> None:
        assert default_controls.prompts == [{"text": "ambient", "weight": 1.0}]

    def test_default_mute_bass(self, default_controls: ControlState) -> None:
        assert default_controls.mute_bass is False

    def test_default_mute_drums(self, default_controls: ControlState) -> None:
        assert default_controls.mute_drums is False

    def test_default_temperature(self, default_controls: ControlState) -> None:
        assert default_controls.temperature == 1.1


# ── clamped() range enforcement ─────────────────────────────────────────


class TestControlStateClamped:
    """Verify clamped() enforces Lyria-valid ranges."""

    def test_bpm_clamped_low(self) -> None:
        cs = ControlState(bpm=0).clamped()
        assert cs.bpm == 60

    def test_bpm_clamped_high(self) -> None:
        cs = ControlState(bpm=999).clamped()
        assert cs.bpm == 200

    def test_bpm_within_range_unchanged(self) -> None:
        cs = ControlState(bpm=120).clamped()
        assert cs.bpm == 120

    def test_bpm_boundary_low(self) -> None:
        cs = ControlState(bpm=60).clamped()
        assert cs.bpm == 60

    def test_bpm_boundary_high(self) -> None:
        cs = ControlState(bpm=200).clamped()
        assert cs.bpm == 200

    def test_bpm_clamped_is_int(self) -> None:
        cs = ControlState(bpm=120.7).clamped()
        assert isinstance(cs.bpm, int)
        assert cs.bpm == 120

    def test_density_clamped_low(self) -> None:
        cs = ControlState(density=-0.5).clamped()
        assert cs.density == 0.0

    def test_density_clamped_high(self) -> None:
        cs = ControlState(density=1.5).clamped()
        assert cs.density == 1.0

    def test_density_within_range(self) -> None:
        cs = ControlState(density=0.5).clamped()
        assert cs.density == 0.5

    def test_brightness_clamped_low(self) -> None:
        cs = ControlState(brightness=-0.5).clamped()
        assert cs.brightness == 0.0

    def test_brightness_clamped_high(self) -> None:
        cs = ControlState(brightness=1.5).clamped()
        assert cs.brightness == 1.0

    def test_brightness_within_range(self) -> None:
        cs = ControlState(brightness=0.7).clamped()
        assert cs.brightness == 0.7

    def test_guidance_clamped_low(self) -> None:
        cs = ControlState(guidance=-1.0).clamped()
        assert cs.guidance == 0.0

    def test_guidance_clamped_high(self) -> None:
        cs = ControlState(guidance=10.0).clamped()
        assert cs.guidance == 6.0

    def test_guidance_within_range(self) -> None:
        cs = ControlState(guidance=3.0).clamped()
        assert cs.guidance == 3.0

    def test_temperature_clamped_low(self) -> None:
        cs = ControlState(temperature=-1.0).clamped()
        assert cs.temperature == 0.0

    def test_temperature_clamped_high(self) -> None:
        cs = ControlState(temperature=5.0).clamped()
        assert cs.temperature == 3.0

    def test_temperature_within_range(self) -> None:
        cs = ControlState(temperature=1.5).clamped()
        assert cs.temperature == 1.5

    def test_clamped_preserves_scale(self) -> None:
        cs = ControlState(scale="C_MAJOR_A_MINOR").clamped()
        assert cs.scale == "C_MAJOR_A_MINOR"

    def test_clamped_preserves_prompts(self) -> None:
        prompts = [{"text": "test", "weight": 0.5}]
        cs = ControlState(prompts=prompts).clamped()
        assert cs.prompts == prompts

    def test_clamped_preserves_mute_bass(self) -> None:
        cs = ControlState(mute_bass=True).clamped()
        assert cs.mute_bass is True

    def test_clamped_preserves_mute_drums(self) -> None:
        cs = ControlState(mute_drums=True).clamped()
        assert cs.mute_drums is True

    def test_extreme_low_all_fields(self, extreme_low_controls: ControlState) -> None:
        c = extreme_low_controls.clamped()
        assert c.bpm == 60
        assert c.density == 0.0
        assert c.brightness == 0.0
        assert c.guidance == 0.0
        assert c.temperature == 0.0

    def test_extreme_high_all_fields(self, extreme_high_controls: ControlState) -> None:
        c = extreme_high_controls.clamped()
        assert c.bpm == 200
        assert c.density == 1.0
        assert c.brightness == 1.0
        assert c.guidance == 6.0
        assert c.temperature == 3.0

    def test_clamped_returns_new_instance(self) -> None:
        original = ControlState(bpm=0)
        clamped = original.clamped()
        assert original is not clamped
        assert original.bpm == 0  # original unchanged
        assert clamped.bpm == 60


# ── diff() dead-zone and field detection ────────────────────────────────


class TestControlStateDiff:
    """Verify diff() uses correct dead-zones and detects real changes."""

    def test_identical_states_empty_diff(self) -> None:
        a = ControlState()
        b = ControlState()
        assert a.diff(b) == {}

    def test_bpm_change_detected(self) -> None:
        a = ControlState(bpm=120)
        b = ControlState(bpm=121)
        diff = a.diff(b)
        assert "bpm" in diff
        assert diff["bpm"] == 120

    def test_bpm_no_change_exact(self) -> None:
        a = ControlState(bpm=120)
        b = ControlState(bpm=120)
        assert "bpm" not in a.diff(b)

    def test_density_within_dead_zone(self) -> None:
        a = ControlState(density=0.5)
        b = ControlState(density=0.505)
        assert "density" not in a.diff(b)

    def test_density_outside_dead_zone(self) -> None:
        a = ControlState(density=0.5)
        b = ControlState(density=0.52)
        diff = a.diff(b)
        assert "density" in diff

    def test_density_at_dead_zone_boundary(self) -> None:
        a = ControlState(density=0.5)
        b = ControlState(density=0.51)
        # Due to floating-point, abs(0.5 - 0.51) = 0.010000000000000009 > 0.01
        # so this does trigger the diff
        assert "density" in a.diff(b)

    def test_density_just_inside_dead_zone(self) -> None:
        a = ControlState(density=0.5)
        b = ControlState(density=0.509)
        # abs(0.5 - 0.509) = 0.009 < 0.01
        assert "density" not in a.diff(b)

    def test_brightness_within_dead_zone(self) -> None:
        a = ControlState(brightness=0.5)
        b = ControlState(brightness=0.505)
        assert "brightness" not in a.diff(b)

    def test_brightness_outside_dead_zone(self) -> None:
        a = ControlState(brightness=0.5)
        b = ControlState(brightness=0.52)
        assert "brightness" in a.diff(b)

    def test_guidance_within_dead_zone(self) -> None:
        a = ControlState(guidance=3.0)
        b = ControlState(guidance=3.005)
        assert "guidance" not in a.diff(b)

    def test_guidance_outside_dead_zone(self) -> None:
        a = ControlState(guidance=3.0)
        b = ControlState(guidance=3.02)
        assert "guidance" in a.diff(b)

    def test_temperature_within_dead_zone(self) -> None:
        a = ControlState(temperature=1.0)
        b = ControlState(temperature=1.005)
        assert "temperature" not in a.diff(b)

    def test_temperature_outside_dead_zone(self) -> None:
        a = ControlState(temperature=1.0)
        b = ControlState(temperature=1.02)
        assert "temperature" in a.diff(b)

    def test_scale_change_detected(self) -> None:
        a = ControlState(scale="C_MAJOR_A_MINOR")
        b = ControlState(scale="D_MAJOR_B_MINOR")
        assert "scale" in a.diff(b)

    def test_scale_same_not_detected(self) -> None:
        a = ControlState(scale="C_MAJOR_A_MINOR")
        b = ControlState(scale="C_MAJOR_A_MINOR")
        assert "scale" not in a.diff(b)

    def test_prompts_change_detected(self) -> None:
        a = ControlState(prompts=[{"text": "a", "weight": 1.0}])
        b = ControlState(prompts=[{"text": "b", "weight": 1.0}])
        assert "prompts" in a.diff(b)

    def test_prompts_same_not_detected(self) -> None:
        a = ControlState(prompts=[{"text": "a", "weight": 1.0}])
        b = ControlState(prompts=[{"text": "a", "weight": 1.0}])
        assert "prompts" not in a.diff(b)

    def test_mute_bass_change_detected(self) -> None:
        a = ControlState(mute_bass=False)
        b = ControlState(mute_bass=True)
        assert "mute_bass" in a.diff(b)

    def test_mute_bass_same_not_detected(self) -> None:
        a = ControlState(mute_bass=False)
        b = ControlState(mute_bass=False)
        assert "mute_bass" not in a.diff(b)

    def test_mute_drums_change_detected(self) -> None:
        a = ControlState(mute_drums=False)
        b = ControlState(mute_drums=True)
        assert "mute_drums" in a.diff(b)

    def test_mute_drums_same_not_detected(self) -> None:
        a = ControlState(mute_drums=False)
        b = ControlState(mute_drums=False)
        assert "mute_drums" not in a.diff(b)

    def test_multiple_changes_all_detected(self) -> None:
        a = ControlState(bpm=100, density=0.3, scale="C_MAJOR_A_MINOR")
        b = ControlState(bpm=120, density=0.8, scale="D_MAJOR_B_MINOR")
        diff = a.diff(b)
        assert "bpm" in diff
        assert "density" in diff
        assert "scale" in diff

    def test_diff_returns_self_values(self) -> None:
        """diff() should return values from `self`, not from `other`."""
        a = ControlState(bpm=100)
        b = ControlState(bpm=120)
        diff = a.diff(b)
        assert diff["bpm"] == 100  # a.bpm, not b.bpm
