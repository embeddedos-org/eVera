"""LangGraph StateGraph — the heart of Voca's processing pipeline."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from langgraph.graph import END, StateGraph

try:
    from langgraph.graph import START
except ImportError:
    START = "__start__"

from voca.brain.language import correct_spelling, detect_language
from voca.brain.state import VocaState
from voca.brain.supervisor import SupervisorAgent
from voca.memory.vault import MemoryVault
from voca.providers.manager import ProviderManager
from voca.providers.models import ModelTier
from voca.safety.policy import PolicyAction, PolicyService
from voca.safety.privacy import PrivacyGuard

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
    """Build and compile the Voca processing graph.

    Pipeline: enrich → classify → safety → (tier0 | agent) → store → synthesize
    """
    supervisor = SupervisorAgent(provider_manager)

    # Import agent registry lazily to avoid circular imports
    from voca.brain.agents import get_agent

    # --- Node functions ---

    async def enrich_memory_node(state: VocaState) -> VocaState:
        """Query memory for relevant context, correct spelling, detect language."""
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

        ctx = memory_vault.enrich(transcript)

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
        return state

    async def classify_node(state: VocaState) -> VocaState:
        """Classify intent and route to agent."""
        return await supervisor.classify(state)

    async def safety_check_node(state: VocaState) -> VocaState:
        """Check safety policies and privacy."""
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
        return state

    async def tier0_handler_node(state: VocaState) -> VocaState:
        """Handle Tier 0 (regex) responses directly — no LLM."""
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
        return state

    async def agent_node(state: VocaState) -> VocaState:
        """Execute the selected agent."""
        agent_name = state.get("agent_name", "companion")
        agent = get_agent(agent_name)

        if agent is None:
            logger.warning("Agent '%s' not found — falling back to companion", agent_name)
            agent = get_agent("companion")

        if agent is None:
            state["agent_response"] = "I'm sorry, no agent is available to handle that request."
            return state

        return await agent.run(state)

    async def confirmation_node(state: VocaState) -> VocaState:
        """Handle actions requiring user confirmation."""
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
        from voca.core import VocaBrain
        brain = VocaBrain()
        brain.store_pending_action(state.get("session_id", "default"), pending)

        return state

    async def store_memory_node(state: VocaState) -> VocaState:
        """Store the interaction in memory."""
        transcript = state.get("transcript", "")
        response = state.get("agent_response", "")
        agent = state.get("agent_name", "")

        memory_vault.store_interaction(
            transcript=transcript,
            response=response,
            agent=agent,
            metadata=state.get("metadata"),
        )
        return state

    async def synthesize_node(state: VocaState) -> VocaState:
        """Prepare final response."""
        state["final_response"] = state.get("agent_response", "I have nothing to say.")
        return state

    # --- Route function ---

    def route_after_safety(state: VocaState) -> str:
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

    graph = StateGraph(VocaState)

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
