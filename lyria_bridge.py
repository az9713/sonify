"""Lyria RealTime session wrapper with control diffing and mock fallback."""

from __future__ import annotations

import asyncio
import math
import os
import random
import struct
import time
from dataclasses import dataclass, field

from lenses.base import ControlState


class MockAudioGenerator:
    """Additive synthesizer driven by ControlState. No Lyria dependency.

    Applied ControlState fields:
        bpm        -> LFO rate (rhythmic pulse at the beat rate)
        brightness -> base pitch (110-440 Hz, then quantized to scale)
        density    -> harmonic count (1-6 overtones)
        scale      -> pitch quantization (snaps frequency to nearest scale tone)
        guidance   -> LFO depth and regularity (high = steady pulse, low = erratic)
        temperature-> noise floor (0 = pure tone, 3 = noisy)
        mute_bass  -> removes fundamental + 2nd harmonic
        mute_drums -> suppresses LFO rhythmic pulsing

    NOT applied (impossible without generative model):
        prompts    -> natural-language text; requires AI to interpret
    """

    # Pitch classes (semitones from C) for each Lyria scale
    SCALE_NOTES: dict[str, set[int]] = {
        "C_MAJOR_A_MINOR": {0, 2, 4, 5, 7, 9, 11},
        "D_MAJOR_B_MINOR": {1, 2, 4, 6, 7, 9, 11},
        "A_FLAT_MAJOR_F_MINOR": {0, 1, 3, 5, 7, 8, 10},
        "G_FLAT_MAJOR_E_FLAT_MINOR": {1, 3, 5, 6, 8, 10, 11},
    }

    def __init__(self, sample_rate: int = 48000, channels: int = 2) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._phase = 0.0
        self._freq = 220.0
        self._target_freq = 220.0
        self._volume = 0.3
        self._harmonics: list[tuple[float, float]] = [(1.0, 0.3)]
        self._lfo_phase = 0.0
        self._lfo_rate = 2.0
        self._lfo_depth = 0.5
        self._noise_level = 0.0
        self._mute_drums = False
        self._rng = random.Random(42)

    def _quantize_to_scale(self, freq: float, scale_notes: set[int] | None) -> float:
        """Snap a frequency to the nearest pitch in the given scale.

        Uses equal temperament: f(n) = 440 * 2^((n - 69) / 12).
        """
        if scale_notes is None or freq <= 0:
            return freq
        midi = 69.0 + 12.0 * math.log2(freq / 440.0)
        midi_rounded = round(midi)
        pitch_class = midi_rounded % 12

        # Find the nearest pitch class in the scale (wrapping around octave)
        best_dist = 12
        best_pc = pitch_class
        for pc in scale_notes:
            dist = min(abs(pc - pitch_class), 12 - abs(pc - pitch_class))
            if dist < best_dist:
                best_dist = dist
                best_pc = pc

        # Compute signed offset to snap to the chosen pitch class
        diff = best_pc - pitch_class
        if diff > 6:
            diff -= 12
        elif diff < -6:
            diff += 12
        quantized_midi = midi_rounded + diff

        return 440.0 * (2.0 ** ((quantized_midi - 69) / 12.0))

    def update_from_controls(self, controls: ControlState) -> None:
        """Update synth parameters from ControlState.

        Maps 8 of 9 ControlState fields. Only `prompts` is ignored.
        """
        # brightness -> base frequency (A2 to A4)
        raw_freq = 110 + controls.brightness * 330

        # scale -> quantize frequency to nearest note in the active scale
        scale_notes = self.SCALE_NOTES.get(controls.scale)
        self._target_freq = self._quantize_to_scale(raw_freq, scale_notes)

        # density -> number of harmonics (1 = pure sine, 6 = rich timbre)
        n_harmonics = 1 + int(controls.density * 5)
        self._harmonics = [
            (float(i + 1), 0.3 / (i + 1)) for i in range(n_harmonics)
        ]

        # mute_bass -> remove fundamental and 2nd harmonic
        if controls.mute_bass and len(self._harmonics) > 2:
            self._harmonics = self._harmonics[2:]

        # bpm -> LFO rate (rhythmic amplitude modulation)
        self._lfo_rate = controls.bpm / 60.0

        # guidance -> LFO depth and regularity
        #   High guidance (5-6): deep, metronomic pulse (model follows instructions tightly)
        #   Low guidance (0-2): shallow, irregular pulse (model wanders freely)
        self._lfo_depth = min(1.0, controls.guidance / 6.0)

        # temperature -> noise injection
        #   0.0: pure tonal output
        #   3.0: 15% noise floor (stochastic, unpredictable character)
        self._noise_level = controls.temperature / 3.0 * 0.15

        # mute_drums -> suppress the LFO (the rhythmic element of the synth)
        self._mute_drums = controls.mute_drums

    def generate_chunk(self, num_samples: int = 2400) -> bytes:
        """Generate a chunk of 16-bit PCM audio."""
        freq_step = (self._target_freq - self._freq) * 0.01
        samples = []

        for _ in range(num_samples):
            self._freq += freq_step * 0.001
            self._lfo_phase += self._lfo_rate / self.sample_rate

            # LFO: rhythmic amplitude modulation
            if self._mute_drums:
                lfo = 1.0  # flat envelope, no rhythmic pulsing
            else:
                lfo_raw = math.sin(self._lfo_phase * math.tau)
                # Guidance controls depth: high guidance = deep regular pulse
                # Low guidance adds jitter (irregularity)
                jitter = (1.0 - self._lfo_depth) * self._rng.gauss(0, 0.3)
                lfo = 0.5 + self._lfo_depth * 0.5 * lfo_raw + jitter
                lfo = max(0.1, min(1.0, lfo))

            # Additive synthesis
            value = 0.0
            for harmonic_mult, harmonic_amp in self._harmonics:
                value += harmonic_amp * math.sin(self._phase * harmonic_mult)

            # Temperature-controlled noise floor
            if self._noise_level > 0:
                value += self._rng.gauss(0, self._noise_level)

            value *= self._volume * lfo
            self._phase += math.tau * self._freq / self.sample_rate

            if self._phase > math.tau * 1000:
                self._phase -= math.tau * 1000

            sample_int = max(-32767, min(32767, int(value * 32767)))
            for _ in range(self.channels):
                samples.append(sample_int)

        return struct.pack(f"<{len(samples)}h", *samples)


class LyriaBridge:
    """Manages the Lyria RealTime session or mock fallback.

    Diffs ControlState and only sends changes to minimize API calls.
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("GOOGLE_API_KEY", "")
        self._use_mock = not self._api_key
        self._session = None
        self._client = None
        self._prev_controls: ControlState | None = None
        self._mock = MockAudioGenerator() if self._use_mock else None
        self._connected = False
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
        self._receive_task: asyncio.Task | None = None

    @property
    def is_mock(self) -> bool:
        return self._use_mock

    async def connect(self) -> None:
        """Establish connection to Lyria or start mock generator."""
        if self._use_mock:
            print("[LyriaBridge] No GOOGLE_API_KEY found. Using mock audio generator.")
            self._connected = True
            return

        try:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self._api_key,
                http_options={"api_version": "v1alpha"},
            )
            self._session = await self._client.aio.live.music.connect(
                model="models/lyria-realtime-exp"
            )
            self._connected = True
            print("[LyriaBridge] Connected to Lyria RealTime.")
            self._receive_task = asyncio.create_task(self._receive_audio())

        except Exception as e:
            print(f"[LyriaBridge] Failed to connect to Lyria: {e}")
            print("[LyriaBridge] Falling back to mock audio generator.")
            self._use_mock = True
            self._mock = MockAudioGenerator()
            self._connected = True

    async def _receive_audio(self) -> None:
        """Background task to receive audio chunks from Lyria."""
        try:
            while self._session:
                async for message in self._session.receive():
                    if hasattr(message, "server_content") and message.server_content:
                        chunks = getattr(message.server_content, "audio_chunks", None)
                        if chunks:
                            for chunk in chunks:
                                data = chunk.data
                                if isinstance(data, str):
                                    import base64
                                    data = base64.b64decode(data)
                                try:
                                    self._audio_queue.put_nowait(data)
                                except asyncio.QueueFull:
                                    try:
                                        self._audio_queue.get_nowait()
                                    except asyncio.QueueEmpty:
                                        pass
                                    self._audio_queue.put_nowait(data)
                    await asyncio.sleep(1e-6)
        except Exception as e:
            print(f"[LyriaBridge] Audio receive error: {e}")

    async def update(self, controls: ControlState) -> None:
        """Send control changes to Lyria (only diffs)."""
        if not self._connected:
            return

        if self._use_mock:
            self._mock.update_from_controls(controls)
            return

        if self._prev_controls is None:
            await self._send_full_state(controls)
        else:
            changes = controls.diff(self._prev_controls)
            if changes:
                await self._send_changes(controls, changes)

        self._prev_controls = controls

    async def _send_full_state(self, controls: ControlState) -> None:
        """Send complete state to Lyria."""
        try:
            from google.genai import types

            prompts = [
                types.WeightedPrompt(text=p["text"], weight=p["weight"])
                for p in controls.prompts
            ]
            await self._session.set_weighted_prompts(prompts=prompts)

            scale_enum = getattr(types.Scale, controls.scale, None)
            config_kwargs = {
                "bpm": controls.bpm,
                "density": controls.density,
                "brightness": controls.brightness,
                "guidance": controls.guidance,
                "temperature": controls.temperature,
                "mute_bass": controls.mute_bass,
                "mute_drums": controls.mute_drums,
            }
            if scale_enum is not None:
                config_kwargs["scale"] = scale_enum

            await self._session.set_music_generation_config(
                config=types.LiveMusicGenerationConfig(**config_kwargs)
            )
            await self._session.play()

        except Exception as e:
            print(f"[LyriaBridge] Error sending full state: {e}")

    async def _send_changes(self, controls: ControlState, changes: dict) -> None:
        """Send only changed parameters to Lyria."""
        try:
            from google.genai import types

            needs_context_reset = False

            if "prompts" in changes:
                prompts = [
                    types.WeightedPrompt(text=p["text"], weight=p["weight"])
                    for p in controls.prompts
                ]
                await self._session.set_weighted_prompts(prompts=prompts)

            config_keys = {"bpm", "density", "brightness", "guidance",
                           "temperature", "mute_bass", "mute_drums", "scale"}
            if changes.keys() & config_keys:
                scale_enum = getattr(types.Scale, controls.scale, None)
                config_kwargs = {
                    "bpm": controls.bpm,
                    "density": controls.density,
                    "brightness": controls.brightness,
                    "guidance": controls.guidance,
                    "temperature": controls.temperature,
                    "mute_bass": controls.mute_bass,
                    "mute_drums": controls.mute_drums,
                }
                if scale_enum is not None:
                    config_kwargs["scale"] = scale_enum

                await self._session.set_music_generation_config(
                    config=types.LiveMusicGenerationConfig(**config_kwargs)
                )

                if "bpm" in changes or "scale" in changes:
                    needs_context_reset = True

            if needs_context_reset:
                await self._session.reset_context()

        except Exception as e:
            print(f"[LyriaBridge] Error sending changes: {e}")

    async def get_audio_chunk(self) -> bytes | None:
        """Get next audio chunk. Returns mock audio or real Lyria audio."""
        if self._use_mock:
            return self._mock.generate_chunk(num_samples=2400)

        try:
            return await asyncio.wait_for(self._audio_queue.get(), timeout=0.1)
        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            return None

    async def reset(self) -> None:
        """Reset the Lyria session context (for lens switching)."""
        self._prev_controls = None
        if not self._use_mock and self._session:
            try:
                await self._session.reset_context()
            except Exception as e:
                print(f"[LyriaBridge] Error resetting context: {e}")

    async def disconnect(self) -> None:
        """Clean shutdown."""
        self._connected = False
        if self._receive_task:
            self._receive_task.cancel()
        if self._session:
            try:
                await self._session.stop()
            except Exception:
                pass
        self._session = None
