"""Sanity Tests — quick smoke tests to verify the system is functional.

These run fast and catch obvious breakages.
"""

from __future__ import annotations


class TestSanityImports:
    """Every major module can be imported without crashing."""

    def test_import_core(self):
        from vera.core import VeraBrain

        assert VeraBrain is not None

    def test_import_app(self):
        from vera.app import create_app

        assert create_app is not None

    def test_import_all_agents(self):
        from vera.brain.agents import AGENT_REGISTRY

        assert len(AGENT_REGISTRY) >= 10

    def test_import_router(self):
        from vera.brain.router import TIER0_PATTERNS

        assert len(TIER0_PATTERNS) >= 8

    def test_import_memory(self):
        from vera.memory.vault import MemoryVault

        assert MemoryVault is not None

    def test_import_safety(self):
        from vera.safety.policy import PolicyService
        from vera.safety.privacy import PrivacyGuard

        assert PolicyService is not None
        assert PrivacyGuard is not None

    def test_import_scheduler(self):
        from vera.scheduler import ProactiveScheduler

        assert ProactiveScheduler is not None

    def test_import_rbac(self):
        from vera.rbac import RBACManager

        assert RBACManager is not None

    def test_import_crew(self):
        from vera.brain.crew import Crew

        assert Crew is not None

    def test_import_workflow(self):
        from vera.brain.workflow import WorkflowEngine

        assert WorkflowEngine is not None

    def test_import_plugins(self):
        from vera.brain.plugins import PluginManager

        assert PluginManager is not None

    def test_import_language(self):
        from vera.brain.language import correct_spelling

        assert correct_spelling is not None

    def test_import_messaging(self):
        from vera.messaging import broadcast_notification

        assert broadcast_notification is not None


class TestSanityAgents:
    """Every agent has the basics."""

    def test_every_agent_has_name(self):
        from vera.brain.agents import AGENT_REGISTRY

        for name, agent in AGENT_REGISTRY.items():
            assert agent.name == name
            assert agent.description
            assert agent.system_prompt

    def test_every_agent_has_tools(self):
        from vera.brain.agents import AGENT_REGISTRY

        for name, agent in AGENT_REGISTRY.items():
            assert len(agent.tools) > 0, f"{name} has no tools"

    def test_every_tool_has_schema(self):
        from vera.brain.agents import AGENT_REGISTRY

        for name, agent in AGENT_REGISTRY.items():
            for tool in agent.tools:
                schema = tool.to_openai_schema()
                assert schema["type"] == "function"
                assert "name" in schema["function"]

    def test_every_agent_has_offline_fallback(self):
        from vera.brain.agents import AGENT_REGISTRY

        for name, agent in AGENT_REGISTRY.items():
            # git agent uses base offline — acceptable
            assert len(agent.offline_responses) > 0 or name == "git"


class TestSanityRouter:
    """Router correctly classifies basic intents."""

    def test_time_is_tier0(self):
        from vera.brain.router import TIER0_PATTERNS

        text = "what time is it"
        matched = False
        for pattern, agent, intent, template in TIER0_PATTERNS:
            if pattern.search(text):
                assert intent == "get_time"
                matched = True
                break
        assert matched

    def test_greeting_detected(self):
        from vera.brain.router import TIER0_PATTERNS

        text = "hello"
        matched = False
        for pattern, agent, intent, template in TIER0_PATTERNS:
            if pattern.search(text):
                assert intent == "greeting"
                matched = True
                break
        assert matched

    def test_help_detected(self):
        from vera.brain.router import TIER0_PATTERNS

        text = "what can you do"
        matched = False
        for pattern, agent, intent, template in TIER0_PATTERNS:
            if pattern.search(text):
                assert intent == "help"
                matched = True
                break
        assert matched


class TestSanityMemory:
    """Memory system basic operations work."""

    def test_semantic_memory_roundtrip(self):
        import tempfile

        from vera.memory.semantic import SemanticMemory

        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path

            mem = SemanticMemory(store_path=Path(tmp) / "test.json")
            mem.remember("user_name", "TestUser")
            assert mem.recall("user_name") == "TestUser"

    def test_working_memory_add_and_get(self):
        from vera.memory.working import WorkingMemory

        wm = WorkingMemory(max_turns=5)
        wm.add("user", "hello")
        wm.add("assistant", "hi there")
        ctx = wm.get_context()
        assert len(ctx) == 2

    def test_working_memory_max_turns(self):
        from vera.memory.working import WorkingMemory

        wm = WorkingMemory(max_turns=3)
        for i in range(10):
            wm.add("user", f"msg {i}")
        ctx = wm.get_context()
        assert len(ctx) <= 6  # 3 turns = 6 messages max
