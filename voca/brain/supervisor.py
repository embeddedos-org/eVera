"""Supervisor agent — orchestrates routing and conversation continuity."""

from __future__ import annotations

import logging

from voca.brain.router import RouteDecision, TierRouter
from voca.brain.state import VocaState
from voca.providers.manager import ProviderManager
from voca.providers.models import ModelTier

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """Top-level supervisor that routes transcripts and maintains conversation flow."""

    def __init__(self, provider_manager: ProviderManager) -> None:
        self._router = TierRouter(provider_manager)
        self._last_agent: str | None = None
        self._last_intent: str | None = None

    async def classify(self, state: VocaState) -> VocaState:
        """Classify the transcript and update state with routing decision."""
        transcript = state.get("transcript", "")

        # Handle follow-up patterns
        if self._is_followup(transcript) and self._last_agent:
            logger.info("Follow-up detected — reusing agent: %s", self._last_agent)
            state["agent_name"] = self._last_agent
            state["intent"] = self._last_intent or "followup"
            state["tier"] = self._router._agent_tier(self._last_agent)
            state["confidence"] = 0.9
            return state

        # Full classification
        decision: RouteDecision = await self._router.classify(transcript)

        state["agent_name"] = decision.agent_name
        state["intent"] = decision.intent
        state["tier"] = decision.tier
        state["confidence"] = decision.confidence

        # Store Tier 0 template if applicable
        if decision.response_template:
            state["metadata"] = state.get("metadata", {})
            state["metadata"]["response_template"] = decision.response_template

        # Track for follow-ups
        if decision.agent_name != "tier0":
            self._last_agent = decision.agent_name
            self._last_intent = decision.intent

        logger.info(
            "Classification: agent=%s intent=%s tier=%s confidence=%.2f",
            decision.agent_name,
            decision.intent,
            ModelTier(decision.tier).name,
            decision.confidence,
        )
        return state

    def _is_followup(self, transcript: str) -> bool:
        """Detect follow-up patterns like 'tell me more', 'and also', etc."""
        followup_phrases = [
            "tell me more",
            "go on",
            "continue",
            "and also",
            "what else",
            "more about",
            "elaborate",
            "can you expand",
            "keep going",
        ]
        lower = transcript.lower().strip()
        return any(phrase in lower for phrase in followup_phrases)

    def reset(self) -> None:
        """Reset conversation tracking."""
        self._last_agent = None
        self._last_intent = None
