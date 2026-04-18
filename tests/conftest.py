"""Shared test fixtures."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def event_bus():
    from voca.events.bus import EventBus
    return EventBus()


@pytest.fixture
def provider_manager():
    from voca.providers.manager import ProviderManager
    with patch("voca.providers.manager.litellm") as mock_litellm:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Mock response"))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        yield ProviderManager()


@pytest.fixture
def memory_vault(tmp_path):
    with patch("voca.memory.vault.settings") as mock_settings:
        mock_settings.memory.working_memory_max_turns = 10
        mock_settings.memory.embedding_model = "all-MiniLM-L6-v2"
        mock_settings.memory.faiss_index_path = tmp_path / "faiss"
        mock_settings.memory.semantic_store_path = tmp_path / "semantic.json"
        mock_settings.memory.secure_vault_path = tmp_path / "vault.enc"
        from voca.memory.vault import MemoryVault
        vault = MemoryVault()
        yield vault


@pytest.fixture
def policy_service():
    from voca.safety.policy import PolicyService
    return PolicyService()


@pytest.fixture
def privacy_guard():
    from voca.safety.privacy import PrivacyGuard
    return PrivacyGuard()
