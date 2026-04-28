"""Tier-based intent routing for Vera.

@file vera/brain/router.py
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

from vera.providers.manager import ProviderManager
from vera.providers.models import ModelTier

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
    (re.compile(r"\b(?:what\s+time|current\s+time|time\s+is\s+it)\b", re.I), "tier0", "get_time", "It's {time}! ⏰"),
    (
        re.compile(r"\bset\s+(?:a\s+)?timer?\s+(?:for\s+)?(\d+)\s*(min|minute|sec|second|hour)s?\b", re.I),
        "tier0",
        "set_timer",
        "Timer set for {duration}! ⏱️ I'll let you know when it's up!",
    ),
    (re.compile(r"\b(?:stop|cancel|nevermind|never\s+mind)\b", re.I), "tier0", "cancel", "No worries, cancelled! 👍"),
    (
        re.compile(r"\b(?:thanks?|thank\s+you)\b", re.I),
        "tier0",
        "thanks",
        "You're welcome, buddy! 😊 Need anything else?",
    ),
    (
        re.compile(r"\b(?:hello|hi|hey|good\s+(?:morning|afternoon|evening))\b", re.I),
        "companion",
        "greeting",
        "Hey there, buddy! 👋 How can I help you today?",
    ),
    (
        re.compile(r"\b(?:what\s+(?:is\s+the\s+)?date|today'?s?\s+date|what\s+day)\b", re.I),
        "tier0",
        "get_date",
        "Today is {date} 📅",
    ),
    (
        re.compile(r"\b(?:goodbye|bye|see\s+you|good\s+night)\b", re.I),
        "tier0",
        "goodbye",
        "See you later, buddy! 👋 I'll be right here when you need me!",
    ),
    (
        re.compile(r"\bwho\s+are\s+you\b", re.I),
        "tier0",
        "identity",
        "I'm Vera, your AI buddy! 🤖 I'm here to help with anything you need — just ask!",
    ),
    (
        re.compile(r"\b(?:help|what\s+can\s+you\s+do)\b", re.I),
        "tier0",
        "help",
        "I'm your all-in-one buddy! 🚀 I can help with:\n📅 Scheduling & reminders\n🏠 Smart home control\n🔍 Web research\n✍️ Writing & editing\n💻 PC automation\n💬 Casual chat & jokes\nJust tell me what you need!",
    ),
]

# Intent → Agent mapping for LLM classification
INTENT_AGENT_MAP: dict[str, str] = {
    "schedule": "life_manager",
    "calendar": "calendar",
    "email": "life_manager",
    "reminder": "life_manager",
    "todo": "life_manager",
    "meeting": "meeting",
    "appointment": "life_manager",
    "light": "home_controller",
    "thermostat": "home_controller",
    "temperature": "home_controller",
    "lock": "home_controller",
    "security": "home_controller",
    "media": "home_controller",
    "music": "music",
    "media_player": "home_controller",
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
    "translate": "translation",
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
    "automate": "automation",
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
    # Content creation
    "video_script": "content_creator",
    "content": "content_creator",
    "marketing": "content_creator",
    "seo": "content_creator",
    "schedule_post": "content_creator",
    # Media factory — image gen, video assembly, upload
    "generate_image": "media_factory",
    "create_reel": "media_factory",
    "edit_image": "media_factory",
    "edit_photo": "media_factory",
    "remove_background": "media_factory",
    "voiceover": "media_factory",
    "subtitle": "media_factory",
    "upload_youtube": "media_factory",
    "upload_instagram": "media_factory",
    "assemble_video": "media_factory",
    "make_video": "media_factory",
    "animated": "media_factory",
    "reel": "media_factory",
    "thumbnail": "media_factory",
    "video": "media_factory",
    "tiktok": "media_factory",
    "youtube_video": "media_factory",
    "publish": "media_factory",
    # Finance
    "balance": "finance",
    "bank": "finance",
    "account": "finance",
    "transaction": "finance",
    "spending": "finance",
    "budget": "finance",
    "expense": "finance",
    "saving": "finance",
    # Email reading
    "inbox": "life_manager",
    "unread": "life_manager",
    "reply": "life_manager",
    "mail": "life_manager",
    # Job hunting
    "job": "job_hunter",
    "apply": "job_hunter",
    "resume": "job_hunter",
    "career": "job_hunter",
    "hiring": "job_hunter",
    "application": "job_hunter",
    "interview": "job_hunter",
    "employment": "job_hunter",
    "vacancy": "job_hunter",
    "position": "job_hunter",
    # Planner
    "plan": "planner",
    "planning": "planner",
    "priority": "planner",
    "prioritize": "planner",
    "goal": "planner",
    "goals": "planner",
    "daily_review": "planner",
    "weekly_review": "planner",
    "monthly_review": "planner",
    # Wellness
    "focus": "wellness",
    "break": "wellness",
    "pomodoro": "wellness",
    "energy": "wellness",
    "burnout": "wellness",
    "screen_time": "wellness",
    "wellness": "wellness",
    "rest": "wellness",
    # Digest
    "digest": "digest",
    "news": "digest",
    "rss": "digest",
    "feed": "digest",
    "briefing": "digest",
    "reading_list": "digest",
    "newsletter": "digest",
    "summarize_thread": "digest",
    # Language learning
    "learn": "language_tutor",
    "language": "language_tutor",
    "teach": "language_tutor",
    "spanish": "language_tutor",
    "french": "language_tutor",
    "german": "language_tutor",
    "italian": "language_tutor",
    "japanese": "language_tutor",
    "korean": "language_tutor",
    "chinese": "language_tutor",
    "portuguese": "language_tutor",
    "vocabulary": "language_tutor",
    "grammar": "language_tutor",
    "pronunciation": "language_tutor",
    "tutor": "language_tutor",
    "lesson": "language_tutor",
    # Live trading
    "ibkr": "live_trader",
    "interactive brokers": "live_trader",
    "tradestation": "live_trader",
    "schwab": "live_trader",
    "thinkorswim": "live_trader",
    "live trade": "live_trader",
    "paper trade": "live_trader",
    "backtest": "live_trader",
    "regime": "live_trader",
    "dca": "live_trader",
    "risk check": "live_trader",
    # Jira / ticket management
    "jira": "jira",
    "ticket": "jira",
    "sprint": "jira",
    "backlog": "jira",
    "kanban": "jira",
    "issue": "jira",
    "assignee": "jira",
    # Codebase indexer
    "index": "codebase_indexer",
    "codebase": "codebase_indexer",
    "architecture": "codebase_indexer",
    "project_structure": "codebase_indexer",
    # Diagram / visualization
    "diagram": "diagram",
    "flowchart": "diagram",
    "call_graph": "diagram",
    "class_diagram": "diagram",
    "visualize": "diagram",
    # Meeting notes
    "meeting_notes": "meeting",
    "action_items": "meeting",
    "transcript": "meeting",
    "minutes": "meeting",
    # Work pilot
    "work_on": "work_pilot",
    "do_ticket": "work_pilot",
    "start_work": "work_pilot",
    "work_item": "work_pilot",
    # Git additions
    "pr": "git",
    "pull_request": "git",
}

# Extended keyword patterns for offline classification (regex → agent, intent)
KEYWORD_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # Operator — app/program launching
    (
        re.compile(
            r"\b(?:open|launch|start|run)\s+(?:(?:ms|microsoft)\s+)?(?:word|excel|powerpoint|notepad|chrome|firefox|edge|browser|calculator|paint|outlook|teams|code|vscode|terminal|cmd|powershell|explorer|spotify|discord|slack|zoom)\b",
            re.I,
        ),
        "operator",
        "open_app",
    ),
    (
        re.compile(r"\b(?:open|launch|start|run)\s+\w+(?:\s+\w+)?\s*(?:app|application|program|document)?\b", re.I),
        "operator",
        "open_app",
    ),
    (
        re.compile(r"\b(?:take\s+a?\s*screenshot|screen\s*cap(?:ture)?|print\s*screen)\b", re.I),
        "operator",
        "screenshot",
    ),
    (re.compile(r"\b(?:create|make|new)\s+(?:a\s+)?(?:folder|directory|file)\b", re.I), "operator", "manage_files"),
    (
        re.compile(r"\b(?:delete|remove|move|copy|rename)\s+(?:the\s+)?(?:file|folder|directory)\b", re.I),
        "operator",
        "manage_files",
    ),
    (re.compile(r"\b(?:run|execute)\s+(?:a\s+)?(?:script|command|program)\b", re.I), "operator", "execute_script"),
    # Home controller
    (
        re.compile(r"\b(?:turn|switch)\s+(?:on|off)\s+(?:the\s+)?(?:light|lamp|fan|tv|television)\b", re.I),
        "home_controller",
        "control_light",
    ),
    (
        re.compile(r"\b(?:set|change|adjust)\s+(?:the\s+)?(?:temperature|thermostat|temp)\b", re.I),
        "home_controller",
        "set_thermostat",
    ),
    (re.compile(r"\b(?:lock|unlock)\s+(?:the\s+)?(?:door|front|back|garage)\b", re.I), "home_controller", "lock_door"),
    (
        re.compile(
            r"\b(?:play|pause|stop|skip|next|previous)\s+(?:the\s+)?(?:music|song|track|video|movie|podcast)\b", re.I
        ),
        "home_controller",
        "play_media",
    ),
    # Life manager
    (
        re.compile(r"\b(?:schedule|book|plan)\s+(?:a\s+)?(?:meeting|event|appointment|call)\b", re.I),
        "life_manager",
        "schedule",
    ),
    (
        re.compile(r"\b(?:remind\s+me|set\s+(?:a\s+)?reminder|don'?t\s+(?:let\s+me\s+)?forget)\b", re.I),
        "life_manager",
        "reminder",
    ),
    (
        re.compile(r"\b(?:send|write|draft|compose)\s+(?:a(?:n)?\s+)?(?:email|mail|message)\b", re.I),
        "life_manager",
        "email",
    ),
    (re.compile(r"\b(?:add|create)\s+(?:a\s+)?(?:to\s*-?\s*do|task|todo)\b", re.I), "life_manager", "todo"),
    (re.compile(r"\b(?:what'?s?\s+(?:on\s+)?my\s+(?:calendar|schedule|agenda))\b", re.I), "life_manager", "calendar"),
    # Researcher
    (
        re.compile(
            r"\b(?:search|look\s*up|google|find\s+(?:info|information)|research)\s+(?:for\s+)?(?:about\s+)?\b", re.I
        ),
        "researcher",
        "search",
    ),
    (re.compile(r"\b(?:summarize|summary\s+of|explain|what\s+is|who\s+is|define)\b", re.I), "researcher", "summarize"),
    # Writer (translate pattern moved after language_tutor translate)
    (
        re.compile(r"\b(?:write|draft|compose)\s+(?:a\s+)?(?:letter|blog|post|article|essay|report|note)\b", re.I),
        "writer",
        "write",
    ),
    (re.compile(r"\b(?:proofread|edit|revise|rewrite)\b", re.I), "writer", "edit"),
    # Income / Stocks
    (re.compile(r"\b(?:stock|market|invest|portfolio|crypto|bitcoin|trading)\b", re.I), "income", "market"),
    (
        re.compile(r"\b(?:buy|sell|trade)\s+(?:\d+\s+)?(?:shares?\s+(?:of\s+)?)?\b[A-Z]{1,5}\b", re.I),
        "income",
        "trading",
    ),
    (re.compile(r"\b(?:price|quote|ticker)\s+(?:of\s+|for\s+)?\b[A-Z]{1,5}\b", re.I), "income", "stock"),
    (re.compile(r"\b(?:how\s+(?:is|are)\s+(?:the\s+)?(?:market|stocks?|my\s+portfolio))\b", re.I), "income", "market"),
    (re.compile(r"\b(?:watchlist|watch\s+list|add\s+to\s+(?:my\s+)?watch)\b", re.I), "income", "market"),
    # Coder
    (
        re.compile(
            r"\b(?:create|write|make)\s+(?:a\s+)?(?:python|javascript|html|css|java|c\+\+|rust|go)\s+(?:file|script|program|class|function)\b",
            re.I,
        ),
        "coder",
        "code",
    ),
    (
        re.compile(r"\b(?:read|show|display|cat|view)\s+(?:the\s+)?(?:file|code|source|contents)\b", re.I),
        "coder",
        "read_file",
    ),
    (
        re.compile(r"\b(?:edit|modify|change|update|fix)\s+(?:the\s+)?(?:code|file|script|function|bug)\b", re.I),
        "coder",
        "edit_file",
    ),
    (
        re.compile(
            r"\b(?:search|find|grep|look\s+for)\s+(?:in\s+)?(?:the\s+)?(?:code|codebase|files|project|source)\b", re.I
        ),
        "coder",
        "search",
    ),
    (re.compile(r"\bopen\s+(?:in\s+)?(?:vs\s*code|editor)\b", re.I), "coder", "code"),
    # Screen vision
    (
        re.compile(
            r"\b(?:what'?s?\s+(?:on\s+)?(?:my\s+)?screen|what\s+(?:do\s+)?you\s+see|look\s+at\s+(?:my\s+)?screen|analyze\s+(?:my\s+)?screen|read\s+(?:my\s+)?screen)\b",
            re.I,
        ),
        "operator",
        "screenshot",
    ),
    # Job hunter
    (
        re.compile(r"\b(?:apply|search|find|look)\s+(?:for\s+)?(?:a\s+)?(?:job|position|role|opening)s?\b", re.I),
        "job_hunter",
        "search_jobs",
    ),
    (re.compile(r"\b(?:job|career)\s+(?:search|hunt|application|apply)\b", re.I), "job_hunter", "search_jobs"),
    (re.compile(r"\b(?:update|edit)\s+(?:my\s+)?(?:resume|cv|profile)\b", re.I), "job_hunter", "update_profile"),
    (re.compile(r"\b(?:check|show|list)\s+(?:my\s+)?(?:applications?|applied)\b", re.I), "job_hunter", "check_status"),
    # Planner
    (
        re.compile(r"\b(?:plan|start|organize)\s+(?:my\s+)?(?:day|morning|week|month)\b", re.I),
        "planner",
        "morning_plan",
    ),
    (re.compile(r"\b(?:daily|weekly|monthly)\s+(?:review|retrospective|retro)\b", re.I), "planner", "daily_review"),
    (re.compile(r"\b(?:set|add|create)\s+(?:a\s+)?goal\b", re.I), "planner", "set_goals"),
    (re.compile(r"\b(?:check|show|view|my)\s+goals?\b", re.I), "planner", "check_goals"),
    (
        re.compile(r"\b(?:prioritize|rank|score)\s+(?:my\s+)?(?:tasks?|todos?|to-dos?)\b", re.I),
        "planner",
        "priority_score",
    ),
    # Wellness
    (re.compile(r"\b(?:start|begin)\s+(?:a\s+)?(?:focus|pomodoro|deep\s+work)\b", re.I), "wellness", "start_focus"),
    (re.compile(r"\b(?:take|need)\s+(?:a\s+)?break\b", re.I), "wellness", "take_break"),
    (re.compile(r"\b(?:screen\s+time|how\s+long.*working)\b", re.I), "wellness", "screen_time"),
    (re.compile(r"\b(?:energy|how\s+am\s+i\s+feeling|tired|exhausted)\b", re.I), "wellness", "energy_check"),
    (re.compile(r"\b(?:work\s+hours|set\s+(?:my\s+)?(?:work|office)\s+hours)\b", re.I), "wellness", "set_work_hours"),
    (
        re.compile(r"\b(?:wellness|wellbeing|burnout)\s+(?:report|summary|check)\b", re.I),
        "wellness",
        "wellness_summary",
    ),
    # Digest
    (re.compile(r"\b(?:generate|show|my)\s+(?:daily\s+)?digest\b", re.I), "digest", "generate_digest"),
    (re.compile(r"\b(?:add|subscribe)\s+(?:to\s+)?(?:rss|feed|source|newsletter)\b", re.I), "digest", "add_source"),
    (re.compile(r"\b(?:reading\s+list|read\s+later|save\s+(?:for\s+)?later)\b", re.I), "digest", "reading_list"),
    (
        re.compile(r"\b(?:summarize)\s+(?:this\s+)?(?:thread|conversation|email\s+thread)\b", re.I),
        "digest",
        "summarize_thread",
    ),
    # Language learning
    (
        re.compile(
            r"\b(?:teach|learn|study|practice)\s+(?:me\s+)?(?:some\s+)?(?:spanish|french|german|italian|japanese|korean|chinese|portuguese|english|arabic|russian|hindi|dutch|turkish|swedish|telugu)\b",
            re.I,
        ),
        "language_tutor",
        "learn_language",
    ),
    (
        re.compile(
            r"\b(?:how\s+do\s+(?:you|I)\s+say|translate)\s+.+\s+(?:in|to)\s+(?:spanish|french|german|italian|japanese|korean|chinese|portuguese|arabic|russian|hindi)\b",
            re.I,
        ),
        "language_tutor",
        "vocabulary",
    ),
    (
        re.compile(r"\b(?:language\s+lesson|vocab(?:ulary)?\s+(?:lesson|practice)|conversation\s+practice)\b", re.I),
        "language_tutor",
        "learn_language",
    ),
    (
        re.compile(
            r"\b(?:quiz\s+me|test\s+me)\s+(?:on|in)\s+(?:spanish|french|german|italian|japanese|korean)\b", re.I
        ),
        "language_tutor",
        "quiz",
    ),
    (re.compile(r"\b(?:pronounce|pronunciation\s+(?:of|help|guide))\b", re.I), "language_tutor", "pronunciation"),
    # Browser
    (
        re.compile(
            r"\b(?:go\s+to|open|visit|navigate\s+to|browse)\s+(?:(?:the\s+)?website\s+)?(?:https?://)?[\w.-]+\.(?:com|org|net|io|dev|co|app|me)\b",
            re.I,
        ),
        "browser",
        "browse",
    ),
    (re.compile(r"\b(?:log\s*in|sign\s*in|login|signin)\s+(?:to\s+)?(?:my\s+)?\w+\b", re.I), "browser", "login"),
    (
        re.compile(
            r"\b(?:post|tweet|share|publish)\s+(?:on|to|in)\s+(?:facebook|twitter|x|instagram|linkedin|reddit)\b", re.I
        ),
        "browser",
        "post",
    ),
    (
        re.compile(
            r"\b(?:check|read|open)\s+(?:my\s+)?(?:facebook|twitter|x|instagram|linkedin|reddit|gmail|email|inbox|feed|timeline|notifications)\b",
            re.I,
        ),
        "browser",
        "browse",
    ),
    # Jira / tickets
    (re.compile(r"\b(?:show|get|list|check)\s+(?:my\s+)?tickets?\b", re.I), "jira", "get_my_tickets"),
    (re.compile(r"\bcreate\s+(?:a\s+)?ticket\b", re.I), "jira", "create_ticket"),
    (re.compile(r"\bsprint\s+board\b", re.I), "jira", "list_sprint_tickets"),
    (re.compile(r"\b(?:get|show|fetch)\s+(?:ticket\s+)?[A-Z]+-\d+\b", re.I), "jira", "get_ticket"),
    (re.compile(r"\b(?:update|move|change)\s+(?:ticket\s+)?status\b", re.I), "jira", "update_ticket_status"),
    # Codebase indexer
    (
        re.compile(r"\b(?:index|analyze|understand)\s+(?:the\s+)?(?:codebase|project|repo)\b", re.I),
        "codebase_indexer",
        "index_project",
    ),
    (
        re.compile(r"\b(?:project|codebase)\s+(?:structure|architecture|overview)\b", re.I),
        "codebase_indexer",
        "get_architecture_summary",
    ),
    (re.compile(r"\bfind\s+(?:files?\s+)?related\s+(?:to|files?)\b", re.I), "codebase_indexer", "find_related_files"),
    # Diagram / visualization
    (
        re.compile(r"\b(?:generate|show|create)\s+(?:a\s+)?(?:call\s+graph|class\s+diagram|flowchart)\b", re.I),
        "diagram",
        "diagram",
    ),
    (re.compile(r"\bvisualize\s+(?:the\s+)?(?:code|project|architecture)\b", re.I), "diagram", "visualize"),
    (re.compile(r"\b(?:diagram|graph)\s+(?:of|for)\s+", re.I), "diagram", "diagram"),
    # Meeting
    (re.compile(r"\b(?:extract|get|find)\s+action\s+items\b", re.I), "meeting", "extract_action_items"),
    (re.compile(r"\b(?:parse|process)\s+meeting\b", re.I), "meeting", "parse_meeting_notes"),
    (
        re.compile(r"\bcreate\s+(?:tasks?|todos?)\s+from\s+(?:the\s+)?meeting\b", re.I),
        "meeting",
        "create_tasks_from_meeting",
    ),
    # Work pilot
    (re.compile(r"\b(?:start|begin)\s+work(?:ing)?\s+on\b", re.I), "work_pilot", "start_work_on_ticket"),
    (re.compile(r"\bdo\s+(?:my\s+)?ticket\b", re.I), "work_pilot", "start_work_on_ticket"),
    (re.compile(r"\bcomplete\s+(?:the\s+)?work\b", re.I), "work_pilot", "complete_work_item"),
    # Git — PR creation
    (re.compile(r"\b(?:create|open|make)\s+(?:a\s+)?(?:pr|pull\s+request)\b", re.I), "git", "git_create_pr"),
]

CLASSIFICATION_PROMPT = """You are an intent classifier. Given the user's message, classify it into exactly one intent and agent.

Available agents and their domains:
- life_manager: calendar, scheduling, email (read/send/reply), reminders, to-do lists
- home_controller: IoT devices, lights, thermostat, locks, media playback
- researcher: web search, summarization, academic papers, fact-checking
- writer: drafting text, editing, formatting, translation
- operator: PC automation, scripts, file management, screenshots, screen analysis, vision
- income: market monitoring, stock trading, portfolio, content drafting, lead tracking
- companion: open conversation, emotional support, mood, jokes, activities
- coder: reading, writing, editing code files, searching codebases, VS Code integration
- browser: web browsing, navigating websites, filling forms, logging in, social media posting, web automation
- content_creator: video creation, social media scheduling, content scripts, SEO optimization, marketing
- media_factory: image generation, photo editing, video assembly, subtitles, voiceovers, YouTube/Instagram/TikTok upload, reel creation
- finance: bank accounts, balances, transactions, spending analysis, budgets
- job_hunter: job searching, applications, resume, career, hiring
- planner: daily/weekly/monthly planning, goal setting, priority scoring, Eisenhower matrix, reviews
- wellness: focus sessions, pomodoro, breaks, screen time, energy tracking, burnout prevention
- digest: RSS feeds, news digests, information filtering, reading lists, thread summarization
- language_tutor: language learning, vocabulary, grammar, pronunciation, conversation practice, quizzes
- live_trader: live broker trading (IBKR, TradeStation, Schwab), algo strategies, backtesting, AI trading decisions
- jira: ticket management, Jira, sprints, issues, kanban boards
- codebase_indexer: project indexing, architecture analysis, codebase understanding
- diagram: code visualization, call graphs, class diagrams, flowcharts, architecture diagrams
- meeting: meeting notes parsing, action item extraction, transcript processing
- work_pilot: autonomous work pipeline, start work on ticket, ticket-to-PR workflow

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

        # Fall back to simple word matching against INTENT_AGENT_MAP + PLUGIN_INTENTS
        from vera.brain.agents import PLUGIN_INTENTS

        combined_intents = {**INTENT_AGENT_MAP, **PLUGIN_INTENTS}

        words = re.findall(r"\b\w+\b", lower)
        scores: dict[str, int] = {}
        matched_intent: dict[str, str] = {}

        for word in words:
            if word in combined_intents:
                agent = combined_intents[word]
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
            "coder": ModelTier.SPECIALIST,
            "git": ModelTier.SPECIALIST,
            "browser": ModelTier.SPECIALIST,
            "content_creator": ModelTier.SPECIALIST,
            "finance": ModelTier.SPECIALIST,
            "live_trader": ModelTier.STRATEGIST,
            "job_hunter": ModelTier.SPECIALIST,
            "planner": ModelTier.SPECIALIST,
            "wellness": ModelTier.EXECUTOR,
            "language_tutor": ModelTier.EXECUTOR,
            "digest": ModelTier.SPECIALIST,
            "jira": ModelTier.SPECIALIST,
            "codebase_indexer": ModelTier.SPECIALIST,
            "meeting": ModelTier.SPECIALIST,
            "diagram": ModelTier.SPECIALIST,
            "work_pilot": ModelTier.STRATEGIST,
            "media_factory": ModelTier.SPECIALIST,
            "calendar": ModelTier.SPECIALIST,
            "music": ModelTier.EXECUTOR,
            "translation": ModelTier.SPECIALIST,
            "automation": ModelTier.SPECIALIST,
        }
        return tier_map.get(agent_name, ModelTier.EXECUTOR)
