"""Tests for tier-based routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from vera.brain.router import TierRouter
from vera.providers.models import ModelTier


@pytest.fixture
def router():
    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock()
    return TierRouter(mock_provider)


def test_tier0_time_query(router: TierRouter):
    result = router.try_tier0("What time is it?")
    assert result is not None
    assert result.tier == ModelTier.REFLEX
    assert result.intent == "get_time"
    assert result.confidence == 1.0


def test_tier0_timer(router: TierRouter):
    result = router.try_tier0("Set a timer for 5 minutes")
    assert result is not None
    assert result.tier == ModelTier.REFLEX
    assert result.intent == "set_timer"


def test_tier0_greeting(router: TierRouter):
    result = router.try_tier0("Hello there")
    assert result is not None
    assert result.agent_name == "companion"
    assert result.intent == "greeting"


def test_tier0_cancel(router: TierRouter):
    result = router.try_tier0("Stop")
    assert result is not None
    assert result.intent == "cancel"


def test_tier0_miss(router: TierRouter):
    result = router.try_tier0("Draft an email about Q3 results")
    assert result is None


@pytest.mark.asyncio
async def test_classify_fallback(router: TierRouter):
    router._provider.complete = AsyncMock(side_effect=Exception("LLM unavailable"))
    result = await router.classify("Tell me about quantum physics")
    assert result.agent_name == "companion"
    assert result.confidence <= 0.5
