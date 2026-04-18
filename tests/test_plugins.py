"""Tests for plugin system — discovery, loading, registration."""

from __future__ import annotations

import pytest


@pytest.fixture
def plugin_dir(tmp_path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    return plugins


def test_discover_empty(plugin_dir):
    from voca.brain.plugins import PluginManager
    pm = PluginManager(plugins_dir=plugin_dir)
    result = pm.discover()
    assert isinstance(result, list)


def test_load_plugin(plugin_dir):
    # Create a test plugin
    plugin_file = plugin_dir / "test_plugin.py"
    plugin_file.write_text('''
from voca.brain.agents.base import BaseAgent, Tool
from voca.providers.models import ModelTier

class TestTool(Tool):
    def __init__(self):
        super().__init__(name="test_tool", description="Test", parameters={})
    async def execute(self, **kwargs):
        return {"status": "success"}

class TestPluginAgent(BaseAgent):
    name = "test_plugin"
    description = "Test plugin agent"
    tier = ModelTier.EXECUTOR
    system_prompt = "Test"
    def _setup_tools(self):
        self._tools = [TestTool()]

PLUGIN_AGENTS = [TestPluginAgent]
PLUGIN_INTENTS = {"test_intent": "test_plugin"}
''')

    from voca.brain.plugins import PluginManager
    pm = PluginManager(plugins_dir=plugin_dir)
    agents = pm.load_all()

    assert "test_plugin" in agents
    assert len(agents["test_plugin"].tools) == 1
    assert pm.get_intents()["test_intent"] == "test_plugin"


def test_skip_underscore_files(plugin_dir):
    (plugin_dir / "_private.py").write_text("# skip me")
    (plugin_dir / "__init__.py").write_text("")

    from voca.brain.plugins import PluginManager
    pm = PluginManager(plugins_dir=plugin_dir)
    result = pm.discover()
    assert len(result) == 0


def test_example_plugin_created(tmp_path):
    empty_dir = tmp_path / "new_plugins"
    from voca.brain.plugins import PluginManager
    pm = PluginManager(plugins_dir=empty_dir)
    pm.discover()
    assert (empty_dir / "_example_plugin.py").exists()
