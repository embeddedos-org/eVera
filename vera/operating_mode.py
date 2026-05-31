"""eVera Operating Mode System.

Three distinct operating modes that control which agents, providers, and
capabilities are available:

  LOCAL — Fully offline. No internet. Controls your computer, talks to you,
          helps with tasks using only Ollama models. Zero data leaves the machine.

  LAN   — Local network access. Can reach other computers on the same network,
          SSH into machines, access shared files, query org databases.
          Still uses Ollama as primary LLM. No public internet required.

  WWW   — Full internet access. All 39 agents active. Cloud LLMs available
          (OpenAI, Claude, Gemini, Groq, etc.). Web search, stock data,
          social media, travel booking, and all external APIs.

Mode is set via:
  - Environment variable: VERA_OPERATING_MODE=local|lan|www
  - API endpoint: POST /mode  {"mode": "lan"}
  - UI mode selector in the header
"""
from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class OperatingMode(str, Enum):
    """eVera operating mode — controls agent availability and provider access."""
    LOCAL = "local"
    LAN = "lan"
    WWW = "www"


# Human-readable descriptions for each mode
MODE_DESCRIPTIONS: dict[OperatingMode, dict[str, Any]] = {
    OperatingMode.LOCAL: {
        "label": "LOCAL",
        "icon": "🖥️",
        "color": "#4ade80",  # green
        "description": "Fully offline — computer control, conversation, local tasks. No internet.",
        "llm": "Ollama only (offline)",
        "internet": False,
        "lan_access": False,
        "agents_available": [
            "companion", "computer_use", "coder", "writer", "planner",
            "life_manager", "wellness", "calendar", "diagram", "data_analyst",
            "language_tutor", "music", "operator", "pdf", "spreadsheet",
            "translation", "education", "git",
        ],
        "agents_blocked": [
            "browser", "researcher", "finance", "income", "shopping",
            "travel", "social_media", "content_creator", "digest",
            "cybersecurity", "devops", "network", "api", "database",
            "meeting", "home_controller", "brokers", "presentation",
            "threed", "automation",
        ],
    },
    OperatingMode.LAN: {
        "label": "LAN",
        "icon": "🌐",
        "color": "#60a5fa",  # blue
        "description": "Local network — access other computers, SSH, shared files, org data.",
        "llm": "Ollama primary + LAN-hosted models",
        "internet": False,
        "lan_access": True,
        "agents_available": [
            "companion", "computer_use", "coder", "writer", "planner",
            "life_manager", "wellness", "calendar", "diagram", "data_analyst",
            "language_tutor", "music", "operator", "pdf", "spreadsheet",
            "translation", "education", "git", "network", "devops",
            "database", "automation", "cybersecurity",
        ],
        "agents_blocked": [
            "browser", "researcher", "finance", "income", "shopping",
            "travel", "social_media", "content_creator", "digest",
            "api", "meeting", "home_controller", "brokers",
            "presentation", "threed",
        ],
    },
    OperatingMode.WWW: {
        "label": "WWW",
        "icon": "🌍",
        "color": "#f59e0b",  # amber
        "description": "Full internet — all 39 agents, cloud LLMs, web search, APIs.",
        "llm": "All providers (Ollama + OpenAI + Claude + Gemini + Groq + ...)",
        "internet": True,
        "lan_access": True,
        "agents_available": None,  # None = all agents available
        "agents_blocked": [],
    },
}


class ModeManager:
    """Singleton that tracks and enforces the current operating mode."""

    _instance: ModeManager | None = None

    def __new__(cls) -> ModeManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        # Load from environment or default to LOCAL (safest)
        env_mode = os.environ.get("VERA_OPERATING_MODE", "local").lower()
        try:
            self._mode = OperatingMode(env_mode)
        except ValueError:
            logger.warning("Invalid VERA_OPERATING_MODE=%r, defaulting to LOCAL", env_mode)
            self._mode = OperatingMode.LOCAL
        logger.info("eVera operating mode: %s", self._mode.value.upper())

    @property
    def mode(self) -> OperatingMode:
        return self._mode

    def set_mode(self, mode: OperatingMode | str) -> None:
        """Change the operating mode at runtime."""
        if isinstance(mode, str):
            mode = OperatingMode(mode.lower())
        old = self._mode
        self._mode = mode
        logger.info("Operating mode changed: %s → %s", old.value.upper(), mode.value.upper())

    def is_agent_available(self, agent_name: str) -> bool:
        """Check if an agent is available in the current mode."""
        info = MODE_DESCRIPTIONS[self._mode]
        available = info["agents_available"]
        blocked = info["agents_blocked"]
        if available is None:
            return True  # WWW mode: all agents available
        return agent_name in available and agent_name not in blocked

    def is_internet_available(self) -> bool:
        return MODE_DESCRIPTIONS[self._mode]["internet"]

    def is_lan_available(self) -> bool:
        return MODE_DESCRIPTIONS[self._mode]["lan_access"]

    def get_allowed_providers(self) -> list[str]:
        """Return the list of LLM providers allowed in the current mode."""
        from vera.providers.models import ZONE_PROVIDER_POLICY
        return ZONE_PROVIDER_POLICY.get(self._mode.value, ["ollama"])

    def get_status(self) -> dict[str, Any]:
        """Return full mode status for the /mode endpoint."""
        info = MODE_DESCRIPTIONS[self._mode]
        return {
            "mode": self._mode.value,
            "label": info["label"],
            "icon": info["icon"],
            "color": info["color"],
            "description": info["description"],
            "llm": info["llm"],
            "internet": info["internet"],
            "lan_access": info["lan_access"],
            "agents_available": info["agents_available"],
            "agents_blocked": info["agents_blocked"],
        }

    def get_offline_message(self, agent_name: str) -> str:
        """Return a helpful message when an agent is blocked in current mode."""
        mode = self._mode
        if mode == OperatingMode.LOCAL:
            return (
                f"The {agent_name} agent requires internet access and is not available in LOCAL mode. "
                f"Switch to LAN or WWW mode to use it. "
                f"In LOCAL mode, I can help you with: computer control, coding, writing, planning, "
                f"music, data analysis, and conversation — all 100% offline."
            )
        elif mode == OperatingMode.LAN:
            return (
                f"The {agent_name} agent requires public internet and is not available in LAN mode. "
                f"Switch to WWW mode to use it."
            )
        return f"The {agent_name} agent is not available in {mode.value.upper()} mode."


# Global singleton
mode_manager = ModeManager()
