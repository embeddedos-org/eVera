"""Shared pytest fixtures for eVera backup tests."""
from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Ensure vera package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── EventBus fixture ──────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def event_bus():
    """Provide a fresh EventBus instance for each test."""
    from vera.events.bus import EventBus
    bus = EventBus()
    yield bus
    # Cleanup: stop if running
    try:
        await bus.stop()
    except Exception:
        pass


# ── SafetyPolicy fixture ──────────────────────────────────────────────────────
@pytest.fixture
def safety_policy():
    """Provide a PolicyService with default rules."""
    from vera.safety.policy import PolicyService
    return PolicyService()


@pytest.fixture
def privacy_guard():
    """Provide a PrivacyGuard instance."""
    from vera.safety.privacy import PrivacyGuard
    return PrivacyGuard()


# ── ProviderManager fixture (mocked LLM calls) ───────────────────────────────
@pytest.fixture
def mock_provider():
    """Provide a ProviderManager with mocked LLM backend."""
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="mocked response"))]
        )
        from vera.providers.manager import ProviderManager
        mgr = ProviderManager.__new__(ProviderManager)
        mgr._providers = {}
        mgr._active = None
        yield mgr


# ── TierRouter fixture ────────────────────────────────────────────────────────
@pytest.fixture
def tier_router(mock_provider):
    """Provide a TierRouter with mocked provider."""
    from vera.brain.router import TierRouter
    router = TierRouter.__new__(TierRouter)
    router.provider = mock_provider
    router._tier0_patterns = []
    return router


# ── Memory fixtures ───────────────────────────────────────────────────────────
@pytest.fixture
def memory_vault(tmp_path):
    """Provide a MemoryVault backed by a temp directory."""
    from vera.memory.vault import MemoryVault
    vault = MemoryVault(db_path=str(tmp_path / "vault.db"))
    yield vault
    vault.close()


# ── RBAC fixture ──────────────────────────────────────────────────────────────
@pytest.fixture
def rbac_manager():
    """Provide an RBACManager with default roles."""
    from vera.rbac import RBACManager
    return RBACManager()


# ── Scheduler fixture ─────────────────────────────────────────────────────────
@pytest.fixture
def scheduler():
    """Provide a ProactiveScheduler instance."""
    from vera.scheduler import ProactiveScheduler
    return ProactiveScheduler.__new__(ProactiveScheduler)

# ── policy_service alias (used by test_safety.py) ────────────────────────────
@pytest.fixture
def policy_service():
    """Alias for safety_policy — used by test_safety.py."""
    from vera.safety.policy import PolicyService
    return PolicyService()
