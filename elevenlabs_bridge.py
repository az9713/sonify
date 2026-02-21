"""ElevenLabs Music API bridge — text-prompt-based music generation."""

from __future__ import annotations

import asyncio
import os
import struct
from functools import partial

from lenses.base import ControlState
from lyria_bridge import MockAudioGenerator


class ElevenLabsBridge:
    """Generates music via ElevenLabs Music API, same interface as LyriaBridge.

    Converts ControlState fields into a text prompt, generates 30-second
    segments, and queues raw PCM chunks for streaming.  Falls back to
    MockAudioGenerator when no API key is set or on connection failure.
    """

    # Chunk geometry — matches mock: 2400 stereo frames @ 48 kHz = 50 ms
    _FRAMES_PER_CHUNK = 2400
    _CHANNELS = 2
    _BYTES_PER_SAMPLE = 2  # 16-bit
    _CHUNK_BYTES = _FRAMES_PER_CHUNK * _CHANNELS * _BYTES_PER_SAMPLE  # 9600

    def __init__(self) -> None:
        self._api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        self._use_mock = not self._api_key
        self._mock = MockAudioGenerator() if self._use_mock else None
        self._client = None
        self._connected = False

        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._current_prompt: str = ""
        self._prompt_changed = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._generation_task: asyncio.Task | None = None
        self._segment_length_ms = 30_000

        # Exponential backoff state
        self._backoff = 2.0
        self._max_backoff = 60.0

    # ── public interface ────────────────────────────────────────────────

    @property
    def is_mock(self) -> bool:
        return self._use_mock

    async def connect(self) -> None:
        if self._use_mock:
            print("[ElevenLabsBridge] No ELEVENLABS_API_KEY found. Using mock audio generator.")
            self._connected = True
            return

        try:
            from elevenlabs import ElevenLabs
            self._client = ElevenLabs(api_key=self._api_key)
            self._connected = True
            self._generation_task = asyncio.create_task(self._generation_loop())
            print("[ElevenLabsBridge] Connected to ElevenLabs Music API.")
        except Exception as e:
            print(f"[ElevenLabsBridge] Failed to initialise client: {e}")
            print("[ElevenLabsBridge] Falling back to mock audio generator.")
            self._use_mock = True
            self._mock = MockAudioGenerator()
            self._connected = True

    async def update(self, controls: ControlState) -> None:
        if not self._connected:
            return

        if self._use_mock:
            self._mock.update_from_controls(controls)
            return

        new_prompt = self._build_prompt(controls)
        if new_prompt != self._current_prompt:
            self._current_prompt = new_prompt
            self._prompt_changed.set()

    async def get_audio_chunk(self) -> bytes | None:
        if self._use_mock:
            return self._mock.generate_chunk(num_samples=self._FRAMES_PER_CHUNK)

        try:
            return await asyncio.wait_for(self._audio_queue.get(), timeout=0.1)
        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            return None

    async def reset(self) -> None:
        self._current_prompt = ""
        # Drain the queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def disconnect(self) -> None:
        self._connected = False
        self._stop_event.set()
        if self._generation_task:
            self._generation_task.cancel()
            try:
                await self._generation_task
            except (asyncio.CancelledError, Exception):
                pass
        self._generation_task = None

    # ── prompt builder ──────────────────────────────────────────────────

    @staticmethod
    def _build_prompt(controls: ControlState) -> str:
        parts: list[str] = []

        # Text prompts from the lens (sorted by weight descending)
        if controls.prompts:
            sorted_prompts = sorted(controls.prompts, key=lambda p: p.get("weight", 0), reverse=True)
            for p in sorted_prompts:
                parts.append(p.get("text", ""))

        # BPM → tempo descriptor
        bpm = controls.bpm
        if bpm < 80:
            parts.append("slow tempo")
        elif bpm < 110:
            parts.append("moderate tempo")
        elif bpm < 140:
            parts.append("upbeat tempo")
        else:
            parts.append("fast energetic tempo")

        # Density → arrangement
        if controls.density < 0.3:
            parts.append("sparse minimal arrangement")
        elif controls.density > 0.7:
            parts.append("dense layered arrangement")

        # Brightness → tone
        if controls.brightness < 0.3:
            parts.append("dark muted tones")
        elif controls.brightness > 0.7:
            parts.append("bright shimmering tones")

        # Scale → key / mood
        scale_map = {
            "C_MAJOR_A_MINOR": "C major, uplifting mood",
            "D_MAJOR_B_MINOR": "D major, bright joyful mood",
            "A_FLAT_MAJOR_F_MINOR": "F minor, melancholic mood",
            "G_FLAT_MAJOR_E_FLAT_MINOR": "E-flat minor, dark brooding mood",
        }
        if controls.scale in scale_map:
            parts.append(scale_map[controls.scale])

        # Mute flags
        if controls.mute_bass:
            parts.append("no bass")
        if controls.mute_drums:
            parts.append("no drums")

        # Temperature → experimental vs structured
        if controls.temperature > 2.0:
            parts.append("experimental, unconventional")
        elif controls.temperature < 0.5:
            parts.append("structured, predictable")

        parts.append("instrumental")

        return ", ".join(p for p in parts if p)

    # ── generation loop ─────────────────────────────────────────────────

    async def _generation_loop(self) -> None:
        """Continuously generate audio segments while a prompt exists."""
        try:
            while not self._stop_event.is_set():
                # Wait until we have a prompt
                if not self._current_prompt:
                    try:
                        await asyncio.wait_for(self._prompt_changed.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    self._prompt_changed.clear()
                    continue

                self._prompt_changed.clear()
                prompt = self._current_prompt

                await self._generate_segment(prompt)

                # If prompt didn't change during generation, wait briefly
                # then loop for continuous playback
                if not self._prompt_changed.is_set():
                    try:
                        await asyncio.wait_for(self._prompt_changed.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        pass  # Generate another segment with same prompt
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[ElevenLabsBridge] Generation loop error: {e}")

    async def _generate_segment(self, prompt: str) -> None:
        """Call ElevenLabs Music API and queue PCM chunks."""
        try:
            loop = asyncio.get_running_loop()

            # Run the synchronous streaming API in a thread
            raw_pcm = await loop.run_in_executor(
                None,
                partial(self._call_api_sync, prompt),
            )

            if raw_pcm is None:
                return

            # Reset backoff on success
            self._backoff = 2.0

            # Detect mono vs stereo.  The API returns pcm_48000 which is
            # 16-bit signed LE.  If total samples is odd relative to
            # stereo frame expectation, treat as mono and duplicate.
            total_samples = len(raw_pcm) // self._BYTES_PER_SAMPLE
            is_mono = (total_samples % 2 != 0) or (
                # Heuristic: if byte count matches exactly N mono frames
                # rather than N stereo frames, duplicate channels
                len(raw_pcm) % (self._FRAMES_PER_CHUNK * self._BYTES_PER_SAMPLE) == 0
                and len(raw_pcm) % self._CHUNK_BYTES != 0
            )

            if is_mono:
                raw_pcm = self._mono_to_stereo(raw_pcm)

            # Split into chunks and queue with pacing
            offset = 0
            while offset + self._CHUNK_BYTES <= len(raw_pcm):
                if self._prompt_changed.is_set() or self._stop_event.is_set():
                    break

                chunk = raw_pcm[offset : offset + self._CHUNK_BYTES]
                offset += self._CHUNK_BYTES

                # Queue chunk, dropping oldest on overflow
                try:
                    self._audio_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    try:
                        self._audio_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    self._audio_queue.put_nowait(chunk)

                await asyncio.sleep(0.02)

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate" in error_str.lower():
                print(f"[ElevenLabsBridge] Rate limited. Backing off {self._backoff:.0f}s")
            else:
                print(f"[ElevenLabsBridge] Generation error: {e}")

            await asyncio.sleep(self._backoff)
            self._backoff = min(self._backoff * 2, self._max_backoff)

    def _call_api_sync(self, prompt: str) -> bytes | None:
        """Synchronous helper — runs in thread executor."""
        try:
            audio_iter = self._client.music.stream(
                prompt=prompt,
                music_length_ms=self._segment_length_ms,
                output_format="pcm_48000",
                force_instrumental=True,
            )
            # Collect all chunks from the iterator
            chunks: list[bytes] = []
            for chunk in audio_iter:
                chunks.append(chunk)
            return b"".join(chunks)
        except Exception as e:
            print(f"[ElevenLabsBridge] API call error: {e}")
            return None

    @staticmethod
    def _mono_to_stereo(pcm: bytes) -> bytes:
        """Duplicate mono 16-bit PCM to stereo."""
        samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        stereo = []
        for s in samples:
            stereo.append(s)
            stereo.append(s)
        return struct.pack(f"<{len(stereo)}h", *stereo)
