"""Tests for voice personality addendum in BaseAgent system prompts."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from vera.brain.agents.base import VOICE_PERSONALITY_ADDENDUM, BaseAgent


class _StubAgent(BaseAgent):
    """Minimal concrete agent for testing."""

    name = "test_agent"
    description = "Stub agent for tests"
    system_prompt = "You are a test agent."

    def _setup_tools(self) -> None:
        pass


class TestVoicePersonality:
    """Verify voice personality addendum is injected correctly."""

    def test_voice_mode_off_no_addendum(self):
        agent = _StubAgent()
        state = {"transcript": "hello", "metadata": {"voice_mode": False}}
        prompt = agent._build_system_prompt(state)
        assert "VOICE MODE GUIDELINES" not in prompt

    def test_voice_mode_on_includes_addendum(self):
        agent = _StubAgent()
        state = {"transcript": "hello", "metadata": {"voice_mode": True}}
        prompt = agent._build_system_prompt(state)
        assert "VOICE MODE GUIDELINES" in prompt
        assert "2-3 sentences" in prompt
        assert "sound like a helpful friend" in prompt

    def test_no_metadata_no_addendum(self):
        agent = _StubAgent()
        state = {"transcript": "hello"}
        prompt = agent._build_system_prompt(state)
        assert "VOICE MODE GUIDELINES" not in prompt

    def test_empty_metadata_no_addendum(self):
        agent = _StubAgent()
        state = {"transcript": "hello", "metadata": {}}
        prompt = agent._build_system_prompt(state)
        assert "VOICE MODE GUIDELINES" not in prompt

    def test_addendum_content_quality(self):
        """Verify the addendum has all the expected guidelines."""
        assert "concise" in VOICE_PERSONALITY_ADDENDUM.lower()
        assert "markdown" in VOICE_PERSONALITY_ADDENDUM.lower()
        assert "conversational" in VOICE_PERSONALITY_ADDENDUM.lower()
