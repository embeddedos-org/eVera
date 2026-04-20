"""Tier-based intent routing for Voca.

@file voca/brain/router.py
@brief TierRouter classifies user transcripts into intents and routes
       them to the appropriate agent via a 4-tier system.

Tier 0: Regex-based instant responses (no LLM, free)
Tier 1: Local LLM (Ollama) classification
Tier 2: Cloud LLM (GPT-4o-mini / Gemini Flash) classification
Tier K: Keyword-based offline fallback
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from voca.providers.manager import ProviderManager
from voca.providers.models import ModelTier

logger = logging.getLogger(__name__)


@dataclass
class RouteDecision:
    """Result of intent classification."""

    tier: ModelTier
    agent_name: str
    intent: str
    confidence: float
    response_template: str | None = None  # For Tier 0 direct responses


# Tier 0: Regex-based instant responses (no LLM)
TIER0_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(r"\b(?:what\s+time|current\s+time|time\s+is\s+it)\b", re.I),
     "tier0", "get_time", "It's {time}! ⏰"),
    (re.compile(r"\bset\s+(?:a\s+)?timer?\s+(?:for\s+)?(\d+)\s*(min|minute|sec|second|hour)s?\b", re.I),
     "tier0", "set_timer", "Timer set for {duration}! ⏱️ I'll let you know when it's up!"),
    (re.compile(r"\b(?:stop|cancel|nevermind|never\s+mind)\b", re.I),
     "tier0", "cancel", "No worries, cancelled! 👍"),
    (re.compile(r"\b(?:thanks?|thank\s+you)\b", re.I),
     "tier0", "thanks", "You're welcome, buddy! 😊 Need anything else?"),
    (re.compile(r"\b(?:hello|hi|hey|good\s+(?:morning|afternoon|evening))\b", re.I),
     "companion", "greeting", "Hey there, buddy! 👋 How can I help you today?"),
    (re.compile(r"\b(?:what\s+(?:is\s+the\s+)?date|today'?s?\s+date|what\s+day)\b", re.I),
     "tier0", "get_date", "Today is {date} 📅"),
    (re.compile(r"\b(?:goodbye|bye|see\s+you|good\s+night)\b", re.I),
     "tier0", "goodbye", "See you later, buddy! 👋 I'll be right here when you need me!"),
    (re.compile(r"\bwho\s+are\s+you\b", re.I),
     "tier0", "identity", "I'm Voca, your AI buddy! 🤖 I'm here to help with anything you need — just ask!"),
    (re.compile(r"\b(?:help|what\s+can\s+you\s+do)\b", re.I),
     "tier0", "help", "I'm your all-in-one buddy! 🚀 I can help with:\n📅 Scheduling & reminders\n🏠 Smart home control\n🔍 Web research\n✍️ Writing & editing\n💻 PC automation\n💬 Casual chat & jokes\nJust tell me what you need!"),
]

# Intent → Agent mapping for LLM classification
INTENT_AGENT_MAP: dict[str, str] = {
    "schedule": "life_manager",
    "calendar": "life_manager",
    "email": "life_manager",
    "reminder": "life_manager",
    "todo": "life_manager",
    "meeting": "life_manager",
    "appointment": "life_manager",
    "light": "home_controller",
    "thermostat": "home_controller",
    "temperature": "home_controller",
    "lock": "home_controller",
    "security": "home_controller",
    "media": "home_controller",
    "music": "home_controller",
    "speaker": "home_controller",
    "play": "home_controller",
    "search": "researcher",
    "research": "researcher",
    "find": "researcher",
    "summarize": "researcher",
    "fact_check": "researcher",
    "lookup": "researcher",
    "google": "researcher",
    "wikipedia": "researcher",
    "write": "writer",
    "draft": "writer",
    "edit": "writer",
    "translate": "writer",
    "format": "writer",
    "compose": "writer",
    "proofread": "writer",
    "script": "operator",
    "open_app": "operator",
    "open": "operator",
    "launch": "operator",
    "run": "operator",
    "execute": "operator",
    "file": "operator",
    "folder": "operator",
    "screenshot": "operator",
    "automate": "operator",
    "command": "operator",
    "terminal": "operator",
    "market": "income",
    "invest": "income",
    "business": "income",
    "lead": "income",
    "monetize": "income",
    "stock": "income",
    "trading": "income",
    "portfolio": "income",
    "buy": "income",
    "sell": "income",
    "shares": "income",
    "crypto": "income",
    "bitcoin": "income",
    "nasdaq": "income",
    "dividend": "income",
    "watchlist": "income",
    "chat": "companion",
    "joke": "companion",
    "mood": "companion",
    "activity": "companion",
    "conversation": "companion",
    "feeling": "companion",
    "bored": "companion",
    "story": "companion",
    "code": "coder",
    "coding": "coder",
    "program": "coder",
    "programming": "coder",
    "debug": "coder",
    "function": "coder",
    "class": "coder",
    "variable": "coder",
    "refactor": "coder",
    "create_file": "coder",
    "read_file": "coder",
    "edit_file": "coder",
    "screen": "operator",
    "see": "operator",
    "look": "operator",
    "vision": "operator",
    "git": "git",
    "commit": "git",
    "push": "git",
    "pull": "git",
    "branch": "git",
    "merge": "git",
    "stash": "git",
    "diff": "git",
    "repo": "git",
    "review": "git",
    "browse": "browser",
    "website": "browser",
    "webpage": "browser",
    "login": "browser",
    "signin": "browser",
    "signup": "browser",
    "post": "browser",
    "tweet": "browser",
    "facebook": "browser",
    "instagram": "browser",
    "twitter": "browser",
    "linkedin": "browser",
    "reddit": "browser",
    "youtube": "browser",
    "social": "browser",
    "bookmark": "browser",
    "download": "browser",
}

# Extended keyword patterns for offline classification (regex → agent, intent)
KEYWORD_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # Operator — app/program launching
    (re.compile(r"\b(?:open|launch|start|run)\s+(?:(?:ms|microsoft)\s+)?(?:word|excel|powerpoint|notepad|chrome|firefox|edge|browser|calculator|paint|outlook|teams|code|vscode|terminal|cmd|powershell|explorer|spotify|discord|slack|zoom)\b", re.I),
     "operator", "open_app"),
    (re.compile(r"\b(?:open|launch|start|run)\s+\w+(?:\s+\w+)?\s*(?:app|application|program|document)?\b", re.I),
     "operator", "open_app"),
    (re.compile(r"\b(?:take\s+a?\s*screenshot|screen\s*cap(?:ture)?|print\s*screen)\b", re.I),
     "operator", "screenshot"),
    (re.compile(r"\b(?:create|make|new)\s+(?:a\s+)?(?:folder|directory|file)\b", re.I),
     "operator", "manage_files"),
    (re.compile(r"\b(?:delete|remove|move|copy|rename)\s+(?:the\s+)?(?:file|folder|directory)\b", re.I),
     "operator", "manage_files"),
    (re.compile(r"\b(?:run|execute)\s+(?:a\s+)?(?:script|command|program)\b", re.I),
     "operator", "execute_script"),

    # Home controller
    (re.compile(r"\b(?:turn|switch)\s+(?:on|off)\s+(?:the\s+)?(?:light|lamp|fan|tv|television)\b", re.I),
     "home_controller", "control_light"),
    (re.compile(r"\b(?:set|change|adjust)\s+(?:the\s+)?(?:temperature|thermostat|temp)\b", re.I),
     "home_controller", "set_thermostat"),
    (re.compile(r"\b(?:lock|unlock)\s+(?:the\s+)?(?:door|front|back|garage)\b", re.I),
     "home_controller", "lock_door"),
    (re.compile(r"\b(?:play|pause|stop|skip|next|previous)\s+(?:the\s+)?(?:music|song|track|video|movie|podcast)\b", re.I),
     "home_controller", "play_media"),

    # Life manager
    (re.compile(r"\b(?:schedule|book|plan)\s+(?:a\s+)?(?:meeting|event|appointment|call)\b", re.I),
     "life_manager", "schedule"),
    (re.compile(r"\b(?:remind\s+me|set\s+(?:a\s+)?reminder|don'?t\s+(?:let\s+me\s+)?forget)\b", re.I),
     "life_manager", "reminder"),
    (re.compile(r"\b(?:send|write|draft|compose)\s+(?:a(?:n)?\s+)?(?:email|mail|message)\b", re.I),
     "life_manager", "email"),
    (re.compile(r"\b(?:add|create)\s+(?:a\s+)?(?:to\s*-?\s*do|task|todo)\b", re.I),
     "life_manager", "todo"),
    (re.compile(r"\b(?:what'?s?\s+(?:on\s+)?my\s+(?:calendar|schedule|agenda))\b", re.I),
     "life_manager", "calendar"),

    # Researcher
    (re.compile(r"\b(?:search|look\s*up|google|find\s+(?:info|information)|research)\s+(?:for\s+)?(?:about\s+)?\b", re.I),
     "researcher", "search"),
    (re.compile(r"\b(?:summarize|summary\s+of|explain|what\s+is|who\s+is|define)\b", re.I),
     "researcher", "summarize"),

    # Writer
    (re.compile(r"\b(?:write|draft|compose)\s+(?:a\s+)?(?:letter|blog|post|article|essay|report|note)\b", re.I),
     "writer", "write"),
    (re.compile(r"\b(?:translate)\s+", re.I),
     "writer", "translate"),
    (re.compile(r"\b(?:proofread|edit|revise|rewrite)\b", re.I),
     "writer", "edit"),

    # Income / Stocks
    (re.compile(r"\b(?:stock|market|invest|portfolio|crypto|bitcoin|trading)\b", re.I),
     "income", "market"),
    (re.compile(r"\b(?:buy|sell|trade)\s+(?:\d+\s+)?(?:shares?\s+(?:of\s+)?)?\b[A-Z]{1,5}\b", re.I),
     "income", "trading"),
    (re.compile(r"\b(?:price|quote|ticker)\s+(?:of\s+|for\s+)?\b[A-Z]{1,5}\b", re.I),
     "income", "stock"),
    (re.compile(r"\b(?:how\s+(?:is|are)\s+(?:the\s+)?(?:market|stocks?|my\s+portfolio))\b", re.I),
     "income", "market"),
    (re.compile(r"\b(?:watchlist|watch\s+list|add\s+to\s+(?:my\s+)?watch)\b", re.I),
     "income", "market"),

    # Coder
    (re.compile(r"\b(?:create|write|make)\s+(?:a\s+)?(?:python|javascript|html|css|java|c\+\+|rust|go)\s+(?:file|script|program|class|function)\b", re.I),
     "coder", "code"),
    (re.compile(r"\b(?:read|show|display|cat|view)\s+(?:the\s+)?(?:file|code|source|contents)\b", re.I),
     "coder", "read_file"),
    (re.compile(r"\b(?:edit|modify|change|update|fix)\s+(?:the\s+)?(?:code|file|script|function|bug)\b", re.I),
     "coder", "edit_file"),
    (re.compile(r"\b(?:search|find|grep|look\s+for)\s+(?:in\s+)?(?:the\s+)?(?:code|codebase|files|project|source)\b", re.I),
     "coder", "search"),
    (re.compile(r"\bopen\s+(?:in\s+)?(?:vs\s*code|editor)\b", re.I),
     "coder", "code"),

    # Screen vision
    (re.compile(r"\b(?:what'?s?\s+(?:on\s+)?(?:my\s+)?screen|what\s+(?:do\s+)?you\s+see|look\s+at\s+(?:my\s+)?screen|analyze\s+(?:my\s+)?screen|read\s+(?:my\s+)?screen)\b", re.I),
     "operator", "screenshot"),

    # Browser
    (re.compile(r"\b(?:go\s+to|open|visit|navigate\s+to|browse)\s+(?:(?:the\s+)?website\s+)?(?:https?://)?[\w.-]+\.(?:com|org|net|io|dev|co|app|me)\b", re.I),
     "browser", "browse"),
    (re.compile(r"\b(?:log\s*in|sign\s*in|login|signin)\s+(?:to\s+)?(?:my\s+)?\w+\b", re.I),
     "browser", "login"),
    (re.compile(r"\b(?:post|tweet|share|publish)\s+(?:on|to|in)\s+(?:facebook|twitter|x|instagram|linkedin|reddit)\b", re.I),
     "browser", "post"),
    (re.compile(r"\b(?:check|read|open)\s+(?:my\s+)?(?:facebook|twitter|x|instagram|linkedin|reddit|gmail|email|inbox|feed|timeline|notifications)\b", re.I),
     "browser", "browse"),
]

CLASSIFICATION_PROMPT = """You are an intent classifier. Given the user's message, classify it into exactly one intent and agent.

Available agents and their domains:
- life_manager: calendar, scheduling, email, reminders, to-do lists
- home_controller: IoT devices, lights, thermostat, locks, media playback
- researcher: web search, summarization, academic papers, fact-checking
- writer: drafting text, editing, formatting, translation
- operator: PC automation, scripts, file management, screenshots, screen analysis, vision
- income: market monitoring, content drafting, lead tracking, opportunity analysis
- companion: open conversation, emotional support, mood, jokes, activities
- coder: reading, writing, editing code files, searching codebases, VS Code integration
- browser: web browsing, navigating websites, filling forms, logging in, social media posting, web automation

Respond with ONLY a JSON object (no markdown):
{"intent": "<intent>", "agent": "<agent_name>", "confidence": <0.0-1.0>}

User message: {transcript}"""


class TierRouter:
    """Routes user transcripts to the appropriate agent via tiered classification.

    Uses a cascading approach: Tier 0 (regex) → Tier 1 (local LLM) →
    Tier 2 (cloud LLM) → keyword fallback. Each tier is tried in order;
    if confidence is sufficient, routing stops.

    @param provider_manager: ProviderManager for LLM-based classification.
    """

    def __init__(self, provider_manager: ProviderManager) -> None:
        self._provider = provider_manager

    def try_tier0(self, transcript: str) -> RouteDecision | None:
        """Attempt Tier 0 regex matching."""
        for pattern, agent, intent, template in TIER0_PATTERNS:
            match = pattern.search(transcript)
            if match:
                logger.info("Tier 0 match: intent=%s agent=%s", intent, agent)
                return RouteDecision(
                    tier=ModelTier.REFLEX,
                    agent_name=agent,
                    intent=intent,
                    confidence=1.0,
                    response_template=template,
                )
        return None

    def classify_by_keywords(self, transcript: str) -> RouteDecision:
        """Offline keyword-based classification — no LLM needed."""
        lower = transcript.lower()

        # First try detailed regex patterns
        for pattern, agent, intent in KEYWORD_PATTERNS:
            if pattern.search(lower):
                logger.info("Keyword pattern match: agent=%s intent=%s", agent, intent)
                return RouteDecision(
                    tier=self._agent_tier(agent),
                    agent_name=agent,
                    intent=intent,
                    confidence=0.75,
                )

        # Fall back to simple word matching against INTENT_AGENT_MAP
        words = re.findall(r'\b\w+\b', lower)
        scores: dict[str, int] = {}
        matched_intent: dict[str, str] = {}

        for word in words:
            if word in INTENT_AGENT_MAP:
                agent = INTENT_AGENT_MAP[word]
                scores[agent] = scores.get(agent, 0) + 1
                matched_intent[agent] = word

        if scores:
            best_agent = max(scores, key=scores.get)
            intent = matched_intent.get(best_agent, "chat")
            logger.info("Keyword word match: agent=%s intent=%s", best_agent, intent)
            return RouteDecision(
                tier=self._agent_tier(best_agent),
                agent_name=best_agent,
                intent=intent,
                confidence=0.6,
            )

        # Default to companion
        logger.info("No keyword match — defaulting to companion")
        return RouteDecision(
            tier=ModelTier.EXECUTOR,
            agent_name="companion",
            intent="chat",
            confidence=0.4,
        )

    async def classify(self, transcript: str) -> RouteDecision:
        """Full classification pipeline: Tier 0 → Tier 1 → Tier 2 → Keywords."""
        # Tier 0: regex
        tier0 = self.try_tier0(transcript)
        if tier0:
            return tier0

        # Tier 1: local LLM classification
        try:
            decision = await self._classify_with_llm(transcript, ModelTier.EXECUTOR)
            if decision.confidence >= 0.6:
                return decision
            logger.info(
                "Tier 1 confidence %.2f < 0.6 — escalating to Tier 2",
                decision.confidence,
            )
        except Exception as e:
            logger.warning("Tier 1 classification failed: %s — escalating", e)

        # Tier 2: cloud LLM classification
        try:
            return await self._classify_with_llm(transcript, ModelTier.SPECIALIST)
        except Exception as e:
            logger.warning("Tier 2 classification failed: %s — using keyword fallback", e)

        # Tier K: keyword-based offline classification (no LLM needed)
        return self.classify_by_keywords(transcript)

    async def _classify_with_llm(self, transcript: str, tier: ModelTier) -> RouteDecision:
        """Use LLM to classify intent."""
        import json as json_mod

        prompt = CLASSIFICATION_PROMPT.format(transcript=transcript)
        result = await self._provider.complete(
            messages=[{"role": "user", "content": prompt}],
            tier=tier,
            max_tokens=100,
            temperature=0.1,
        )

        try:
            parsed = json_mod.loads(result.content.strip())
            agent_name = parsed.get("agent", "companion")
            intent = parsed.get("intent", "chat")
            confidence = float(parsed.get("confidence", 0.5))

            # Determine execution tier based on agent
            exec_tier = self._agent_tier(agent_name)

            return RouteDecision(
                tier=exec_tier,
                agent_name=agent_name,
                intent=intent,
                confidence=confidence,
            )
        except (json_mod.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse LLM classification: %s", e)
            return RouteDecision(
                tier=ModelTier.EXECUTOR,
                agent_name="companion",
                intent="chat",
                confidence=0.3,
            )

    def _agent_tier(self, agent_name: str) -> ModelTier:
        """Get the default execution tier for an agent."""
        tier_map = {
            "life_manager": ModelTier.SPECIALIST,
            "home_controller": ModelTier.EXECUTOR,
            "researcher": ModelTier.SPECIALIST,
            "writer": ModelTier.SPECIALIST,
            "operator": ModelTier.SPECIALIST,
            "income": ModelTier.STRATEGIST,
            "companion": ModelTier.EXECUTOR,
        }
        return tier_map.get(agent_name, ModelTier.EXECUTOR)
