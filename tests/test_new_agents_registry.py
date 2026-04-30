"""Integration tests for new power agents — registration, structure, tool schemas.

Tests all 20 new agents for proper registration, tool counts, descriptions,
system prompts, offline responses, and OpenAI function-calling schema generation.
"""

from __future__ import annotations

import pytest


# ============================================================
# Registry & Registration
# ============================================================

class TestNewAgentRegistry:
    """Verify all 20 new agents are in the registry."""

    NEW_AGENTS = [
        "music", "data_analyst", "computer_use", "devops", "cybersecurity",
        "travel", "shopping", "social_media", "education", "database",
        "translation", "presentation", "automation", "calendar", "network",
        "pdf", "spreadsheet", "api", "threed",
    ]

    def test_all_new_agents_registered(self):
        from vera.brain.agents import AGENT_REGISTRY

        for name in self.NEW_AGENTS:
            assert name in AGENT_REGISTRY, f"Agent '{name}' missing from AGENT_REGISTRY"

    def test_registry_has_at_least_38_agents(self):
        """19 original + 19 new = 38 minimum."""
        from vera.brain.agents import AGENT_REGISTRY

        assert len(AGENT_REGISTRY) >= 38, f"Expected >= 38 agents, got {len(AGENT_REGISTRY)}"

    def test_total_tool_count_exceeds_250(self):
        from vera.brain.agents import AGENT_REGISTRY

        total = sum(len(agent.tools) for agent in AGENT_REGISTRY.values())
        assert total >= 250, f"Expected >= 250 tools, got {total}"

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_agent_has_name(self, agent_name):
        from vera.brain.agents import AGENT_REGISTRY

        agent = AGENT_REGISTRY[agent_name]
        assert agent.name == agent_name

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_agent_has_description(self, agent_name):
        from vera.brain.agents import AGENT_REGISTRY

        agent = AGENT_REGISTRY[agent_name]
        assert agent.description, f"Agent '{agent_name}' has no description"
        assert len(agent.description) > 10

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_agent_has_system_prompt(self, agent_name):
        from vera.brain.agents import AGENT_REGISTRY

        agent = AGENT_REGISTRY[agent_name]
        assert agent.system_prompt, f"Agent '{agent_name}' has no system prompt"

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_agent_has_tools(self, agent_name):
        from vera.brain.agents import AGENT_REGISTRY

        agent = AGENT_REGISTRY[agent_name]
        assert len(agent.tools) >= 3, f"Agent '{agent_name}' has < 3 tools ({len(agent.tools)})"

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_agent_has_offline_responses(self, agent_name):
        from vera.brain.agents import AGENT_REGISTRY

        agent = AGENT_REGISTRY[agent_name]
        assert len(agent.offline_responses) > 0, f"Agent '{agent_name}' has no offline responses"

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_agent_has_tier(self, agent_name):
        from vera.brain.agents import AGENT_REGISTRY
        from vera.providers.models import ModelTier

        agent = AGENT_REGISTRY[agent_name]
        assert isinstance(agent.tier, ModelTier)


# ============================================================
# Tool Counts Per Agent
# ============================================================

class TestNewAgentToolCounts:
    """Verify each new agent has the expected number of tools."""

    EXPECTED_TOOL_COUNTS = {
        "music": 7,
        "data_analyst": 7,
        "computer_use": 8,
        "devops": 8,
        "cybersecurity": 7,
        "travel": 6,
        "shopping": 5,
        "social_media": 5,
        "education": 5,
        "database": 5,
        "translation": 3,
        "presentation": 3,
        "automation": 5,
        "calendar": 4,
        "network": 5,
        "pdf": 5,
        "spreadsheet": 4,
        "api": 4,
        "threed": 4,
    }

    @pytest.mark.parametrize("agent_name,expected_count", EXPECTED_TOOL_COUNTS.items())
    def test_tool_count(self, agent_name, expected_count):
        from vera.brain.agents import AGENT_REGISTRY

        agent = AGENT_REGISTRY[agent_name]
        actual = len(agent.tools)
        assert actual == expected_count, (
            f"Agent '{agent_name}' has {actual} tools, expected {expected_count}"
        )


# ============================================================
# OpenAI Function-Calling Schema
# ============================================================

class TestToolSchemas:
    """Verify all new agent tools produce valid OpenAI function-calling schemas."""

    NEW_AGENTS = [
        "music", "data_analyst", "computer_use", "devops", "cybersecurity",
        "travel", "shopping", "social_media", "education", "database",
        "translation", "presentation", "automation", "calendar", "network",
        "pdf", "spreadsheet", "api", "threed",
    ]

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_all_tools_have_valid_schema(self, agent_name):
        from vera.brain.agents import AGENT_REGISTRY

        agent = AGENT_REGISTRY[agent_name]
        for tool in agent.tools:
            schema = tool.to_openai_schema()
            assert schema["type"] == "function", f"Tool {tool.name} schema type != function"
            assert "function" in schema, f"Tool {tool.name} missing 'function' key"
            func = schema["function"]
            assert "name" in func, f"Tool {tool.name} missing function name"
            assert "parameters" in func, f"Tool {tool.name} missing parameters"
            assert func["name"] == tool.name, f"Tool name mismatch: {func['name']} != {tool.name}"

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_tool_names_unique(self, agent_name):
        from vera.brain.agents import AGENT_REGISTRY

        agent = AGENT_REGISTRY[agent_name]
        names = [t.name for t in agent.tools]
        assert len(names) == len(set(names)), f"Agent '{agent_name}' has duplicate tool names: {names}"

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_tool_descriptions_non_empty(self, agent_name):
        from vera.brain.agents import AGENT_REGISTRY

        agent = AGENT_REGISTRY[agent_name]
        for tool in agent.tools:
            assert tool.description, f"Tool '{tool.name}' in '{agent_name}' has no description"


# ============================================================
# Tool Name Verification
# ============================================================

class TestNewAgentToolNames:
    """Verify specific tool names are registered for each new agent."""

    def test_music_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["music"].tools]
        assert "spotify_control" in names
        assert "youtube_music" in names
        assert "lyrics_lookup" in names
        assert "mood_playlist" in names
        assert "podcast_discovery" in names
        assert "audio_analysis" in names
        assert "dj_mix" in names

    def test_data_analyst_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["data_analyst"].tools]
        assert "load_data" in names
        assert "analyze_data" in names
        assert "visualize_data" in names
        assert "clean_data" in names
        assert "train_model" in names
        assert "pivot_table" in names
        assert "sql_query" in names

    def test_computer_use_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["computer_use"].tools]
        assert "take_screenshot" in names
        assert "mouse_control" in names
        assert "keyboard_control" in names
        assert "ocr_extract" in names
        assert "clipboard" in names
        assert "find_on_screen" in names
        assert "window_manager" in names
        assert "app_launcher" in names

    def test_devops_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["devops"].tools]
        assert "docker_manage" in names
        assert "kubectl" in names
        assert "system_monitor" in names
        assert "ssh_execute" in names
        assert "docker_compose" in names

    def test_cybersecurity_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["cybersecurity"].tools]
        assert "port_scan" in names
        assert "password_strength" in names
        assert "hash_tool" in names
        assert "ssl_check" in names
        assert "network_scan" in names
        assert "dns_lookup" in names

    def test_travel_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["travel"].tools]
        assert "flight_search" in names
        assert "hotel_search" in names
        assert "currency_convert" in names
        assert "weather_check" in names
        assert "packing_list" in names
        assert "create_itinerary" in names

    def test_shopping_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["shopping"].tools]
        assert "product_search" in names
        assert "price_compare" in names
        assert "deal_finder" in names
        assert "wish_list" in names
        assert "product_review" in names

    def test_social_media_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["social_media"].tools]
        assert "social_post" in names
        assert "hashtag_generator" in names
        assert "content_calendar" in names
        assert "trend_analysis" in names
        assert "caption_writer" in names

    def test_education_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["education"].tools]
        assert "flashcards" in names
        assert "generate_quiz" in names
        assert "learning_path" in names
        assert "pomodoro_timer" in names
        assert "study_notes" in names

    def test_database_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["database"].tools]
        assert "sqlite_query" in names
        assert "db_info" in names
        assert "db_migrate" in names
        assert "query_optimizer" in names
        assert "db_backup" in names

    def test_translation_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["translation"].tools]
        assert "translate_text" in names
        assert "detect_language" in names
        assert "dictionary_lookup" in names

    def test_presentation_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["presentation"].tools]
        assert "create_slides" in names
        assert "slide_templates" in names
        assert "export_slides_pdf" in names

    def test_automation_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["automation"].tools]
        assert "create_automation" in names
        assert "list_automations" in names
        assert "cron_job" in names
        assert "file_watcher" in names
        assert "webhook_manager" in names

    def test_calendar_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["calendar"].tools]
        assert "create_event" in names
        assert "view_calendar" in names
        assert "check_availability" in names

    def test_network_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["network"].tools]
        assert "ping" in names
        assert "traceroute" in names
        assert "speed_test" in names
        assert "network_info" in names
        assert "whois_lookup" in names

    def test_pdf_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["pdf"].tools]
        assert "pdf_read" in names
        assert "pdf_merge" in names
        assert "pdf_split" in names
        assert "pdf_create" in names
        assert "pdf_info" in names

    def test_spreadsheet_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["spreadsheet"].tools]
        assert "create_spreadsheet" in names
        assert "read_spreadsheet" in names
        assert "formula_helper" in names
        assert "convert_spreadsheet" in names

    def test_api_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["api"].tools]
        assert "api_request" in names
        assert "api_docs" in names
        assert "api_load_test" in names
        assert "api_collection" in names

    def test_threed_tool_names(self):
        from vera.brain.agents import AGENT_REGISTRY

        names = [t.name for t in AGENT_REGISTRY["threed"].tools]
        assert "generate_3d_model" in names
        assert "scene_builder" in names
        assert "model_converter" in names
        assert "model_info" in names
