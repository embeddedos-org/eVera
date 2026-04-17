"""Agent registry — singleton access to all Voca agents."""

from __future__ import annotations

from voca.brain.agents.base import BaseAgent
from voca.brain.agents.browser import BrowserAgent
from voca.brain.agents.coder import CoderAgent
from voca.brain.agents.companion import CompanionAgent
from voca.brain.agents.home_controller import HomeControllerAgent
from voca.brain.agents.income import IncomeAgent
from voca.brain.agents.life_manager import LifeManagerAgent
from voca.brain.agents.operator import OperatorAgent
from voca.brain.agents.researcher import ResearcherAgent
from voca.brain.agents.writer import WriterAgent

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
}


def get_agent(name: str) -> BaseAgent | None:
    """Get an agent by name."""
    return AGENT_REGISTRY.get(name)


def list_agents() -> list[str]:
    """List all registered agent names."""
    return list(AGENT_REGISTRY.keys())


__all__ = ["AGENT_REGISTRY", "get_agent", "list_agents", "BaseAgent"]
