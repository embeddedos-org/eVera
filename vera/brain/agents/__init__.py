"""Agent registry — singleton access to all Vera agents + plugins."""

from __future__ import annotations

import logging

from vera.brain.agents.base import BaseAgent
from vera.brain.agents.browser import BrowserAgent
from vera.brain.agents.codebase_indexer import CodebaseIndexerAgent
from vera.brain.agents.coder import CoderAgent
from vera.brain.agents.companion import CompanionAgent
from vera.brain.agents.content_creator import ContentCreatorAgent
from vera.brain.agents.diagram_agent import DiagramAgent
from vera.brain.agents.digest import DigestAgent
from vera.brain.agents.finance import FinanceAgent
from vera.brain.agents.git_agent import GitAgent
from vera.brain.agents.home_controller import HomeControllerAgent
from vera.brain.agents.income import IncomeAgent
from vera.brain.agents.language_tutor import LanguageTutorAgent
from vera.brain.agents.life_manager import LifeManagerAgent
from vera.brain.agents.meeting_agent import MeetingAgent
from vera.brain.agents.operator import OperatorAgent
from vera.brain.agents.planner import PlannerAgent
from vera.brain.agents.researcher import ResearcherAgent
from vera.brain.agents.wellness import WellnessAgent
from vera.brain.agents.writer import WriterAgent

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
    "content_creator": ContentCreatorAgent(),
    "finance": FinanceAgent(),
    "planner": PlannerAgent(),
    "wellness": WellnessAgent(),
    "digest": DigestAgent(),
    "language_tutor": LanguageTutorAgent(),
    "codebase_indexer": CodebaseIndexerAgent(),
    "meeting": MeetingAgent(),
    "diagram": DiagramAgent(),
}

# Conditionally register mobile controller
from config import settings as _settings  # noqa: E402

if _settings.mobile.control_enabled:
    from vera.brain.agents.mobile import MobileControlAgent

    AGENT_REGISTRY["mobile_controller"] = MobileControlAgent()

# Conditionally register job hunter
if _settings.job_hunter.enabled:
    from vera.brain.agents.job_hunter import JobHunterAgent

    AGENT_REGISTRY["job_hunter"] = JobHunterAgent()

# Conditionally register jira agent
if _settings.jira.enabled:
    from vera.brain.agents.jira_agent import JiraAgent

    AGENT_REGISTRY["jira"] = JiraAgent()

    # Work pilot depends on jira
    from vera.brain.agents.work_pilot import WorkPilotAgent

    AGENT_REGISTRY["work_pilot"] = WorkPilotAgent()

# Load plugins
try:
    from vera.brain.plugins import get_plugin_manager

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
except Exception as e:
    logger.warning("Failed to load plugin intents: %s", e)


def get_agent(name: str) -> BaseAgent | None:
    """Get an agent by name."""
    return AGENT_REGISTRY.get(name)


def list_agents() -> list[str]:
    """List all registered agent names."""
    return list(AGENT_REGISTRY.keys())


def reload_plugins() -> dict[str, BaseAgent]:
    """Reload all plugins and return new agents."""
    from vera.brain.plugins import get_plugin_manager

    pm = get_plugin_manager()
    new_agents = pm.load_all()
    AGENT_REGISTRY.update(new_agents)
    PLUGIN_INTENTS.update(pm.get_intents())
    return new_agents


__all__ = ["AGENT_REGISTRY", "PLUGIN_INTENTS", "get_agent", "list_agents", "reload_plugins", "BaseAgent"]
