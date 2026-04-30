"""Integration tests for new agent routing — keyword classification and tier mapping.

Tests that the TierRouter correctly routes transcripts to new agents
via Tier 0 patterns, keyword matching, and tier assignments.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestNewAgentRouting:
    """Test keyword-based routing to new agents."""

    @pytest.fixture
    def router(self):
        with patch("vera.providers.manager.litellm"):
            from vera.brain.router import TierRouter
            from vera.providers.manager import ProviderManager

            pm = ProviderManager()
            return TierRouter(pm)

    def test_music_keywords(self, router):
        for kw in ["play some spotify", "find me a playlist", "what song is this", "recommend a podcast"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "music", f"'{kw}' routed to '{result.agent_name}' instead of 'music'"

    def test_data_analyst_keywords(self, router):
        for kw in ["analyze this csv", "show me the chart", "run statistics on data"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "data_analyst", f"'{kw}' routed to '{result.agent_name}'"

    def test_devops_keywords(self, router):
        for kw in ["list docker containers", "deploy to kubernetes", "check server status", "run nginx"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "devops", f"'{kw}' routed to '{result.agent_name}'"

    def test_cybersecurity_keywords(self, router):
        for kw in ["check ssl certificate", "scan for vulnerability", "hash this password"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "cybersecurity", f"'{kw}' routed to '{result.agent_name}'"

    def test_travel_keywords(self, router):
        for kw in ["search flights to paris", "book a hotel", "check weather in london", "plan my trip"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "travel", f"'{kw}' routed to '{result.agent_name}'"

    def test_shopping_keywords(self, router):
        for kw in ["find me the best deal", "compare price", "add to wishlist", "any coupon available"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "shopping", f"'{kw}' routed to '{result.agent_name}'"

    def test_education_keywords(self, router):
        for kw in ["create a flashcard", "give me a quiz", "help me study"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "education", f"'{kw}' routed to '{result.agent_name}'"

    def test_database_keywords(self, router):
        for kw in ["run sql query", "show database schema", "create migration"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "database", f"'{kw}' routed to '{result.agent_name}'"

    def test_translation_keywords(self, router):
        for kw in ["translate this to spanish", "look up in dictionary"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "translation", f"'{kw}' routed to '{result.agent_name}'"

    def test_presentation_keywords(self, router):
        for kw in ["create slides for meeting", "make a pitch deck", "build a powerpoint"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "presentation", f"'{kw}' routed to '{result.agent_name}'"

    def test_automation_keywords(self, router):
        for kw in ["set up a cron job", "create webhook", "automate this trigger"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "automation", f"'{kw}' routed to '{result.agent_name}'"

    def test_calendar_keywords(self, router):
        for kw in ["check my calendar", "create an event", "am i available tomorrow"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "calendar", f"'{kw}' routed to '{result.agent_name}'"

    def test_network_keywords(self, router):
        for kw in ["ping google", "run speedtest", "whois lookup"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "network", f"'{kw}' routed to '{result.agent_name}'"

    def test_pdf_keywords(self, router):
        for kw in ["read this pdf", "merge pdf files"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "pdf", f"'{kw}' routed to '{result.agent_name}'"

    def test_spreadsheet_keywords(self, router):
        for kw in ["help with vlookup formula", "create a spreadsheet"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "spreadsheet", f"'{kw}' routed to '{result.agent_name}'"

    def test_api_keywords(self, router):
        for kw in ["test this api endpoint", "check swagger docs", "send a curl request"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "api", f"'{kw}' routed to '{result.agent_name}'"

    def test_threed_keywords(self, router):
        for kw in ["generate 3d model", "create a mesh", "convert this obj file"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "threed", f"'{kw}' routed to '{result.agent_name}'"


class TestNewAgentTierMapping:
    """Test that new agents have correct tier assignments."""

    @pytest.fixture
    def router(self):
        with patch("vera.providers.manager.litellm"):
            from vera.brain.router import TierRouter
            from vera.providers.manager import ProviderManager

            pm = ProviderManager()
            return TierRouter(pm)

    def test_executor_tier_agents(self, router):
        """Agents that should use EXECUTOR tier (fast, local)."""
        from vera.providers.models import ModelTier

        for name in ["music", "education", "translation", "calendar", "pdf", "spreadsheet"]:
            tier = router._agent_tier(name)
            assert tier == ModelTier.EXECUTOR, f"'{name}' should be EXECUTOR, got {tier}"

    def test_specialist_tier_agents(self, router):
        """Agents that should use SPECIALIST tier (cloud LLM)."""
        from vera.providers.models import ModelTier

        for name in ["data_analyst", "computer_use", "devops", "cybersecurity",
                      "travel", "shopping", "social_media", "database",
                      "presentation", "automation", "network", "api", "threed"]:
            tier = router._agent_tier(name)
            assert tier == ModelTier.SPECIALIST, f"'{name}' should be SPECIALIST, got {tier}"


class TestNewAgentLLMClassification:
    """Test LLM-based classification includes new agents in prompt."""

    def test_classification_prompt_includes_new_agents(self):
        """The LLM classification prompt should list all new agents."""
        from vera.brain.router import INTENT_AGENT_MAP

        new_agent_keywords = [
            "spotify", "docker", "flight", "flashcard", "sql",
            "translate", "slides", "cron", "ping", "pdf",
            "spreadsheet", "api", "3d", "mesh",
        ]
        for kw in new_agent_keywords:
            assert kw in INTENT_AGENT_MAP, f"Keyword '{kw}' missing from INTENT_AGENT_MAP"

    def test_intent_agent_map_has_new_agents(self):
        from vera.brain.router import INTENT_AGENT_MAP

        new_agents = {
            "music", "data_analyst", "computer_use", "devops", "cybersecurity",
            "travel", "shopping", "social_media", "education", "database",
            "translation", "presentation", "automation", "calendar", "network",
            "pdf", "spreadsheet", "api", "threed",
        }
        mapped_agents = set(INTENT_AGENT_MAP.values())
        for agent in new_agents:
            assert agent in mapped_agents, f"Agent '{agent}' has no keywords in INTENT_AGENT_MAP"
