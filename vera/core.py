"""VeraBrain — singleton orchestrator for the entire Vera system.

@file vera/core.py
@brief Central brain module that initializes and coordinates all Vera components.

VeraBrain is a singleton that wires together the LangGraph pipeline,
memory vault, provider manager, safety engine, event bus, and scheduler.
All user interactions flow through VeraBrain.process().
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from config import settings
from vera.brain.agents.vision import VisionMonitor
from vera.brain.graph import build_graph
from vera.brain.state import VeraState
from vera.events.bus import EventBus, emit_pipeline_event
from vera.memory.vault import MemoryVault
from vera.providers.manager import ProviderManager
from vera.providers.models import ModelTier
from vera.safety.policy import PolicyService
from vera.safety.privacy import PrivacyGuard

logger = logging.getLogger(__name__)


@dataclass
class VeraResponse:
    """Response from VeraBrain processing."""

    response: str
    agent: str
    tier: int
    intent: str = ""
    needs_confirmation: bool = False
    mood: str = "neutral"
    metadata: dict[str, Any] | None = None


class VeraBrain:
    """Central brain — initializes all components and runs the processing graph.

    Singleton orchestrator that owns all Vera subsystems and exposes
    a single async `process()` method for handling user input.

    @note Uses the singleton pattern via `__new__` to ensure exactly one
    instance exists across the application lifecycle.
    """

    _instance: VeraBrain | None = None

    def __new__(cls) -> VeraBrain:
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
        from vera.scheduler import ProactiveScheduler

        self.scheduler = ProactiveScheduler()

        # Vision monitor
        self.vision_monitor = VisionMonitor(event_bus=self.event_bus)
        self._last_screen_context: str = ""

        # Build the LangGraph processing pipeline
        self.graph = build_graph(
            provider_manager=self.provider_manager,
            memory_vault=self.memory_vault,
            policy_service=self.policy_service,
            privacy_guard=self.privacy_guard,
        )

        logger.info("VeraBrain initialized")

    async def _on_screen_context(self, _event_type: Any, data: dict[str, Any]) -> None:
        """Callback for SCREEN_CONTEXT events from VisionMonitor."""
        self._last_screen_context = data.get("description", "")

    async def process(self, transcript: str, session_id: str | None = None, voice_mode: bool = False) -> VeraResponse:
        """Process a user transcript through the full LangGraph pipeline.

        Runs the transcript through: enrich_memory → classify → safety_check →
        [tier0_handler | agent | confirmation] → store_memory → synthesize.

        @param transcript: The user's natural language input.
        @param session_id: Optional session identifier for multi-session support.
        @param voice_mode: If True, agents use concise spoken-style responses.
        @return VeraResponse with the agent's response, metadata, and mood.
        """
        metadata: dict[str, Any] = {}
        if self._last_screen_context:
            metadata["screen_context"] = self._last_screen_context
        if voice_mode:
            metadata["voice_mode"] = True

        initial_state: VeraState = {
            "transcript": transcript,
            "session_id": session_id or "default",
            "metadata": metadata,
        }

        try:
            pipeline_nodes = [
                "enrich_memory",
                "classify",
                "safety_check",
                "tier0_handler",
                "agent",
                "confirmation",
                "store_memory",
                "synthesize",
            ]
            await emit_pipeline_event("pipeline", "start", nodes=pipeline_nodes)
            t0 = time.monotonic()

            result = await self.graph.ainvoke(initial_state)

            elapsed_ms = round((time.monotonic() - t0) * 1000)
            await emit_pipeline_event("pipeline", "end", elapsed_ms=elapsed_ms)

            return VeraResponse(
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
            return VeraResponse(
                response=f"I encountered an error: {e}",
                agent="system",
                tier=ModelTier.REFLEX,
                mood="error",
                metadata={"error": str(e)},
            )

    async def confirm_action(self, session_id: str) -> VeraResponse:
        """Confirm a pending action — replay it through the pipeline.

        Called when the user confirms a previously requested action
        that required explicit approval (e.g., file deletion, broker trade).

        @param session_id: Session ID to look up the pending action.
        @return VeraResponse with the confirmed action's result.
        """
        pending = getattr(self, "_pending_actions", {}).get(session_id)

        if not pending:
            return VeraResponse(
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

            return VeraResponse(
                response=f"Done! ✅ {result.response}",
                agent=result.agent,
                tier=result.tier,
                intent=result.intent,
                mood="happy",
                metadata=result.metadata,
            )
        except Exception as e:
            logger.exception("Error confirming action: %s", e)
            return VeraResponse(
                response=f"Hmm, something went wrong while executing that: {e} 😕",
                agent="system",
                tier=ModelTier.REFLEX,
                mood="error",
            )

    def store_pending_action(self, session_id: str, action: dict) -> None:
        """Store a pending action for later confirmation.

        @param session_id: Session ID to associate the pending action with.
        @param action: Dictionary containing agent, intent, and transcript.
        """
        if not hasattr(self, "_pending_actions"):
            self._pending_actions = {}
        self._pending_actions[session_id] = action

    async def start(self) -> None:
        """Start background services (event bus, proactive scheduler, vision monitor)."""
        await self.event_bus.start()
        await self.scheduler.start()

        # Subscribe to screen context events and start vision monitor
        from vera.events.bus import EventType

        self.event_bus.subscribe(EventType.SCREEN_CONTEXT, self._on_screen_context)
        await self.vision_monitor.start()

        logger.info("VeraBrain started (scheduler + vision monitor active)")

    async def stop(self) -> None:
        """Gracefully shut down all services and persist memory to disk."""
        await self.vision_monitor.stop()
        await self.scheduler.stop()
        await self.event_bus.stop()
        self.memory_vault.save_all()
        logger.info("VeraBrain stopped — memory saved")

    def get_status(self) -> dict[str, Any]:
        """Return system status including memory stats and LLM usage.

        @return Dictionary with status, memory stats, LLM usage, and semantic facts.
        """
        return {
            "status": "running",
            "memory": self.memory_vault.get_stats(),
            "llm_usage": self.provider_manager.get_usage(),
            "memory_facts": self.memory_vault.semantic.get_all(),
        }

    def get_event_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent events from the event bus.

        @param limit: Maximum number of events to return (default 50).
        @return List of event dictionaries ordered newest-first.
        """
        return self.event_bus.get_recent_events(limit)
