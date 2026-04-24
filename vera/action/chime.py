"""Activation chime — short audio feedback when wake word is detected.

Plays a brief 440Hz sine wave tone (200ms) via sounddevice to give
instant audio feedback before the TTS response starts.
Falls back to a printed bell emoji if audio playback fails.
"""

from __future__ import annotations

import logging

import numpy as np

from config import settings

logger = logging.getLogger(__name__)

_CHIME_FREQ_HZ = 440
_CHIME_DURATION_S = 0.2
_CHIME_SAMPLE_RATE = 44100
_CHIME_AMPLITUDE = 0.3


async def play_activation_chime() -> None:
    """Play a short activation chime sound.

    Gated by settings.voice.wake_word_chime. Uses sounddevice (already
    a dependency for AudioStream). Falls back to print if unavailable.
    """
    if not settings.voice.wake_word_chime:
        return

    try:
        import asyncio

        import sounddevice as sd

        t = np.linspace(0, _CHIME_DURATION_S, int(_CHIME_SAMPLE_RATE * _CHIME_DURATION_S), endpoint=False)
        # Apply a smooth envelope to avoid clicks
        envelope = np.sin(np.pi * t / _CHIME_DURATION_S)
        tone = (_CHIME_AMPLITUDE * np.sin(2 * np.pi * _CHIME_FREQ_HZ * t) * envelope).astype(np.float32)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: sd.play(tone, samplerate=_CHIME_SAMPLE_RATE, blocking=True),
        )
        logger.debug("Activation chime played")
    except Exception as e:
        logger.debug("Chime playback failed (%s), using fallback", e)
        logger.info("🔔")
