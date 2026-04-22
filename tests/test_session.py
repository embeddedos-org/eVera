"""Tests for VoiceSession state machine."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from vera.perception.session import SessionState, VoiceSession


@pytest.fixture
def session_wake_on():
    """VoiceSession with wake word enabled."""
    with patch("vera.perception.session.settings") as mock_settings:
        mock_settings.voice.wake_word_enabled = True
        mock_settings.voice.wake_word_timeout_s = 2
        yield VoiceSession()


@pytest.fixture
def session_wake_off():
    """VoiceSession with wake word disabled (always-on mode)."""
    with patch("vera.perception.session.settings") as mock_settings:
        mock_settings.voice.wake_word_enabled = False
        mock_settings.voice.wake_word_timeout_s = 10
        yield VoiceSession()


class TestVoiceSessionStates:
    """Test state transitions."""

    def test_initial_state_wake_on(self, session_wake_on):
        assert session_wake_on.state == SessionState.LISTENING
        assert session_wake_on.is_active is False

    def test_initial_state_wake_off(self, session_wake_off):
        assert session_wake_off.state == SessionState.ACTIVE
        assert session_wake_off.is_active is True

    @pytest.mark.asyncio
    async def test_activate(self, session_wake_on):
        await session_wake_on.activate()
        assert session_wake_on.state == SessionState.ACTIVE
        assert session_wake_on.is_active is True

    @pytest.mark.asyncio
    async def test_deactivate(self, session_wake_on):
        await session_wake_on.activate()
        await session_wake_on.deactivate()
        assert session_wake_on.state == SessionState.LISTENING
        assert session_wake_on.is_active is False

    @pytest.mark.asyncio
    async def test_activate_already_active_is_noop(self, session_wake_on):
        await session_wake_on.activate()
        await session_wake_on.activate()  # second call is noop
        assert session_wake_on.state == SessionState.ACTIVE

    @pytest.mark.asyncio
    async def test_deactivate_already_listening_is_noop(self, session_wake_on):
        await session_wake_on.deactivate()  # already listening
        assert session_wake_on.state == SessionState.LISTENING


class TestTimeout:
    """Test timeout behavior."""

    def test_no_timeout_when_wake_disabled(self, session_wake_off):
        assert session_wake_off.is_timed_out() is False

    @pytest.mark.asyncio
    async def test_timeout_after_inactivity(self, session_wake_on):
        await session_wake_on.activate()
        # Simulate time passing beyond timeout
        session_wake_on._last_activity = time.time() - 5
        assert session_wake_on.is_timed_out() is True

    @pytest.mark.asyncio
    async def test_touch_resets_timeout(self, session_wake_on):
        await session_wake_on.activate()
        session_wake_on._last_activity = time.time() - 5
        session_wake_on.touch()
        assert session_wake_on.is_timed_out() is False


class TestGoodbye:
    """Test goodbye phrase detection."""

    @pytest.mark.parametrize("phrase", [
        "goodbye",
        "Goodbye!",
        "thanks vera",
        "Thanks Vera!",
        "that's all",
        "thats all",
        "never mind",
        "stop listening",
        "go to sleep",
    ])
    def test_goodbye_detected(self, phrase):
        assert VoiceSession.is_goodbye(phrase) is True

    @pytest.mark.parametrize("phrase", [
        "what's the weather",
        "tell me a joke",
        "hello",
        "set a timer",
    ])
    def test_not_goodbye(self, phrase):
        assert VoiceSession.is_goodbye(phrase) is False


class TestEventBusIntegration:
    """Test that session publishes events."""

    @pytest.mark.asyncio
    async def test_activate_publishes_session_started(self):
        mock_bus = AsyncMock()
        with patch("vera.perception.session.settings") as mock_settings:
            mock_settings.voice.wake_word_enabled = True
            mock_settings.voice.wake_word_timeout_s = 10
            session = VoiceSession(event_bus=mock_bus)
            await session.activate()
            mock_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_publishes_session_ended(self):
        mock_bus = AsyncMock()
        with patch("vera.perception.session.settings") as mock_settings:
            mock_settings.voice.wake_word_enabled = True
            mock_settings.voice.wake_word_timeout_s = 10
            session = VoiceSession(event_bus=mock_bus)
            await session.activate()
            mock_bus.reset_mock()
            await session.deactivate()
            mock_bus.publish.assert_called_once()
