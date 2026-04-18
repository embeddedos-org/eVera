"""VocaBrain — singleton orchestrator for the entire Voca system."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from config import settings
from voca.brain.graph import build_graph
from voca.brain.state import VocaState
from voca.events.bus import EventBus
from voca.memory.vault import MemoryVault
from voca.providers.manager import ProviderManager
from voca.providers.models import ModelTier
from voca.safety.policy import PolicyService
from voca.safety.privacy import PrivacyGuard

logger = logging.getLogger(__name__)


@dataclass
class VocaResponse:
    """Response from VocaBrain processing."""

    response: str
    agent: str
    tier: int
    intent: str = ""
    needs_confirmation: bool = False
    mood: str = "neutral"
    metadata: dict[str, Any] | None = None


class VocaBrain:
    """Central brain — initializes all components and runs the processing graph."""

    _instance: VocaBrain | None = None

    def __new__(cls) -> VocaBrain:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        settings.ensure_data_dirs()

        # Initialize components
        self.event_bus = EventBus()
        self.provider_manager = ProviderManager()
        self.memory_vault = MemoryVault()
        self.policy_service = PolicyService()
        self.privacy_guard = PrivacyGuard()

        # Proactive scheduler
        from voca.scheduler import ProactiveScheduler
        self.scheduler = ProactiveScheduler()

        # Build the LangGraph processing pipeline
        self.graph = build_graph(
            provider_manager=self.provider_manager,
            memory_vault=self.memory_vault,
            policy_service=self.policy_service,
            privacy_guard=self.privacy_guard,
        )

        logger.info("VocaBrain initialized")

    async def process(self, transcript: str, session_id: str | None = None) -> VocaResponse:
        """Process a user transcript through the full pipeline."""
        initial_state: VocaState = {
            "transcript": transcript,
            "session_id": session_id or "default",
            "metadata": {},
        }

        try:
            result = await self.graph.ainvoke(initial_state)

            return VocaResponse(
                response=result.get("final_response", ""),
                agent=result.get("agent_name", "unknown"),
                tier=result.get("tier", ModelTier.EXECUTOR),
                intent=result.get("intent", ""),
                needs_confirmation=result.get("needs_confirmation", False),
                mood=result.get("mood", "neutral"),
                metadata=result.get("metadata"),
            )
        except Exception as e:
            logger.exception("Error processing transcript: %s", e)
            return VocaResponse(
                response=f"I encountered an error: {e}",
                agent="system",
                tier=ModelTier.REFLEX,
                mood="error",
                metadata={"error": str(e)},
            )

    async def confirm_action(self, session_id: str) -> VocaResponse:
        """Confirm a pending action — replay it through the pipeline with safety bypassed."""
        pending = getattr(self, "_pending_actions", {}).get(session_id)

        if not pending:
            return VocaResponse(
                response="No pending action to confirm! What would you like me to do? 🤔",
                agent="system",
                tier=ModelTier.REFLEX,
                mood="neutral",
            )

        # Replay the pending action through the pipeline
        try:
            result = await self.process(
                transcript=pending.get("transcript", ""),
                session_id=session_id,
            )

            # Clear the pending action
            self._pending_actions.pop(session_id, None)

            return VocaResponse(
                response=f"Done! ✅ {result.response}",
                agent=result.agent,
                tier=result.tier,
                intent=result.intent,
                mood="happy",
                metadata=result.metadata,
            )
        except Exception as e:
            logger.exception("Error confirming action: %s", e)
            return VocaResponse(
                response=f"Hmm, something went wrong while executing that: {e} 😕",
                agent="system",
                tier=ModelTier.REFLEX,
                mood="error",
            )

    def store_pending_action(self, session_id: str, action: dict) -> None:
        """Store a pending action for later confirmation."""
        if not hasattr(self, "_pending_actions"):
            self._pending_actions = {}
        self._pending_actions[session_id] = action

    async def start(self) -> None:
        """Start background services."""
        await self.event_bus.start()
        await self.scheduler.start()
        logger.info("VocaBrain started (scheduler active)")

    async def stop(self) -> None:
        """Gracefully shut down."""
        await self.scheduler.stop()
        await self.event_bus.stop()
        self.memory_vault.save_all()
        logger.info("VocaBrain stopped — memory saved")

    def get_status(self) -> dict[str, Any]:
        return {
            "status": "running",
            "memory": self.memory_vault.get_stats(),
            "llm_usage": self.provider_manager.get_usage(),
            "memory_facts": self.memory_vault.semantic.get_all(),
        }

    def get_event_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent events from the event bus."""
        return self.event_bus.get_recent_events(limit)
