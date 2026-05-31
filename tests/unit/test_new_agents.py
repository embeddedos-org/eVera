"""Tests for LocalAgent, WWWAgent, system info endpoint, and model registry."""
import pathlib
import pytest
from unittest.mock import patch, MagicMock


class TestLocalAgent:
    """Tests for the LOCAL mode offline intelligence agent."""

    def test_local_agent_import(self):
        from vera.brain.agents.local_agent import LocalAgent
        agent = LocalAgent()
        assert agent is not None

    def test_local_agent_has_tools(self):
        from vera.brain.agents.local_agent import LocalAgent
        agent = LocalAgent()
        assert hasattr(agent, 'tools')
        assert len(agent.tools) > 0

    def test_local_agent_description(self):
        from vera.brain.agents.local_agent import LocalAgent
        agent = LocalAgent()
        assert agent.description
        assert len(agent.description) > 10

    def test_local_agent_offline_tools_present(self):
        from vera.brain.agents.local_agent import LocalAgent
        agent = LocalAgent()
        tool_names = [t.name for t in agent.tools]
        # Should have at least offline code execution and file search
        assert any('code' in n or 'exec' in n or 'run' in n or 'file' in n for n in tool_names), \
            f"No code execution or file tool found in: {tool_names}"

    def test_local_agent_tier_is_model_tier(self):
        from vera.brain.agents.local_agent import LocalAgent
        from vera.providers.models import ModelTier
        agent = LocalAgent()
        assert isinstance(agent.tier, ModelTier)

    def test_local_agent_in_registry(self):
        from vera.brain.agents import AGENT_REGISTRY
        assert 'local' in AGENT_REGISTRY

    def test_local_agent_tools_have_names(self):
        from vera.brain.agents.local_agent import LocalAgent
        agent = LocalAgent()
        for tool in agent.tools:
            assert hasattr(tool, 'name'), f"Tool missing name: {tool}"
            assert tool.name, f"Tool has empty name: {tool}"

    def test_local_agent_tools_have_descriptions(self):
        from vera.brain.agents.local_agent import LocalAgent
        agent = LocalAgent()
        for tool in agent.tools:
            assert hasattr(tool, 'description'), f"Tool missing description: {tool.name}"


class TestWWWAgent:
    """Tests for the WWW mode internet intelligence agent."""

    def test_www_agent_import(self):
        from vera.brain.agents.www_agent import WWWAgent
        agent = WWWAgent()
        assert agent is not None

    def test_www_agent_has_tools(self):
        from vera.brain.agents.www_agent import WWWAgent
        agent = WWWAgent()
        assert hasattr(agent, 'tools')
        assert len(agent.tools) > 0

    def test_www_agent_description(self):
        from vera.brain.agents.www_agent import WWWAgent
        agent = WWWAgent()
        assert agent.description
        assert len(agent.description) > 10

    def test_www_agent_has_web_search_tool(self):
        from vera.brain.agents.www_agent import WWWAgent
        agent = WWWAgent()
        tool_names = [t.name for t in agent.tools]
        assert any('search' in n or 'web' in n or 'news' in n for n in tool_names), \
            f"No web search tool found in: {tool_names}"

    def test_www_agent_has_stock_tool(self):
        from vera.brain.agents.www_agent import WWWAgent
        agent = WWWAgent()
        tool_names = [t.name for t in agent.tools]
        assert any('stock' in n or 'finance' in n or 'market' in n for n in tool_names), \
            f"No stock/finance tool found in: {tool_names}"

    def test_www_agent_in_registry(self):
        from vera.brain.agents import AGENT_REGISTRY
        assert 'www' in AGENT_REGISTRY

    def test_www_agent_tier_is_model_tier(self):
        from vera.brain.agents.www_agent import WWWAgent
        from vera.providers.models import ModelTier
        agent = WWWAgent()
        assert isinstance(agent.tier, ModelTier)

    def test_www_agent_tools_have_names(self):
        from vera.brain.agents.www_agent import WWWAgent
        agent = WWWAgent()
        for tool in agent.tools:
            assert hasattr(tool, 'name'), f"Tool missing name: {tool}"
            assert tool.name, f"Tool has empty name: {tool}"


class TestSystemInfoEndpoint:
    """Tests for the /api/system/info endpoint."""

    def test_system_info_in_app(self):
        """Verify the endpoint is registered in app.py."""
        app_src = pathlib.Path('vera/app.py').read_text()
        assert '/api/system/info' in app_src

    def test_system_info_uses_psutil(self):
        """Verify psutil is used for system metrics in app.py."""
        app_src = pathlib.Path('vera/app.py').read_text()
        assert 'psutil' in app_src

    def test_psutil_available(self):
        """psutil must be importable for the endpoint to work."""
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        assert isinstance(cpu, float)
        assert 0 <= cpu <= 100

    def test_psutil_memory(self):
        import psutil
        mem = psutil.virtual_memory()
        assert mem.total > 0
        assert 0 <= mem.percent <= 100

    def test_psutil_disk(self):
        import psutil
        disk = psutil.disk_usage('/')
        assert disk.total > 0
        assert 0 <= disk.percent <= 100


class TestModelRegistry:
    """Tests for the expanded 130+ model registry."""

    def test_model_registry_has_many_models(self):
        from vera.providers.models import ALL_MODELS
        assert len(ALL_MODELS) >= 60, f"Expected 60+ models, got {len(ALL_MODELS)}"

    def test_ollama_models_present(self):
        from vera.providers.models import ALL_MODELS
        ollama_models = [m for m in ALL_MODELS if m.provider == 'ollama']
        assert len(ollama_models) >= 20, f"Expected 20+ Ollama models, got {len(ollama_models)}"

    def test_llama_family_present(self):
        from vera.providers.models import ALL_MODELS
        llama = [m for m in ALL_MODELS if 'llama' in m.id.lower()]
        assert len(llama) >= 3, f"Expected 3+ Llama models, got {len(llama)}"

    def test_qwen_family_present(self):
        from vera.providers.models import ALL_MODELS
        qwen = [m for m in ALL_MODELS if 'qwen' in m.id.lower()]
        assert len(qwen) >= 2, f"Expected 2+ Qwen models, got {len(qwen)}"

    def test_deepseek_family_present(self):
        from vera.providers.models import ALL_MODELS
        ds = [m for m in ALL_MODELS if 'deepseek' in m.id.lower()]
        assert len(ds) >= 2, f"Expected 2+ DeepSeek models, got {len(ds)}"

    def test_embedding_models_present(self):
        from vera.providers.models import ALL_MODELS
        embed = [m for m in ALL_MODELS if 'embed' in m.id.lower() or 'embed' in (m.description or '').lower()]
        assert len(embed) >= 1, f"Expected at least 1 embedding model, got {len(embed)}"

    def test_all_models_have_required_fields(self):
        from vera.providers.models import ALL_MODELS
        for m in ALL_MODELS:
            assert m.id, f"Model missing id: {m}"
            assert m.provider, f"Model missing provider: {m.id}"

    def test_openai_models_present(self):
        from vera.providers.models import ALL_MODELS
        openai = [m for m in ALL_MODELS if m.provider == 'openai']
        assert len(openai) >= 2, f"Expected 2+ OpenAI models, got {len(openai)}"

    def test_anthropic_models_present(self):
        from vera.providers.models import ALL_MODELS
        claude = [m for m in ALL_MODELS if m.provider == 'anthropic']
        assert len(claude) >= 2, f"Expected 2+ Anthropic models, got {len(claude)}"

    def test_model_tier_backward_compat(self):
        """STRATEGIST and ARCHITECT tiers must exist for backward compat."""
        from vera.providers.models import ModelTier
        assert hasattr(ModelTier, 'STRATEGIST')
        assert hasattr(ModelTier, 'ARCHITECT')

    def test_offline_models_list(self):
        """OFFLINE_MODELS should contain only offline=True models."""
        from vera.providers.models import OFFLINE_MODELS
        assert len(OFFLINE_MODELS) >= 20
        for m in OFFLINE_MODELS:
            assert m.offline is True, f"Non-offline model in OFFLINE_MODELS: {m.id}"


class TestAgentRegistry:
    """Tests for the full agent registry with new agents."""

    def test_registry_has_40_plus_agents(self):
        from vera.brain.agents import AGENT_REGISTRY
        assert len(AGENT_REGISTRY) >= 40, f"Expected 40+ agents, got {len(AGENT_REGISTRY)}"

    def test_all_three_mode_agents_registered(self):
        from vera.brain.agents import AGENT_REGISTRY
        assert 'local' in AGENT_REGISTRY, "LocalAgent not registered"
        assert 'lan' in AGENT_REGISTRY, "LANAgent not registered"
        assert 'www' in AGENT_REGISTRY, "WWWAgent not registered"

    def test_computer_use_agent_registered(self):
        from vera.brain.agents import AGENT_REGISTRY
        assert 'computer_use' in AGENT_REGISTRY

    def test_all_agents_have_description(self):
        from vera.brain.agents import AGENT_REGISTRY
        for name, agent in AGENT_REGISTRY.items():
            assert hasattr(agent, 'description'), f"Agent {name} missing description"
            assert agent.description, f"Agent {name} has empty description"

    def test_all_agents_have_tier(self):
        from vera.brain.agents import AGENT_REGISTRY
        for name, agent in AGENT_REGISTRY.items():
            assert hasattr(agent, 'tier'), f"Agent {name} missing tier"

    def test_all_agents_have_tools(self):
        from vera.brain.agents import AGENT_REGISTRY
        for name, agent in AGENT_REGISTRY.items():
            assert hasattr(agent, 'tools'), f"Agent {name} missing tools attribute"
