"""Plugin system — auto-discovery, loading, and registration of custom agents and tools.

Drop a Python file in the `plugins/` directory and Vera auto-loads it.

Plugin file format:
```python
# plugins/my_agent.py
from vera.brain.agents.base import BaseAgent, Tool

class MyTool(Tool):
    def __init__(self):
        super().__init__(name="my_tool", description="Does something", parameters={})
    async def execute(self, **kwargs):
        return {"status": "success", "data": "hello"}

class MyAgent(BaseAgent):
    name = "my_agent"
    description = "My custom agent"
    tier = 2
    system_prompt = "You are a custom agent."
    def _setup_tools(self):
        self._tools = [MyTool()]

# Required: tells the plugin loader what to register
PLUGIN_AGENTS = [MyAgent]
PLUGIN_INTENTS = {"my_intent": "my_agent", "custom": "my_agent"}
```
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PLUGINS_DIR = Path(__file__).resolve().parent.parent.parent / "plugins"


class PluginManager:
    """Discovers, loads, and manages plugins."""

    def __init__(self, plugins_dir: Path | None = None) -> None:
        self._plugins_dir = plugins_dir or PLUGINS_DIR
        self._loaded: dict[str, Any] = {}
        self._agents: dict[str, Any] = {}
        self._intents: dict[str, str] = {}

    def discover(self) -> list[str]:
        """Find all plugin files in the plugins directory."""
        if not self._plugins_dir.exists():
            self._plugins_dir.mkdir(parents=True, exist_ok=True)
            # Create example plugin
            self._create_example_plugin()
            return []

        plugins = []
        for path in self._plugins_dir.glob("*.py"):
            if path.name.startswith("_"):
                continue
            plugins.append(path.stem)

        logger.info("Discovered %d plugins in %s", len(plugins), self._plugins_dir)
        return plugins

    def load_all(self) -> dict[str, Any]:
        """Load all discovered plugins and return registered agents."""
        plugin_names = self.discover()

        for name in plugin_names:
            try:
                self._load_plugin(name)
            except Exception as e:
                logger.error("Failed to load plugin '%s': %s", name, e)

        logger.info(
            "Loaded %d plugins, %d agents, %d intents",
            len(self._loaded),
            len(self._agents),
            len(self._intents),
        )
        return self._agents

    def _load_plugin(self, name: str) -> None:
        """Load a single plugin by name."""
        plugin_path = self._plugins_dir / f"{name}.py"
        if not plugin_path.exists():
            raise FileNotFoundError(f"Plugin not found: {plugin_path}")

        # Dynamic import
        spec = importlib.util.spec_from_file_location(
            f"vera_plugin_{name}",
            str(plugin_path),
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load plugin: {name}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[f"vera_plugin_{name}"] = module
        spec.loader.exec_module(module)

        self._loaded[name] = module

        # Register agents
        if hasattr(module, "PLUGIN_AGENTS"):
            for agent_cls in module.PLUGIN_AGENTS:
                try:
                    agent = agent_cls()
                    self._agents[agent.name] = agent
                    logger.info(
                        "Plugin '%s' registered agent: %s (%d tools)",
                        name,
                        agent.name,
                        len(agent.tools),
                    )
                except Exception as e:
                    logger.error(
                        "Plugin '%s' failed to instantiate agent %s: %s",
                        name,
                        agent_cls.__name__,
                        e,
                    )

        # Register intents
        if hasattr(module, "PLUGIN_INTENTS"):
            self._intents.update(module.PLUGIN_INTENTS)

    def get_agents(self) -> dict[str, Any]:
        """Get all plugin-registered agents."""
        return self._agents

    def get_intents(self) -> dict[str, str]:
        """Get all plugin-registered intent → agent mappings."""
        return self._intents

    def reload_plugin(self, name: str) -> None:
        """Hot-reload a specific plugin."""
        # Remove old registrations
        if name in self._loaded:
            module = self._loaded[name]
            if hasattr(module, "PLUGIN_AGENTS"):
                for agent_cls in module.PLUGIN_AGENTS:
                    try:
                        agent = agent_cls()
                        self._agents.pop(agent.name, None)
                    except Exception:
                        pass
            if hasattr(module, "PLUGIN_INTENTS"):
                for intent in module.PLUGIN_INTENTS:
                    self._intents.pop(intent, None)
            del self._loaded[name]

        # Reload
        self._load_plugin(name)
        logger.info("Reloaded plugin: %s", name)

    def _create_example_plugin(self) -> None:
        """Create an example plugin file for reference."""
        example = self._plugins_dir / "_example_plugin.py"
        example.write_text(
            '''"""Example Vera plugin -- rename this file (remove underscore) to activate."""

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier


class HelloTool(Tool):
    """Example tool that says hello."""

    def __init__(self):
        super().__init__(
            name="say_hello",
            description="Say hello to someone",
            parameters={"name": {"type": "str", "description": "Name to greet"}},
        )

    async def execute(self, **kwargs):
        name = kwargs.get("name", "World")
        return {"status": "success", "message": f"Hello, {name}!"}


class ExampleAgent(BaseAgent):
    """Example custom agent."""

    name = "example"
    description = "An example plugin agent"
    tier = ModelTier.EXECUTOR
    system_prompt = "You are an example agent. Use say_hello to greet people."

    offline_responses = {
        "greet": "Hello from the example plugin!",
    }

    def _setup_tools(self):
        self._tools = [HelloTool()]


# Required: tells the plugin loader what to register
PLUGIN_AGENTS = [ExampleAgent]
PLUGIN_INTENTS = {"greet": "example", "hello_plugin": "example"}
''',
            encoding="utf-8",
        )
        logger.info("Created example plugin at %s", example)


# Singleton
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get or create the singleton PluginManager."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager
