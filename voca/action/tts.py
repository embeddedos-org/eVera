"""Text-to-Speech using pyttsx3 (local, offline)."""

from __future__ import annotations

import asyncio
import logging
import threading

from config import settings
from voca.events.bus import EventBus, EventType

logger = logging.getLogger(__name__)


class TextToSpeech:
    """Local TTS engine with interruption support."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._engine = None
        self._event_bus = event_bus
        self._interrupted = False
        self._speaking = False
        self._rate = settings.voice.tts_rate
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._rate)
            # Try to set a natural-sounding voice
            voices = self._engine.getProperty("voices")
            if voices and len(voices) > 1:
                self._engine.setProperty("voice", voices[1].id)  # Usually female voice
            logger.info("TTS engine initialized: rate=%d", self._rate)
        except Exception as e:
            logger.warning("TTS init failed: %s — speech output disabled", e)

    async def speak(self, text: str) -> None:
        """Speak text with sentence-level interruption checking."""
        if not self._engine:
            logger.warning("TTS engine not available — printing instead")
            print(f"🔊 {text}")
            return

        self._interrupted = False
        self._speaking = True

        if self._event_bus:
            await self._event_bus.publish(EventType.TTS_START, {"text": text})

        # Split into sentences for interruptibility
        sentences = self._split_sentences(text)

        for sentence in sentences:
            if self._interrupted:
                logger.info("TTS interrupted mid-speech")
                break
            await self._speak_sentence(sentence)

        self._speaking = False
        if self._event_bus:
            await self._event_bus.publish(EventType.TTS_DONE, {"text": text})

    async def _speak_sentence(self, sentence: str) -> None:
        """Speak a single sentence in a thread to avoid blocking."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._speak_sync, sentence)

    def _speak_sync(self, text: str) -> None:
        """Synchronous speech — runs in executor thread."""
        if self._engine and not self._interrupted:
            self._engine.say(text)
            self._engine.runAndWait()

    def interrupt(self) -> None:
        """Interrupt current speech."""
        self._interrupted = True
        if self._engine:
            self._engine.stop()

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences for granular interruption."""
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def set_rate(self, rate: int) -> None:
        self._rate = rate
        if self._engine:
            self._engine.setProperty("rate", rate)
