"""Voice Activity Detection using webrtcvad."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto

from config import settings

logger = logging.getLogger(__name__)


class VADState(Enum):
    SILENCE = auto()
    SPEECH = auto()
    TRAILING_SILENCE = auto()


@dataclass
class VADResult:
    """Result from VAD processing."""

    is_speech_end: bool
    audio_buffer: bytes
    state: VADState


class VoiceActivityDetector:
    """Detects speech boundaries using webrtcvad with a ring buffer."""

    def __init__(
        self,
        sample_rate: int | None = None,
        aggressiveness: int | None = None,
        trailing_silence_ms: int | None = None,
        chunk_duration_ms: int | None = None,
    ) -> None:
        self._sample_rate = sample_rate or settings.voice.sample_rate
        self._aggressiveness = aggressiveness or settings.voice.vad_aggressiveness
        self._trailing_ms = trailing_silence_ms or settings.voice.vad_trailing_silence_ms
        self._chunk_ms = chunk_duration_ms or settings.voice.chunk_duration_ms
        self._vad = None
        self._state = VADState.SILENCE
        self._audio_buffer = bytearray()
        self._silence_chunks = 0
        self._speech_chunks = 0

        # Calculate how many silent chunks = trailing silence
        self._trailing_chunks = self._trailing_ms // self._chunk_ms

        # Ring buffer for pre-speech padding (capture a bit before speech starts)
        self._ring_buffer: deque[bytes] = deque(maxlen=10)

        self._init_vad()

    def _init_vad(self) -> None:
        try:
            import webrtcvad

            self._vad = webrtcvad.Vad(self._aggressiveness)
            logger.info("VAD initialized: aggressiveness=%d", self._aggressiveness)
        except ImportError:
            logger.warning("webrtcvad not installed; VAD disabled (all audio treated as speech)")

    def process_chunk(self, chunk: bytes) -> VADResult:
        """Process a single audio chunk and return VAD result."""
        is_speech = self._detect_speech(chunk)

        if self._state == VADState.SILENCE:
            self._ring_buffer.append(chunk)
            if is_speech:
                self._state = VADState.SPEECH
                self._speech_chunks = 1
                self._silence_chunks = 0
                # Flush ring buffer into audio buffer (pre-speech context)
                self._audio_buffer = bytearray(b"".join(self._ring_buffer))
                self._audio_buffer.extend(chunk)
                logger.debug("Speech started")

        elif self._state == VADState.SPEECH:
            self._audio_buffer.extend(chunk)
            if is_speech:
                self._speech_chunks += 1
                self._silence_chunks = 0
            else:
                self._silence_chunks += 1
                if self._silence_chunks >= self._trailing_chunks:
                    self._state = VADState.TRAILING_SILENCE

        elif self._state == VADState.TRAILING_SILENCE:
            # Speech ended
            audio = bytes(self._audio_buffer)
            self._reset()
            logger.debug(
                "Speech ended: %d chunks, %.1fs of audio",
                self._speech_chunks,
                len(audio) / (self._sample_rate * 2),
            )
            return VADResult(is_speech_end=True, audio_buffer=audio, state=VADState.SILENCE)

        return VADResult(is_speech_end=False, audio_buffer=b"", state=self._state)

    def _detect_speech(self, chunk: bytes) -> bool:
        """Run VAD on a chunk. Returns True if speech detected."""
        if self._vad is None:
            return True  # Fallback: treat all as speech
        try:
            return self._vad.is_speech(chunk, self._sample_rate)
        except Exception:
            return False

    def _reset(self) -> None:
        """Reset to silence state."""
        self._state = VADState.SILENCE
        self._audio_buffer = bytearray()
        self._silence_chunks = 0
        self._speech_chunks = 0
        self._ring_buffer.clear()

    @property
    def state(self) -> VADState:
        return self._state
