"""Speech-to-Text using faster-whisper."""

from __future__ import annotations

import logging

import numpy as np

from config import settings

logger = logging.getLogger(__name__)


class SpeechToText:
    """Local STT using faster-whisper (CTranslate2 backend)."""

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ) -> None:
        self._model_size = model_size or settings.voice.stt_model
        self._device = device or settings.voice.stt_device
        self._compute_type = compute_type or settings.voice.stt_compute_type
        self._model = None

    def _ensure_loaded(self) -> None:
        """Lazy-load the whisper model."""
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel

            logger.info(
                "Loading STT model: %s on %s (%s)",
                self._model_size,
                self._device,
                self._compute_type,
            )
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            logger.info("STT model loaded successfully")
        except ImportError:
            logger.error("faster-whisper not installed; STT unavailable")
            raise

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcribe PCM int16 audio bytes to text."""
        self._ensure_loaded()
        if self._model is None:
            return ""

        # Convert int16 PCM bytes → float32 numpy array
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0

        # Run transcription
        segments, info = self._model.transcribe(
            audio_float32,
            beam_size=5,
            language="en",
            vad_filter=True,
        )

        # Collect all segment texts
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        transcript = " ".join(text_parts).strip()
        logger.info("Transcribed: '%s' (%.1fs audio, lang=%s)", transcript[:80], info.duration, info.language)
        return transcript

    def transcribe_stream(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """Alias for transcribe — for future streaming support."""
        return self.transcribe(audio_bytes, sample_rate)
