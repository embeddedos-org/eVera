"""Wake word detection — reuses SpeechToText for trigger phrase matching.

Transcribes short VAD segments and checks if the transcript contains
the configured wake phrase (with fuzzy matching for common Whisper
misrecognitions).
"""

from __future__ import annotations

import logging
import re

from config import settings
from vera.perception.stt import SpeechToText

logger = logging.getLogger(__name__)

# Common Whisper misrecognitions of "hey vera"
_DEFAULT_FUZZY_VARIANTS = [
    "hey vera",
    "hey siri",
    "hey sree",
    "a vera",
    "hey shri",
    "hey shree",
    "hey verae",
    "hey siry",
    "heyshri",
    "heyvera",
]

# Audio duration bounds (seconds) — wake phrases are 0.5–2s
_MIN_DURATION_S = 0.3
_MAX_DURATION_S = 3.0


class WakeWordDetector:
    """Detect wake word by transcribing short audio and matching the phrase.

    Reuses the existing SpeechToText engine — no new ML models required.
    """

    def __init__(self, stt: SpeechToText | None = None) -> None:
        self._stt = stt or SpeechToText()
        self._phrase = settings.voice.wake_word_phrase.lower().strip()
        self._variants = self._build_variants(self._phrase)

    @staticmethod
    def _build_variants(phrase: str) -> list[re.Pattern[str]]:
        """Build regex patterns for the wake phrase and common misrecognitions."""
        raw = set(_DEFAULT_FUZZY_VARIANTS)
        raw.add(phrase)
        patterns = []
        for v in raw:
            escaped = re.escape(v.strip())
            patterns.append(re.compile(escaped, re.IGNORECASE))
        return patterns

    def check(self, audio_buffer: bytes, sample_rate: int = 16000) -> bool:
        """Transcribe the audio segment and check for the wake phrase.

        Returns True if the wake phrase (or a fuzzy variant) is detected.
        Skips STT for segments outside the expected duration range.
        """
        duration_s = len(audio_buffer) / (2 * sample_rate)  # int16 = 2 bytes/sample

        if duration_s < _MIN_DURATION_S or duration_s > _MAX_DURATION_S:
            logger.debug(
                "Wake word skip: segment %.2fs outside [%.1f, %.1f]",
                duration_s,
                _MIN_DURATION_S,
                _MAX_DURATION_S,
            )
            return False

        transcript = self._stt.transcribe(audio_buffer, sample_rate).lower().strip()
        if not transcript:
            return False

        for pattern in self._variants:
            if pattern.search(transcript):
                logger.info("Wake word detected: '%s'", transcript)
                return True

        return False
