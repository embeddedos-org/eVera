"""LangGraph StateGraph — the heart of Vera's processing pipeline.

@file vera/brain/graph.py
@brief Builds and compiles the LangGraph StateGraph that processes all user input.

Pipeline stages:
  enrich_memory → classify → safety_check → [tier0_handler | agent | confirmation] → store_memory → synthesize

Each stage is an async node function that reads/writes VeraState.
Conditional routing after safety_check determines whether to handle
the request as a Tier 0 regex response, delegate to an agent,
or ask for user confirmation.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from config import settings
from vera.brain.language import correct_spelling, detect_language
from vera.brain.state import VeraState
from vera.brain.supervisor import SupervisorAgent
from vera.emotional.mood_tracker import MoodTracker
from vera.emotional.sentiment import analyze_sentiment
from vera.memory.fact_extractor import extract_facts
from vera.memory.vault import MemoryVault
from vera.providers.manager import ProviderManager
from vera.providers.models import ModelTier
from vera.safety.policy import PolicyAction, PolicyService
from vera.safety.privacy import PrivacyGuard
from vera.events.bus import emit_pipeline_event

# Patterns to detect the user's name
NAME_PATTERNS = [
    re.compile(r"(?:my name is|i'm|i am|call me|they call me|name's)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.IGNORECASE),
]

logger = logging.getLogger(__name__)


def build_graph(
    provider_manager: ProviderManager,
    memory_vault: MemoryVault,
    policy_service: PolicyService,
    privacy_guard: PrivacyGuard,
) -> StateGraph:
    """Build and compile the Vera processing graph.

    Creates a LangGraph StateGraph with 7 nodes and conditional routing.
    Pipeline: enrich → classify → safety → (tier0 | agent | confirmation) → store → synthesize.

    @param provider_manager: Multi-LLM provider for agent inference.
    @param memory_vault: 4-layer memory system for context enrichment and storage.
    @param policy_service: Safety policy engine for action approval.
    @param privacy_guard: PII detection and anonymization.
    @return Compiled LangGraph StateGraph ready for inveration.
    """
    supervisor = SupervisorAgent(provider_manager)
    mood_tracker = MoodTracker(Path(settings.data_dir) / "mood_history.json")

    # Import agent registry lazily to avoid circular imports
    from vera.brain.agents import get_agent

    # --- Node functions ---

    async def enrich_memory_node(state: VeraState) -> VeraState:
        """Query memory for relevant context, correct spelling, detect language."""
        await emit_pipeline_event("enrich_memory", "working")
        transcript = state.get("transcript", "")

        # Spell correction for voice input mistakes
        corrected = correct_spelling(transcript)
        if corrected != transcript.lower():
            logger.info("Spell corrected: '%s' → '%s'", transcript, corrected)
            state["transcript"] = corrected
            transcript = corrected

        # Language detection
        lang = detect_language(transcript)
        if lang != "en":
            logger.info("Detected language: %s", lang)

        ctx = memory_vault.enrich(transcript, session_id=state.get("session_id"))

        # Detect and store user name
        for pattern in NAME_PATTERNS:
            match = pattern.search(transcript)
            if match:
                name = match.group(1).strip()
                memory_vault.remember_fact("user_name", name)
                logger.info("Learned user name: %s", name)
                break

        # Always inject user_name from semantic facts
        user_name = memory_vault.recall_fact("user_name")
        user_facts = ctx.user_facts
        if user_name:
            user_facts["user_name"] = user_name

        state["memory_context"] = {
            "conversation": ctx.conversation,
            "relevant_episodes": ctx.relevant_episodes,
            "user_facts": user_facts,
            "last_agent": ctx.last_agent,
        }
        state["conversation_history"] = ctx.conversation
        state["user_name"] = user_name or ""

        # --- Emotional intelligence: sentiment analysis ---
        if settings.emotional.enabled:
            try:
                sentiment_tier = ModelTier[settings.emotional.sentiment_tier]
                result = await analyze_sentiment(
                    transcript,
                    method=settings.emotional.sentiment_method,
                    provider_manager=provider_manager,
                    tier=sentiment_tier,
                )
                state["user_mood"] = result.mood
                state["user_mood_confidence"] = result.confidence
                state["user_mood_trigger"] = result.trigger or ""

                mood_tracker.record(
                    mood=result.mood,
                    confidence=result.confidence,
                    trigger=result.trigger,
                    transcript=transcript,
                )

                state["metadata"] = state.get("metadata", {})
                state["metadata"]["user_mood"] = result.mood
                state["metadata"]["user_mood_confidence"] = result.confidence

                logger.info("Sentiment: %s (%.2f) via %s", result.mood, result.confidence, result.method)
            except Exception as e:
                logger.warning("Sentiment analysis failed, defaulting to neutral: %s", e)
                state["user_mood"] = "neutral"
                state["user_mood_confidence"] = 0.0
                state["user_mood_trigger"] = ""

        await emit_pipeline_event(
            "enrich_memory", "done",
            corrected_text=state.get("transcript", ""),
            language=lang,
            user_name=state.get("user_name", ""),
        )
        return state

    async def classify_node(state: VeraState) -> VeraState:
        """Classify intent and route to agent."""
        await emit_pipeline_event("classify", "working")
        state = await supervisor.classify(state)
        await emit_pipeline_event(
            "classify", "done",
            agent_name=state.get("agent_name", ""),
            intent=state.get("intent", ""),
            tier=str(state.get("tier", "")),
            confidence=state.get("confidence", 0),
        )
        return state

    async def safety_check_node(state: VeraState) -> VeraState:
        """Check safety policies and privacy."""
        await emit_pipeline_event("safety_check", "working")
        transcript = state.get("transcript", "")
        agent_name = state.get("agent_name", "")
        intent = state.get("intent", "")

        # Privacy check — force local if sensitive
        if privacy_guard.should_process_locally(transcript):
            state["tier"] = ModelTier.EXECUTOR
            state["metadata"] = state.get("metadata", {})
            state["metadata"]["forced_local"] = True

        # Anonymize PII in transcript before sending to LLM
        state["transcript"] = privacy_guard.anonymize(transcript)

        # Policy check
        decision = policy_service.check(agent_name, intent)
        state["safety_approved"] = decision.action == PolicyAction.ALLOW
        state["needs_confirmation"] = decision.action == PolicyAction.CONFIRM

        if decision.action == PolicyAction.DENY:
            state["safety_approved"] = False
            state["agent_response"] = (
                f"I can't perform that action ({intent}). "
                f"Reason: {decision.reason}"
            )

        logger.debug("Safety: %s for %s.%s", decision.action.value, agent_name, intent)
        await emit_pipeline_event(
            "safety_check", "done",
            approved=state.get("safety_approved", False),
            needs_confirmation=state.get("needs_confirmation", False),
            forced_local=state.get("metadata", {}).get("forced_local", False),
        )
        return state

    async def tier0_handler_node(state: VeraState) -> VeraState:
        """Handle Tier 0 (regex) responses directly — no LLM."""
        await emit_pipeline_event("tier0_handler", "working")
        template = state.get("metadata", {}).get("response_template", "")
        intent = state.get("intent", "")
        user_name = state.get("user_name", "")
        name_suffix = f", {user_name}" if user_name else ""

        if intent == "get_time":
            now = datetime.now().strftime("%I:%M %p")
            state["agent_response"] = f"It's {now}{name_suffix}! ⏰"
            state["mood"] = "happy"
        elif intent == "get_date":
            today = datetime.now().strftime("%A, %B %d, %Y")
            state["agent_response"] = f"Today is {today}{name_suffix} 📅"
            state["mood"] = "happy"
        elif intent == "set_timer":
            state["agent_response"] = template.format(duration="the requested time")
            state["mood"] = "happy"
        else:
            state["agent_response"] = template
            state["mood"] = "neutral"

        state["metadata"] = state.get("metadata", {})
        state["metadata"]["tier_used"] = ModelTier.REFLEX
        state["metadata"]["no_llm"] = True
        await emit_pipeline_event(
            "tier0_handler", "done",
            intent=state.get("intent", ""),
            response_preview=state.get("agent_response", "")[:80],
        )
        return state

    async def agent_node(state: VeraState) -> VeraState:
        """Execute the selected agent."""
        await emit_pipeline_event("agent", "working")
        agent_name = state.get("agent_name", "companion")
        agent = get_agent(agent_name)

        if agent is None:
            logger.warning("Agent '%s' not found — falling back to companion", agent_name)
            agent = get_agent("companion")

        if agent is None:
            state["agent_response"] = "I'm sorry, no agent is available to handle that request."
            return state

        state = await agent.run(state)
        await emit_pipeline_event(
            "agent", "done",
            agent_name=agent_name,
            tool_count=len(state.get("tool_results", [])),
        )
        return state

    async def confirmation_node(state: VeraState) -> VeraState:
        """Handle actions requiring user confirmation."""
        await emit_pipeline_event("confirmation", "working")
        intent = state.get("intent", "")
        agent_name = state.get("agent_name", "")
        user_name = state.get("user_name", "")
        name_part = f" {user_name}" if user_name else ""
        state["agent_response"] = (
            f"Hey{name_part}! I'd like to do '{intent}' for you using {agent_name}. "
            "Should I go ahead? 🤔 (yes/no)"
        )
        state["mood"] = "thinking"
        pending = {
            "agent": agent_name,
            "intent": intent,
            "transcript": state.get("transcript", ""),
        }
        state["pending_action"] = pending

        # Store in brain for confirm_action() to replay
        from vera.core import VeraBrain
        brain = VeraBrain()
        brain.store_pending_action(state.get("session_id", "default"), pending)

        await emit_pipeline_event(
            "confirmation", "done",
            pending_action=f"{agent_name}.{intent}",
        )
        return state

    async def store_memory_node(state: VeraState) -> VeraState:
        """Store the interaction in memory."""
        await emit_pipeline_event("store_memory", "working")
        transcript = state.get("transcript", "")
        response = state.get("agent_response", "")
        agent = state.get("agent_name", "")

        memory_vault.store_interaction(
            transcript=transcript,
            response=response,
            agent=agent,
            metadata=state.get("metadata"),
            session_id=state.get("session_id"),
        )

        # --- LLM fact extraction ---
        facts_count = 0
        if settings.memory.fact_extraction_enabled:
            try:
                existing_facts = memory_vault.semantic.get_all()
                new_facts = await extract_facts(
                    transcript=transcript,
                    response=response,
                    existing_facts=existing_facts,
                    provider_manager=provider_manager,
                    settings=settings,
                )
                facts_count = len(new_facts)
                for key, value in new_facts.items():
                    memory_vault.remember_fact(key, value)
                    logger.info("Extracted fact: %s = %s", key, value)
            except Exception as e:
                logger.warning("Fact extraction failed: %s", e)

        await emit_pipeline_event(
            "store_memory", "done",
            facts_extracted=facts_count,
        )
        return state

    async def synthesize_node(state: VeraState) -> VeraState:
        """Prepare final response."""
        await emit_pipeline_event("synthesize", "working")
        state["final_response"] = state.get("agent_response", "I have nothing to say.")
        await emit_pipeline_event(
            "synthesize", "done",
            response_length=len(state.get("final_response", "")),
        )
        return state

    # --- Route function ---

    def route_after_safety(state: VeraState) -> str:
        """Determine next node based on safety check and tier."""
        if state.get("agent_response"):
            # Safety denied — response already set
            return "store_memory"
        if state.get("needs_confirmation"):
            return "confirmation"
        if state.get("tier") == ModelTier.REFLEX:
            return "tier0_handler"
        return "agent"

    # --- Build graph ---

    graph = StateGraph(VeraState)

    # Add nodes
    graph.add_node("enrich_memory", enrich_memory_node)
    graph.add_node("classify", classify_node)
    graph.add_node("safety_check", safety_check_node)
    graph.add_node("tier0_handler", tier0_handler_node)
    graph.add_node("agent", agent_node)
    graph.add_node("confirmation", confirmation_node)
    graph.add_node("store_memory", store_memory_node)
    graph.add_node("synthesize", synthesize_node)

    # Add edges
    graph.add_edge(START, "enrich_memory")
    graph.add_edge("enrich_memory", "classify")
    graph.add_edge("classify", "safety_check")

    # Conditional routing after safety
    graph.add_conditional_edges(
        "safety_check",
        route_after_safety,
        {
            "tier0_handler": "tier0_handler",
            "agent": "agent",
            "confirmation": "confirmation",
            "store_memory": "store_memory",
        },
    )

    graph.add_edge("tier0_handler", "store_memory")
    graph.add_edge("agent", "store_memory")
    graph.add_edge("confirmation", "store_memory")
    graph.add_edge("store_memory", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()
