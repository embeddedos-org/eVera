"""Voice session state machine — LISTENING ↔ ACTIVE lifecycle.

Tracks whether eVera is passively listening for a wake word or actively
engaged in a conversation. Handles timeout-based deactivation and
goodbye phrase detection.

When wake_word_enabled=False, the session stays permanently ACTIVE,
preserving the original always-on behavior.
"""

from __future__ import annotations

import logging
import re
import time
from enum import Enum

from config import settings
from vera.events.bus import EventBus, EventType

logger = logging.getLogger(__name__)

_GOODBYE_PATTERNS = [
    re.compile(r"\bgoodbye\b", re.IGNORECASE),
    re.compile(r"\bthanks?\s+vera\b", re.IGNORECASE),
    re.compile(r"\bthat'?s\s+all\b", re.IGNORECASE),
    re.compile(r"\bnever\s+mind\b", re.IGNORECASE),
    re.compile(r"\bstop\s+listening\b", re.IGNORECASE),
    re.compile(r"\bgo\s+to\s+sleep\b", re.IGNORECASE),
]


class SessionState(str, Enum):
    LISTENING = "listening"
    ACTIVE = "active"
    PROCESSING = "processing"


class VoiceSession:
    """Manages the LISTENING → ACTIVE → LISTENING lifecycle.

    In LISTENING state, only wake word detection runs.
    In ACTIVE state, full STT → Brain → TTS pipeline processes speech.
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus
        self._timeout_s = settings.voice.wake_word_timeout_s
        self._wake_enabled = settings.voice.wake_word_enabled
        self._last_activity = time.time()

        # If wake word is disabled, start in ACTIVE (always-on mode)
        self._state = SessionState.LISTENING if self._wake_enabled else SessionState.ACTIVE

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state in (SessionState.ACTIVE, SessionState.PROCESSING)

    async def activate(self) -> None:
        """Transition to ACTIVE state and publish SESSION_STARTED."""
        if self._state == SessionState.ACTIVE:
            return
        self._state = SessionState.ACTIVE
        self._last_activity = time.time()
        logger.info("Voice session activated")
        if self._event_bus:
            await self._event_bus.publish(EventType.SESSION_STARTED)

    async def deactivate(self) -> None:
        """Transition to LISTENING state and publish SESSION_ENDED."""
        if self._state == SessionState.LISTENING:
            return
        self._state = SessionState.LISTENING
        logger.info("Voice session deactivated")
        if self._event_bus:
            await self._event_bus.publish(EventType.SESSION_ENDED)

    def touch(self) -> None:
        """Reset the inactivity timer (call on every user interaction)."""
        self._last_activity = time.time()

    def is_timed_out(self) -> bool:
        """Check if the session has exceeded the inactivity timeout."""
        if not self._wake_enabled:
            return False
        return time.time() - self._last_activity > self._timeout_s

    @staticmethod
    def is_goodbye(transcript: str) -> bool:
        """Detect goodbye phrases that should end the session."""
        for pattern in _GOODBYE_PATTERNS:
            if pattern.search(transcript):
                return True
        return False
