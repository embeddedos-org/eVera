"""Text-to-Speech — local (pyttsx3) and streaming (edge-tts) engines.

Provides a TTSEngine protocol, two concrete implementations, and a
factory function ``get_tts_engine(name)`` for config-driven selection.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from config import settings
from vera.events.bus import EventBus, EventType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TTSEngine protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class TTSEngine(Protocol):
    """Minimal interface every TTS backend must satisfy."""

    async def speak(self, text: str) -> None:
        """Play *text* on local speakers (CLI mode)."""
        ...

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Yield raw audio bytes suitable for streaming over WebSocket."""
        ...  # pragma: no cover
        yield b""  # type: ignore[misc]

    def interrupt(self) -> None: ...


# ---------------------------------------------------------------------------
# LocalTTSEngine — wraps existing pyttsx3 logic
# ---------------------------------------------------------------------------


class LocalTTSEngine:
    """pyttsx3-based TTS — plays audio locally, no streaming support."""

    def __init__(self) -> None:
        self._engine: Any = None
        self._interrupted = False
        self._speaking = False
        self._rate = settings.voice.tts_rate
        self._init()

    def _init(self) -> None:
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._rate)
            voices = self._engine.getProperty("voices")
            if voices and len(voices) > 1:
                self._engine.setProperty("voice", voices[1].id)
            logger.info("LocalTTS initialized: rate=%d", self._rate)
        except Exception as e:
            logger.warning("pyttsx3 init failed: %s", e)

    async def speak(self, text: str) -> None:
        if not self._engine:
            logger.info("🔊 %s", text)
            return
        self._interrupted = False
        self._speaking = True
        for sentence in _split_sentences(text):
            if self._interrupted:
                break
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._say, sentence)
        self._speaking = False

    def _say(self, text: str) -> None:
        if self._engine and not self._interrupted:
            self._engine.say(text)
            self._engine.runAndWait()

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        raise NotImplementedError("LocalTTSEngine does not support streaming synthesis")
        yield b""  # type: ignore[misc]

    def interrupt(self) -> None:
        self._interrupted = True
        if self._engine:
            self._engine.stop()


# ---------------------------------------------------------------------------
# EdgeTTSEngine — uses edge-tts for high-quality streaming synthesis
# ---------------------------------------------------------------------------


class EdgeTTSEngine:
    """Microsoft Edge TTS — free, high-quality, streamable audio."""

    def __init__(self, voice: str = "en-US-AriaNeural") -> None:
        self._voice = voice
        self._interrupted = False

    async def speak(self, text: str) -> None:
        """Synthesise and play locally via a temp file."""
        import tempfile

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            import edge_tts

            comm = edge_tts.Communicate(text, self._voice)
            await comm.save(tmp_path)

            # Play the file
            import platform
            import subprocess

            system = platform.system()
            if system == "Windows":
                subprocess.Popen(
                    ["powershell", "-c", f'(New-Object Media.SoundPlayer "{tmp_path}").PlaySync()'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif system == "Darwin":
                subprocess.Popen(["afplay", tmp_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                for player in ["mpv", "ffplay", "aplay"]:
                    try:
                        subprocess.Popen(
                            [player, "-nodisp", "-autoexit", tmp_path] if player == "ffplay" else [player, tmp_path],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        break
                    except FileNotFoundError:
                        continue
        except ImportError:
            logger.error("edge-tts not installed. Run: pip install edge-tts")
        except Exception as e:
            logger.error("EdgeTTS speak error: %s", e)

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Yield MP3 audio chunks as they arrive from edge-tts."""
        try:
            import edge_tts
        except ImportError:
            logger.error("edge-tts not installed")
            return

        self._interrupted = False
        comm = edge_tts.Communicate(text, self._voice)
        async for chunk in comm.stream():
            if self._interrupted:
                break
            if chunk["type"] == "audio":
                yield chunk["data"]

    def interrupt(self) -> None:
        self._interrupted = True


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_tts_engine(name: str | None = None) -> LocalTTSEngine | EdgeTTSEngine:
    """Return a TTS engine instance by name (default: from config)."""
    name = (name or settings.voice.tts_engine).lower().replace("-", "")
    if name in ("edgetts", "edge"):
        return EdgeTTSEngine()
    return LocalTTSEngine()


# ---------------------------------------------------------------------------
# TextToSpeech — backward-compatible wrapper used by voice_loop / app
# ---------------------------------------------------------------------------


class TextToSpeech:
    """High-level TTS interface with event-bus integration."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus
        self._engine = get_tts_engine()
        self._speaking = False

    async def speak(self, text: str) -> None:
        self._speaking = True
        if self._event_bus:
            await self._event_bus.publish(EventType.TTS_START, {"text": text})

        await self._engine.speak(text)

        self._speaking = False
        if self._event_bus:
            await self._event_bus.publish(EventType.TTS_DONE, {"text": text})

    def interrupt(self) -> None:
        self._engine.interrupt()

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def set_rate(self, rate: int) -> None:
        if isinstance(self._engine, LocalTTSEngine):
            self._engine._rate = rate
            if self._engine._engine:
                self._engine._engine.setProperty("rate", rate)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]
