"""Tests for all agents — registration, tools, offline responses."""

from __future__ import annotations


def test_agent_registry_has_all_agents():
    from voca.brain.agents import AGENT_REGISTRY
    expected = [
        "companion", "operator", "researcher", "writer",
        "life_manager", "home_controller", "income", "coder", "browser", "git",
    ]
    for name in expected:
        assert name in AGENT_REGISTRY, f"Agent '{name}' missing from registry"


def test_agent_registry_count():
    from voca.brain.agents import AGENT_REGISTRY
    assert len(AGENT_REGISTRY) >= 10


def test_all_agents_have_tools():
    from voca.brain.agents import AGENT_REGISTRY
    for name, agent in AGENT_REGISTRY.items():
        assert len(agent.tools) > 0, f"Agent '{name}' has no tools"


def test_all_agents_have_name():
    from voca.brain.agents import AGENT_REGISTRY
    for name, agent in AGENT_REGISTRY.items():
        assert agent.name == name, f"Agent name mismatch: {agent.name} != {name}"


def test_all_agents_have_description():
    from voca.brain.agents import AGENT_REGISTRY
    for name, agent in AGENT_REGISTRY.items():
        assert agent.description, f"Agent '{name}' has no description"


def test_all_agents_have_system_prompt():
    from voca.brain.agents import AGENT_REGISTRY
    for name, agent in AGENT_REGISTRY.items():
        assert agent.system_prompt, f"Agent '{name}' has no system prompt"


def test_all_tools_have_openai_schema():
    from voca.brain.agents import AGENT_REGISTRY
    for name, agent in AGENT_REGISTRY.items():
        for tool in agent.tools:
            schema = tool.to_openai_schema()
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "parameters" in schema["function"]


def test_companion_has_offline_responses():
    from voca.brain.agents import AGENT_REGISTRY
    companion = AGENT_REGISTRY["companion"]
    assert len(companion.offline_responses) > 0


def test_operator_tool_count():
    from voca.brain.agents import AGENT_REGISTRY
    operator = AGENT_REGISTRY["operator"]
    assert len(operator.tools) >= 8


def test_browser_tool_count():
    from voca.brain.agents import AGENT_REGISTRY
    browser = AGENT_REGISTRY["browser"]
    assert len(browser.tools) >= 11


def test_income_tool_count():
    from voca.brain.agents import AGENT_REGISTRY
    income = AGENT_REGISTRY["income"]
    assert len(income.tools) >= 14


def test_coder_tool_count():
    from voca.brain.agents import AGENT_REGISTRY
    coder = AGENT_REGISTRY["coder"]
    assert len(coder.tools) >= 5


def test_total_tool_count():
    from voca.brain.agents import AGENT_REGISTRY
    total = sum(len(agent.tools) for agent in AGENT_REGISTRY.values())
    assert total >= 70, f"Expected at least 70 tools, got {total}"


def test_git_agent_has_tools():
    from voca.brain.agents import AGENT_REGISTRY
    git = AGENT_REGISTRY["git"]
    assert len(git.tools) >= 9
    tool_names = [t.name for t in git.tools]
    assert "git_status" in tool_names
    assert "git_commit" in tool_names
    assert "code_review" in tool_names
