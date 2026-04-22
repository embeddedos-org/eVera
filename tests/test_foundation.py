"""Foundational Tests — core system integrity, startup, shutdown, state management."""

from __future__ import annotations


class TestVeraBrainLifecycle:
    """Test VeraBrain initialization, start, stop."""

    def test_brain_singleton(self):
        """VeraBrain should be a singleton."""
        from vera.core import VeraBrain

        # Reset singleton for test
        VeraBrain._instance = None
        b1 = VeraBrain()
        b2 = VeraBrain()
        assert b1 is b2
        VeraBrain._instance = None

    def test_brain_has_all_components(self):
        from vera.core import VeraBrain

        VeraBrain._instance = None
        brain = VeraBrain()
        assert brain.event_bus is not None
        assert brain.provider_manager is not None
        assert brain.memory_vault is not None
        assert brain.policy_service is not None
        assert brain.privacy_guard is not None
        assert brain.scheduler is not None
        assert brain.graph is not None
        VeraBrain._instance = None

    def test_vera_response_fields(self):
        from vera.core import VeraResponse

        r = VeraResponse(response="hi", agent="test", tier=0)
        assert r.response == "hi"
        assert r.agent == "test"
        assert r.tier == 0
        assert r.mood == "neutral"
        assert r.intent == ""
        assert r.needs_confirmation is False

    def test_vera_response_with_mood(self):
        from vera.core import VeraResponse

        r = VeraResponse(response="yay", agent="companion", tier=1, mood="happy")
        assert r.mood == "happy"


class TestVeraState:
    """Test state TypedDict has all required fields."""

    def test_state_fields_exist(self):
        from vera.brain.state import VeraState

        # TypedDict with total=False — all fields optional
        annotations = VeraState.__annotations__
        required = [
            "transcript",
            "session_id",
            "user_name",
            "intent",
            "tier",
            "agent_name",
            "confidence",
            "memory_context",
            "conversation_history",
            "agent_response",
            "tool_results",
            "mood",
            "safety_approved",
            "needs_confirmation",
            "pending_action",
            "final_response",
            "metadata",
        ]
        for field in required:
            assert field in annotations, f"Missing field: {field}"

    def test_state_can_be_created(self):
        from vera.brain.state import VeraState

        state: VeraState = {
            "transcript": "hello",
            "session_id": "test-1",
            "user_name": "Alice",
            "mood": "happy",
        }
        assert state["transcript"] == "hello"
        assert state["mood"] == "happy"


class TestConfigDefaults:
    """Test configuration has secure defaults."""

    def test_server_defaults(self):
        from config import settings

        assert settings.server.host == "127.0.0.1"
        assert settings.server.port == 8000
        assert "*" not in settings.server.cors_origins

    def test_safety_defaults(self):
        from config import settings

        assert "transfer_money" in settings.safety.denied_actions
        assert "execute_script" in settings.safety.confirm_actions

    def test_memory_defaults(self):
        from config import settings

        assert settings.memory.working_memory_max_turns == 20
        assert settings.memory.embedding_model == "all-MiniLM-L6-v2"


class TestModelTiers:
    """Test LLM tier system."""

    def test_tier_ordering(self):
        from vera.providers.models import ModelTier

        assert ModelTier.REFLEX < ModelTier.EXECUTOR
        assert ModelTier.EXECUTOR < ModelTier.SPECIALIST
        assert ModelTier.SPECIALIST < ModelTier.STRATEGIST

    def test_tier_values(self):
        from vera.providers.models import ModelTier

        assert ModelTier.REFLEX == 0
        assert ModelTier.EXECUTOR == 1
        assert ModelTier.SPECIALIST == 2
        assert ModelTier.STRATEGIST == 3

    def test_default_models_exist(self):
        from vera.providers.models import DEFAULT_MODELS, ModelTier

        assert ModelTier.REFLEX in DEFAULT_MODELS
        assert ModelTier.EXECUTOR in DEFAULT_MODELS
        assert ModelTier.SPECIALIST in DEFAULT_MODELS
        assert ModelTier.STRATEGIST in DEFAULT_MODELS
        assert len(DEFAULT_MODELS[ModelTier.REFLEX]) == 0  # No LLM for reflex
        assert len(DEFAULT_MODELS[ModelTier.EXECUTOR]) >= 1
