"""Integration tests for new agent routing — keyword classification and tier mapping.

Tests that the TierRouter correctly routes transcripts to new agents
via Tier 0 patterns, keyword matching, and tier assignments.
Updated after production-readiness keyword fixes.
"""

from __future__ import annotations

from unittest.mock import patch

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

    def test_music_keyword_direct(self, router):
        result = router.classify_by_keywords("music recommendations please")
        assert result.agent_name == "music"

    def test_data_analyst_keywords(self, router):
        for kw in ["analyze this csv data", "show me statistics on the dataset"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "data_analyst", f"'{kw}' routed to '{result.agent_name}'"

    def test_devops_keywords(self, router):
        for kw in ["list docker containers", "deploy to kubernetes"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "devops", f"'{kw}' routed to '{result.agent_name}'"

    def test_cybersecurity_keywords(self, router):
        for kw in ["check ssl certificate", "scan for vulnerability"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "cybersecurity", f"'{kw}' routed to '{result.agent_name}'"

    def test_travel_keywords(self, router):
        for kw in ["hotel in tokyo", "flight to london", "trip itinerary vacation"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "travel", f"'{kw}' routed to '{result.agent_name}'"

    def test_shopping_keywords(self, router):
        for kw in ["coupon available", "deal on laptops", "wishlist items"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "shopping", f"'{kw}' routed to '{result.agent_name}'"

    def test_education_keywords(self, router):
        for kw in ["create a flashcard deck", "quiz me on history"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "education", f"'{kw}' routed to '{result.agent_name}'"

    def test_database_keywords(self, router):
        for kw in ["sql query on users table", "show database schema"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "database", f"'{kw}' routed to '{result.agent_name}'"

    def test_translation_keywords(self, router):
        result = router.classify_by_keywords("translate hello to spanish")
        assert result.agent_name == "language_tutor"  # Specific translate-to pattern fires first

    def test_translation_via_word_match(self, router):
        result = router.classify_by_keywords("need translation of this document")
        assert result.agent_name == "translation"

    def test_presentation_keywords(self, router):
        for kw in ["create slides for the meeting", "build a powerpoint deck"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "presentation", f"'{kw}' routed to '{result.agent_name}'"

    def test_automation_keywords(self, router):
        for kw in ["set up a cron job schedule", "create a webhook endpoint"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "automation", f"'{kw}' routed to '{result.agent_name}'"

    def test_calendar_keyword_direct(self, router):
        result = router.classify_by_keywords("calendar event tomorrow")
        assert result.agent_name == "calendar"

    def test_network_keywords(self, router):
        for kw in ["ping the server", "traceroute to host", "speedtest bandwidth"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "network", f"'{kw}' routed to '{result.agent_name}'"

    def test_pdf_keywords(self, router):
        result = router.classify_by_keywords("pdf merge these documents")
        assert result.agent_name == "pdf"

    def test_spreadsheet_keywords(self, router):
        for kw in ["help with vlookup formula", "create a spreadsheet report"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "spreadsheet", f"'{kw}' routed to '{result.agent_name}'"

    def test_api_keywords(self, router):
        for kw in ["test this api endpoint", "check swagger docs"]:
            result = router.classify_by_keywords(kw)
            assert result.agent_name == "api", f"'{kw}' routed to '{result.agent_name}'"

    def test_threed_keywords(self, router):
        for kw in ["create a mesh model", "convert this obj file"]:
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
        from vera.providers.models import ModelTier

        for name in ["music", "education", "pdf", "spreadsheet"]:
            tier = router._agent_tier(name)
            assert tier == ModelTier.EXECUTOR, f"'{name}' should be EXECUTOR, got {tier}"

    def test_specialist_tier_agents(self, router):
        from vera.providers.models import ModelTier

        for name in [
            "data_analyst",
            "computer_use",
            "devops",
            "cybersecurity",
            "travel",
            "shopping",
            "social_media",
            "database",
            "presentation",
            "automation",
            "network",
            "api",
            "threed",
            "calendar",
        ]:
            tier = router._agent_tier(name)
            assert tier == ModelTier.SPECIALIST, f"'{name}' should be SPECIALIST, got {tier}"


class TestNewAgentLLMClassification:
    """Test LLM-based classification includes new agents in prompt."""

    def test_classification_prompt_includes_new_agents(self):
        from vera.brain.router import INTENT_AGENT_MAP

        new_agent_keywords = [
            "spotify",
            "docker",
            "flight",
            "flashcard",
            "sql",
            "translate",
            "slides",
            "cron",
            "ping",
            "pdf",
            "spreadsheet",
            "api",
            "mesh",
        ]
        for kw in new_agent_keywords:
            assert kw in INTENT_AGENT_MAP, f"Keyword '{kw}' missing from INTENT_AGENT_MAP"

    def test_intent_agent_map_has_new_agents(self):
        from vera.brain.router import INTENT_AGENT_MAP

        new_agents = {
            "music",
            "data_analyst",
            "computer_use",
            "devops",
            "cybersecurity",
            "travel",
            "shopping",
            "social_media",
            "education",
            "database",
            "translation",
            "presentation",
            "automation",
            "calendar",
            "network",
            "pdf",
            "spreadsheet",
            "api",
            "threed",
        }
        mapped_agents = set(INTENT_AGENT_MAP.values())
        for agent in new_agents:
            assert agent in mapped_agents, f"Agent '{agent}' has no keywords in INTENT_AGENT_MAP"
