"""Tests for the LangGraph processing pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vera.brain.state import VeraState
from vera.providers.models import ModelTier


@pytest.fixture
def mock_graph():
    """Build a graph with fully mocked LLM."""
    with (
        patch("vera.providers.manager.litellm") as mock_litellm,
        patch("vera.memory.vault.settings") as mock_mem_settings,
        patch("vera.safety.policy.settings") as mock_safety_settings,
    ):
        # Memory settings
        mock_mem_settings.memory.working_memory_max_turns = 10
        mock_mem_settings.memory.embedding_model = "all-MiniLM-L6-v2"
        mock_mem_settings.memory.faiss_index_path = None
        mock_mem_settings.memory.semantic_store_path = None
        mock_mem_settings.memory.secure_vault_path = None

        # Safety settings
        mock_safety_settings.safety.denied_actions = ["transfer_money"]
        mock_safety_settings.safety.confirm_actions = ["execute_script"]
        mock_safety_settings.safety.allowed_actions = ["chat", "get_time"]

        # LLM mock
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"intent":"chat","agent":"companion","confidence":0.9}'))
        ]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)

        from vera.brain.graph import build_graph
        from vera.memory.vault import MemoryVault
        from vera.providers.manager import ProviderManager
        from vera.safety.policy import PolicyService
        from vera.safety.privacy import PrivacyGuard

        pm = ProviderManager()
        mv = MemoryVault()
        ps = PolicyService()
        pg = PrivacyGuard()

        graph = build_graph(pm, mv, ps, pg)
        yield graph, mock_litellm


@pytest.mark.asyncio
async def test_tier0_flow(mock_graph):
    """Tier 0 queries should not invoke LLM."""
    graph, mock_litellm = mock_graph
    state: VeraState = {"transcript": "What time is it?", "session_id": "test", "metadata": {}}
    result = await graph.ainvoke(state)

    assert result["final_response"] is not None
    assert "time" in result["final_response"].lower() or ":" in result["final_response"]
    assert result.get("tier") == ModelTier.REFLEX


@pytest.mark.asyncio
async def test_agent_flow(mock_graph):
    """Non-tier0 queries should route to an agent via LLM."""
    graph, mock_litellm = mock_graph

    # First call = classification (Tier 1), second call = fallback (Tier 2)
    classify_msg = MagicMock(
        content='{"intent":"chat","agent":"companion","confidence":0.9}',
        tool_calls=None,
    )
    classify_resp = MagicMock()
    classify_resp.choices = [MagicMock(message=classify_msg)]
    classify_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)

    mock_litellm.acompletion = AsyncMock(return_value=classify_resp)

    state: VeraState = {"transcript": "Tell me a joke", "session_id": "test", "metadata": {}}
    result = await graph.ainvoke(state)

    assert result["final_response"] is not None
    assert result["agent_name"] == "companion"
