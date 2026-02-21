"""ElevenLabs Music API bridge — text-prompt-based music generation."""

from __future__ import annotations

import asyncio
import os
import struct
import time
from functools import partial

from lenses.base import ControlState
from lyria_bridge import MockAudioGenerator


class ElevenLabsBridge:
    """Generates music via ElevenLabs Music API, same interface as LyriaBridge.

    Converts ControlState fields into a text prompt, generates 30-second
    segments, and queues raw PCM chunks for streaming.  Falls back to
    MockAudioGenerator when no API key is set or on connection failure.

    Key design choices for gapless playback:
    - Prompt changes are debounced (2s) so slider drags don't spam the API.
    - Current segment always finishes queuing; new audio is prepared in the
      background and swapped in seamlessly.
    - A generation counter lets us discard stale API responses.
    """

    # Chunk geometry — matches mock: 2400 stereo frames @ 48 kHz = 50 ms
    _FRAMES_PER_CHUNK = 2400
    _CHANNELS = 2
    _BYTES_PER_SAMPLE = 2  # 16-bit
    _CHUNK_BYTES = _FRAMES_PER_CHUNK * _CHANNELS * _BYTES_PER_SAMPLE  # 9600

    _DEBOUNCE_SECONDS = 2.0  # Wait for sliders to settle before regenerating

    def __init__(self) -> None:
        self._api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        self._use_mock = not self._api_key
        self._mock = MockAudioGenerator() if self._use_mock else None
        self._client = None
        self._connected = False

        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._current_prompt: str = ""
        self._committed_prompt: str = ""  # The prompt currently generating/playing
        self._last_prompt_change: float = 0.0
        self._pending_prompt: str = ""  # Waiting for debounce to commit
        self._stop_event = asyncio.Event()
        self._generation_task: asyncio.Task | None = None
        self._segment_length_ms = 30_000
        self._gen_id: int = 0  # Monotonic counter to discard stale results

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
            self._pending_prompt = new_prompt
            self._last_prompt_change = time.monotonic()

    async def get_audio_chunk(self) -> bytes | None:
        if self._use_mock:
            return self._mock.generate_chunk(num_samples=self._FRAMES_PER_CHUNK)

        try:
            return await asyncio.wait_for(self._audio_queue.get(), timeout=0.1)
        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            return None

    async def reset(self) -> None:
        self._current_prompt = ""
        self._committed_prompt = ""
        self._pending_prompt = ""
        self._gen_id += 1  # Invalidate any in-flight generation
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

        # BPM -> tempo descriptor
        bpm = controls.bpm
        if bpm < 80:
            parts.append("slow tempo")
        elif bpm < 110:
            parts.append("moderate tempo")
        elif bpm < 140:
            parts.append("upbeat tempo")
        else:
            parts.append("fast energetic tempo")

        # Density -> arrangement
        if controls.density < 0.3:
            parts.append("sparse minimal arrangement")
        elif controls.density > 0.7:
            parts.append("dense layered arrangement")

        # Brightness -> tone
        if controls.brightness < 0.3:
            parts.append("dark muted tones")
        elif controls.brightness > 0.7:
            parts.append("bright shimmering tones")

        # Scale -> key / mood
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

        # Temperature -> experimental vs structured
        if controls.temperature > 2.0:
            parts.append("experimental, unconventional")
        elif controls.temperature < 0.5:
            parts.append("structured, predictable")

        parts.append("instrumental")

        return ", ".join(p for p in parts if p)

    # ── generation loop ─────────────────────────────────────────────────

    def _should_regenerate(self) -> bool:
        """Check if a debounced prompt change is ready to commit."""
        if not self._pending_prompt:
            return False
        if self._pending_prompt == self._committed_prompt:
            self._pending_prompt = ""
            return False
        elapsed = time.monotonic() - self._last_prompt_change
        return elapsed >= self._DEBOUNCE_SECONDS

    async def _generation_loop(self) -> None:
        """Continuously generate audio segments.

        - On first prompt: generate immediately (no debounce).
        - On subsequent changes: wait for debounce, then generate.
        - Always finishes queuing the current segment before starting a new one.
        - Loops to generate continuous 30s segments with the same prompt.
        """
        try:
            while not self._stop_event.is_set():
                # Phase 1: wait for *any* prompt to exist
                if not self._committed_prompt and not self._pending_prompt:
                    await asyncio.sleep(0.2)
                    continue

                # First prompt — commit immediately (no debounce)
                if not self._committed_prompt and self._pending_prompt:
                    self._committed_prompt = self._pending_prompt
                    self._pending_prompt = ""
                    print(f"[ElevenLabsBridge] Initial prompt: {self._committed_prompt[:80]}...")

                # Phase 2: generate a segment with the committed prompt
                gen_id = self._gen_id
                await self._generate_segment(self._committed_prompt, gen_id)

                # Phase 3: check if a new prompt is ready (debounced)
                if self._should_regenerate():
                    self._committed_prompt = self._pending_prompt
                    self._pending_prompt = ""
                    print(f"[ElevenLabsBridge] Prompt updated: {self._committed_prompt[:80]}...")
                    continue  # Generate immediately with new prompt

                # Phase 4: no change — wait a bit, then loop for continuous playback
                # During this wait, check periodically for debounced prompt changes
                waited = 0.0
                while waited < 1.0 and not self._stop_event.is_set():
                    await asyncio.sleep(0.2)
                    waited += 0.2
                    if self._should_regenerate():
                        self._committed_prompt = self._pending_prompt
                        self._pending_prompt = ""
                        print(f"[ElevenLabsBridge] Prompt updated: {self._committed_prompt[:80]}...")
                        break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[ElevenLabsBridge] Generation loop error: {e}")

    async def _generate_segment(self, prompt: str, gen_id: int) -> None:
        """Call ElevenLabs Music API and queue ALL PCM chunks (never abort mid-segment)."""
        try:
            loop = asyncio.get_running_loop()

            # Run the synchronous streaming API in a thread
            raw_pcm = await loop.run_in_executor(
                None,
                partial(self._call_api_sync, prompt),
            )

            if raw_pcm is None:
                return

            # Stale generation — a reset() happened while we were in the API call
            if gen_id != self._gen_id:
                return

            # Reset backoff on success
            self._backoff = 2.0

            # Detect mono vs stereo
            total_samples = len(raw_pcm) // self._BYTES_PER_SAMPLE
            is_mono = (total_samples % 2 != 0) or (
                len(raw_pcm) % (self._FRAMES_PER_CHUNK * self._BYTES_PER_SAMPLE) == 0
                and len(raw_pcm) % self._CHUNK_BYTES != 0
            )

            if is_mono:
                raw_pcm = self._mono_to_stereo(raw_pcm)

            # Queue ALL chunks — never abort mid-segment.
            # This ensures gapless playback while next segment generates.
            offset = 0
            while offset + self._CHUNK_BYTES <= len(raw_pcm):
                if self._stop_event.is_set() or gen_id != self._gen_id:
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
