"""Tests for WakeWordDetector."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, patch

import pytest

from vera.perception.wake_word import WakeWordDetector, _MIN_DURATION_S, _MAX_DURATION_S


def _make_audio_bytes(duration_s: float, sample_rate: int = 16000) -> bytes:
    """Create silent PCM int16 audio bytes of a given duration."""
    num_samples = int(sample_rate * duration_s)
    return struct.pack(f"<{num_samples}h", *([0] * num_samples))


@pytest.fixture
def mock_stt():
    stt = MagicMock()
    stt.transcribe = MagicMock(return_value="")
    return stt


@pytest.fixture
def detector(mock_stt):
    with patch("vera.perception.wake_word.settings") as mock_settings:
        mock_settings.voice.wake_word_phrase = "hey vera"
        yield WakeWordDetector(stt=mock_stt)


class TestWakeWordDetector:
    """Tests for wake phrase matching and duration guards."""

    def test_exact_match(self, detector, mock_stt):
        mock_stt.transcribe.return_value = "hey vera"
        audio = _make_audio_bytes(1.0)
        assert detector.check(audio) is True

    def test_fuzzy_hey_siri(self, detector, mock_stt):
        mock_stt.transcribe.return_value = "hey siri"
        audio = _make_audio_bytes(1.0)
        assert detector.check(audio) is True

    def test_fuzzy_hey_sree(self, detector, mock_stt):
        mock_stt.transcribe.return_value = "hey sree"
        audio = _make_audio_bytes(1.0)
        assert detector.check(audio) is True

    def test_fuzzy_a_vera(self, detector, mock_stt):
        mock_stt.transcribe.return_value = "a vera"
        audio = _make_audio_bytes(1.0)
        assert detector.check(audio) is True

    def test_case_insensitive(self, detector, mock_stt):
        mock_stt.transcribe.return_value = "HEY VERA"
        audio = _make_audio_bytes(1.0)
        assert detector.check(audio) is True

    def test_embedded_in_sentence(self, detector, mock_stt):
        mock_stt.transcribe.return_value = "uh hey vera what time is it"
        audio = _make_audio_bytes(1.5)
        assert detector.check(audio) is True

    def test_no_match(self, detector, mock_stt):
        mock_stt.transcribe.return_value = "what is the weather today"
        audio = _make_audio_bytes(1.0)
        assert detector.check(audio) is False

    def test_empty_transcript(self, detector, mock_stt):
        mock_stt.transcribe.return_value = ""
        audio = _make_audio_bytes(1.0)
        assert detector.check(audio) is False

    def test_too_short_skipped(self, detector, mock_stt):
        """Audio shorter than _MIN_DURATION_S should be skipped entirely."""
        audio = _make_audio_bytes(0.1)  # well below 0.3s
        result = detector.check(audio)
        assert result is False
        mock_stt.transcribe.assert_not_called()

    def test_too_long_skipped(self, detector, mock_stt):
        """Audio longer than _MAX_DURATION_S should be skipped entirely."""
        audio = _make_audio_bytes(5.0)  # well above 3.0s
        result = detector.check(audio)
        assert result is False
        mock_stt.transcribe.assert_not_called()

    def test_valid_duration_range(self, detector, mock_stt):
        """Audio within duration bounds should be transcribed."""
        mock_stt.transcribe.return_value = "hello"
        audio = _make_audio_bytes(1.0)
        detector.check(audio)
        mock_stt.transcribe.assert_called_once()
