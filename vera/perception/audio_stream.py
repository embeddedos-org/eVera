"""Audio stream — async microphone capture using sounddevice."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import numpy as np

from config import settings

logger = logging.getLogger(__name__)


class AudioStream:
    """Async wrapper around sounddevice for microphone capture."""

    def __init__(
        self,
        sample_rate: int | None = None,
        chunk_duration_ms: int | None = None,
        channels: int = 1,
    ) -> None:
        self._sample_rate = sample_rate or settings.voice.sample_rate
        self._chunk_duration_ms = chunk_duration_ms or settings.voice.chunk_duration_ms
        self._channels = channels
        self._chunk_size = int(self._sample_rate * self._chunk_duration_ms / 1000)
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._stream = None
        self._running = False

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: dict, status: int) -> None:
        """Callback from sounddevice — runs in a separate thread."""
        if status:
            logger.warning("Audio stream status: %s", status)
        # Convert float32 to int16 PCM bytes
        pcm = (indata[:, 0] * 32767).astype(np.int16).tobytes()
        try:
            self._queue.put_nowait(pcm)
        except asyncio.QueueFull:
            pass  # Drop frame if queue is full

    async def start(self) -> None:
        """Start capturing audio from the microphone."""
        try:
            import sounddevice as sd

            self._running = True
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                blocksize=self._chunk_size,
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.info(
                "AudioStream started: %dHz, %dms chunks",
                self._sample_rate,
                self._chunk_duration_ms,
            )
        except (ImportError, Exception) as e:
            logger.error("Failed to start audio stream: %s", e)
            self._running = False
            raise

    async def stop(self) -> None:
        """Stop the audio stream."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("AudioStream stopped")

    async def get_chunks(self) -> AsyncIterator[bytes]:
        """Yield audio chunks as they become available."""
        while self._running:
            try:
                chunk = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                yield chunk
            except TimeoutError:
                continue

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def is_running(self) -> bool:
        return self._running
