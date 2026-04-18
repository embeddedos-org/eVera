"""Agent registry — singleton access to all Voca agents + plugins."""

from __future__ import annotations

import logging

from voca.brain.agents.base import BaseAgent
from voca.brain.agents.browser import BrowserAgent
from voca.brain.agents.coder import CoderAgent
from voca.brain.agents.companion import CompanionAgent
from voca.brain.agents.git_agent import GitAgent
from voca.brain.agents.home_controller import HomeControllerAgent
from voca.brain.agents.income import IncomeAgent
from voca.brain.agents.life_manager import LifeManagerAgent
from voca.brain.agents.operator import OperatorAgent
from voca.brain.agents.researcher import ResearcherAgent
from voca.brain.agents.writer import WriterAgent

logger = logging.getLogger(__name__)

AGENT_REGISTRY: dict[str, BaseAgent] = {
    "life_manager": LifeManagerAgent(),
    "home_controller": HomeControllerAgent(),
    "researcher": ResearcherAgent(),
    "writer": WriterAgent(),
    "operator": OperatorAgent(),
    "income": IncomeAgent(),
    "companion": CompanionAgent(),
    "coder": CoderAgent(),
    "browser": BrowserAgent(),
    "git": GitAgent(),
}

# Load plugins
try:
    from voca.brain.plugins import get_plugin_manager
    _pm = get_plugin_manager()
    _plugin_agents = _pm.load_all()
    AGENT_REGISTRY.update(_plugin_agents)
    if _plugin_agents:
        logger.info("Loaded %d plugin agents: %s", len(_plugin_agents), list(_plugin_agents.keys()))
except Exception as e:
    logger.warning("Plugin loading failed: %s", e)

PLUGIN_INTENTS: dict[str, str] = {}
try:
    PLUGIN_INTENTS = _pm.get_intents()
except Exception:
    pass


def get_agent(name: str) -> BaseAgent | None:
    """Get an agent by name."""
    return AGENT_REGISTRY.get(name)


def list_agents() -> list[str]:
    """List all registered agent names."""
    return list(AGENT_REGISTRY.keys())


def reload_plugins() -> dict[str, BaseAgent]:
    """Reload all plugins and return new agents."""
    from voca.brain.plugins import get_plugin_manager
    pm = get_plugin_manager()
    new_agents = pm.load_all()
    AGENT_REGISTRY.update(new_agents)
    PLUGIN_INTENTS.update(pm.get_intents())
    return new_agents


__all__ = ["AGENT_REGISTRY", "PLUGIN_INTENTS", "get_agent", "list_agents", "reload_plugins", "BaseAgent"]
