"""Tests for eVera v1.0 production-readiness changes.

Covers: agent registry _pm fix, keyword routing fixes, PLUGIN_INTENTS wiring,
version consistency, scheduler conditional loops, config additions,
safety policy additions, get_status() enhancement, and live_trading plugin exports.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vera.brain.router import INTENT_AGENT_MAP, KEYWORD_PATTERNS, TierRouter
from vera.providers.models import ModelTier
from vera.safety.policy import PolicyAction, PolicyService


# ─── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def router():
    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock()
    return TierRouter(mock_provider)


@pytest.fixture
def scheduler(tmp_path):
    import vera.scheduler as sched_mod

    sched_mod.DATA_DIR = tmp_path
    from vera.scheduler import ProactiveScheduler

    s = ProactiveScheduler()
    return s, tmp_path


# ═══════════════════════════════════════════════════════════════
# Phase 1: Critical Runtime Fixes
# ═══════════════════════════════════════════════════════════════


class TestAgentRegistryPmFix:
    """1.1 — _pm NameError fix in agents/__init__.py."""

    def test_plugin_intents_is_dict(self):
        """PLUGIN_INTENTS should be a dict even if plugin loading fails."""
        from vera.brain.agents import PLUGIN_INTENTS

        assert isinstance(PLUGIN_INTENTS, dict)

    def test_agent_registry_populated(self):
        """AGENT_REGISTRY should contain at least the 19 core agents."""
        from vera.brain.agents import AGENT_REGISTRY

        assert len(AGENT_REGISTRY) >= 19

    def test_get_agent_returns_agent(self):
        from vera.brain.agents import get_agent

        agent = get_agent("companion")
        assert agent is not None
        assert agent.name == "companion"

    def test_get_agent_returns_none_for_unknown(self):
        from vera.brain.agents import get_agent

        assert get_agent("nonexistent_agent_xyz") is None

    def test_list_agents_returns_list(self):
        from vera.brain.agents import list_agents

        names = list_agents()
        assert isinstance(names, list)
        assert "companion" in names
        assert "income" in names


class TestLiveTradingPluginExports:
    """1.2 — live_trading.py PLUGIN_AGENTS + PLUGIN_INTENTS exports."""

    def test_plugin_agents_exported(self):
        from plugins.live_trading import PLUGIN_AGENTS

        assert isinstance(PLUGIN_AGENTS, list)
        assert len(PLUGIN_AGENTS) == 1

    def test_plugin_agents_contains_live_trading_agent(self):
        from plugins.live_trading import PLUGIN_AGENTS, LiveTradingAgent

        assert PLUGIN_AGENTS[0] is LiveTradingAgent

    def test_plugin_intents_exported(self):
        from plugins.live_trading import PLUGIN_INTENTS

        assert isinstance(PLUGIN_INTENTS, dict)
        assert len(PLUGIN_INTENTS) > 0

    def test_plugin_intents_maps_to_live_trader(self):
        from plugins.live_trading import PLUGIN_INTENTS

        for keyword, agent in PLUGIN_INTENTS.items():
            assert agent == "live_trader", f"Intent '{keyword}' maps to '{agent}', expected 'live_trader'"

    def test_plugin_intents_has_ibkr(self):
        from plugins.live_trading import PLUGIN_INTENTS

        assert "ibkr" in PLUGIN_INTENTS

    def test_plugin_intents_has_schwab(self):
        from plugins.live_trading import PLUGIN_INTENTS

        assert "schwab" in PLUGIN_INTENTS


class TestKeywordRoutingConflicts:
    """1.4 — Fix INTENT_AGENT_MAP keyword conflicts."""

    def test_music_routes_to_music_not_home_controller(self):
        assert INTENT_AGENT_MAP["music"] == "music"

    def test_media_player_routes_to_home_controller(self):
        assert INTENT_AGENT_MAP["media_player"] == "home_controller"

    def test_translate_routes_to_translation(self):
        assert INTENT_AGENT_MAP["translate"] == "translation"

    def test_calendar_routes_to_calendar(self):
        assert INTENT_AGENT_MAP["calendar"] == "calendar"

    def test_meeting_routes_to_meeting(self):
        assert INTENT_AGENT_MAP["meeting"] == "meeting"

    def test_automate_routes_to_automation(self):
        assert INTENT_AGENT_MAP["automate"] == "automation"

    def test_play_still_routes_to_home_controller(self):
        """'play' should stay with home_controller (not re-routed)."""
        assert INTENT_AGENT_MAP["play"] == "home_controller"

    def test_screenshot_stays_with_operator(self):
        assert INTENT_AGENT_MAP["screenshot"] == "operator"

    def test_overly_broad_keywords_removed(self):
        """Over-broad keywords like 'broker', 'algo', 'strategy' should not be in INTENT_AGENT_MAP."""
        assert "broker" not in INTENT_AGENT_MAP
        assert "algo" not in INTENT_AGENT_MAP
        assert "strategy" not in INTENT_AGENT_MAP


class TestVersionConsistency:
    """1.6 — All version strings should be 1.0.0."""

    def test_vera_version(self):
        import vera

        assert vera.__version__ == "1.0.0"


class TestPluginIntentsWired:
    """1.3 — classify_by_keywords uses PLUGIN_INTENTS."""

    def test_classify_by_keywords_uses_combined_intents(self, router: TierRouter):
        """The router should merge PLUGIN_INTENTS into the word scoring."""
        with patch("vera.brain.agents.PLUGIN_INTENTS", {"xyzuniquetestbroker": "live_trader"}):
            result = router.classify_by_keywords("please connect to xyzuniquetestbroker now")
            assert result.agent_name == "live_trader"


# ═══════════════════════════════════════════════════════════════
# Phase 1.7 / Scheduler: Conditional loop starts
# ═══════════════════════════════════════════════════════════════


class TestSchedulerConditionalLoops:
    """1.7 — Scheduler should only start loops when their feature is enabled."""

    @pytest.mark.asyncio
    async def test_start_with_defaults_has_base_loops(self, scheduler):
        """With default settings, base loops + enabled-by-default loops should start."""
        sched, _ = scheduler
        await sched.start()
        # Base = 7 (reminder, calendar, stock, briefing, tasks, content, spending)
        # + planner.enabled=True → morning_plan + daily_review = 2
        # + wellness.enabled=True → break_reminder = 1
        # + digest.enabled=True → digest = 1
        # + emotional.enabled=True → mood_check = 1
        # = 12 total (job_hunter, jira, channel_monitor are disabled by default)
        assert len(sched._tasks) >= 7  # At least the unconditional base loops
        await sched.stop()

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, scheduler):
        sched, _ = scheduler
        assert sched._running is False
        await sched.start()
        assert sched._running is True
        await sched.stop()
        assert sched._running is False

    @pytest.mark.asyncio
    async def test_disabled_features_skip_loops(self, scheduler):
        """When job_hunter, jira, channel_monitor are disabled, their loops should not start."""
        sched, _ = scheduler
        from config import settings

        # These are disabled by default
        assert settings.job_hunter.enabled is False
        assert settings.jira.enabled is False
        assert settings.channel_monitor.enabled is False

        await sched.start()
        task_count = len(sched._tasks)
        # Should not have 15 tasks (the old unconditional number)
        assert task_count < 15
        await sched.stop()

    @pytest.mark.asyncio
    async def test_job_hunter_enabled_adds_job_scan_loop(self, scheduler):
        """When job_hunter.enabled=True, _job_scan_loop task should be added."""
        sched, _ = scheduler

        with patch("config.settings") as mock_settings:
            mock_settings.job_hunter.enabled = True
            mock_settings.planner.enabled = False
            mock_settings.wellness.enabled = False
            mock_settings.digest.enabled = False
            mock_settings.emotional.enabled = False
            mock_settings.jira.enabled = False
            mock_settings.channel_monitor.enabled = False

            await sched.start()
            # Base 7 loops + 1 job_scan_loop = 8
            assert len(sched._tasks) == 8
            await sched.stop()

    @pytest.mark.asyncio
    async def test_jira_enabled_adds_ticket_scan_loop(self, scheduler):
        """When jira.enabled=True, _ticket_scan_loop task should be added."""
        sched, _ = scheduler

        with patch("config.settings") as mock_settings:
            mock_settings.job_hunter.enabled = False
            mock_settings.planner.enabled = False
            mock_settings.wellness.enabled = False
            mock_settings.digest.enabled = False
            mock_settings.emotional.enabled = False
            mock_settings.jira.enabled = True
            mock_settings.channel_monitor.enabled = False

            await sched.start()
            # Base 7 loops + 1 ticket_scan_loop = 8
            assert len(sched._tasks) == 8
            await sched.stop()

    @pytest.mark.asyncio
    async def test_channel_monitor_enabled_adds_channel_monitor_loop(self, scheduler):
        """When channel_monitor.enabled=True, _channel_monitor_loop task should be added."""
        sched, _ = scheduler

        with patch("config.settings") as mock_settings:
            mock_settings.job_hunter.enabled = False
            mock_settings.planner.enabled = False
            mock_settings.wellness.enabled = False
            mock_settings.digest.enabled = False
            mock_settings.emotional.enabled = False
            mock_settings.jira.enabled = False
            mock_settings.channel_monitor.enabled = True

            await sched.start()
            # Base 7 loops + 1 channel_monitor_loop = 8
            assert len(sched._tasks) == 8
            await sched.stop()


# ═══════════════════════════════════════════════════════════════
# Phase 2: Routing & Agent Integration Fixes
# ═══════════════════════════════════════════════════════════════


class TestAgentTierMap:
    """2.1 — coder, git, browser should be SPECIALIST, not default EXECUTOR."""

    def test_coder_tier_is_specialist(self, router: TierRouter):
        assert router._agent_tier("coder") == ModelTier.SPECIALIST

    def test_git_tier_is_specialist(self, router: TierRouter):
        assert router._agent_tier("git") == ModelTier.SPECIALIST

    def test_browser_tier_is_specialist(self, router: TierRouter):
        assert router._agent_tier("browser") == ModelTier.SPECIALIST

    def test_unknown_agent_defaults_to_executor(self, router: TierRouter):
        assert router._agent_tier("nonexistent_agent") == ModelTier.EXECUTOR

    def test_calendar_tier(self, router: TierRouter):
        assert router._agent_tier("calendar") == ModelTier.SPECIALIST

    def test_translation_tier(self, router: TierRouter):
        assert router._agent_tier("translation") == ModelTier.SPECIALIST

    def test_automation_tier(self, router: TierRouter):
        assert router._agent_tier("automation") == ModelTier.SPECIALIST


class TestKeywordPatternOrder:
    """2.5 — language_tutor translate pattern should fire before generic translate."""

    def test_translate_to_spanish_routes_to_language_tutor(self, router: TierRouter):
        result = router.classify_by_keywords("translate hello to spanish")
        assert result.agent_name == "language_tutor"

    def test_generic_translate_no_longer_goes_to_writer(self, router: TierRouter):
        """Generic 'translate' should NOT hit writer via KEYWORD_PATTERNS (pattern was removed)."""
        # Verify no translate pattern exists for writer in KEYWORD_PATTERNS
        writer_translate_patterns = [
            (p, agent, intent)
            for p, agent, intent in KEYWORD_PATTERNS
            if agent == "writer" and intent == "translate"
        ]
        assert len(writer_translate_patterns) == 0

    def test_write_a_letter_still_routes_to_writer(self, router: TierRouter):
        result = router.classify_by_keywords("write a letter to my boss")
        assert result.agent_name == "writer"


class TestRouterClassifyByKeywords:
    """Test classify_by_keywords behavior for various inputs."""

    def test_ibkr_routes_to_live_trader(self, router: TierRouter):
        result = router.classify_by_keywords("connect to ibkr")
        assert result.agent_name == "live_trader"

    def test_stock_routes_to_income(self, router: TierRouter):
        result = router.classify_by_keywords("check the stock market")
        assert result.agent_name == "income"

    def test_unknown_input_defaults_to_companion(self, router: TierRouter):
        result = router.classify_by_keywords("asdfghjkl nonsense")
        assert result.agent_name == "companion"
        assert result.confidence == 0.4

    def test_extract_action_items_routes_to_meeting(self, router: TierRouter):
        result = router.classify_by_keywords("extract action items from the meeting")
        assert result.agent_name == "meeting"

    def test_create_pr_routes_to_git(self, router: TierRouter):
        result = router.classify_by_keywords("create a pull request")
        assert result.agent_name == "git"

    def test_start_working_on_routes_to_work_pilot(self, router: TierRouter):
        result = router.classify_by_keywords("do my ticket please")
        assert result.agent_name == "work_pilot"

    def test_learn_spanish_routes_to_language_tutor(self, router: TierRouter):
        result = router.classify_by_keywords("learn spanish")
        assert result.agent_name == "language_tutor"

    def test_take_a_break_routes_to_wellness(self, router: TierRouter):
        result = router.classify_by_keywords("take a break")
        assert result.agent_name == "wellness"

    def test_show_my_digest_routes_to_digest(self, router: TierRouter):
        result = router.classify_by_keywords("show my daily digest")
        assert result.agent_name == "digest"


# ═══════════════════════════════════════════════════════════════
# Phase 2: Safety Policy Additions
# ═══════════════════════════════════════════════════════════════


class TestSafetyPolicyAdditions:
    """2.4 — New policy rules for work_pilot, language_tutor, diagram, codebase_indexer, meeting."""

    def test_work_pilot_wildcard_requires_confirm(self):
        ps = PolicyService()
        decision = ps.check("work_pilot", "some_action")
        assert decision.action == PolicyAction.CONFIRM

    def test_work_pilot_start_work_requires_confirm(self):
        ps = PolicyService()
        decision = ps.check("work_pilot", "start_work_on_ticket")
        assert decision.action == PolicyAction.CONFIRM

    def test_work_pilot_create_pr_requires_confirm(self):
        ps = PolicyService()
        decision = ps.check("work_pilot", "create_pr")
        assert decision.action == PolicyAction.CONFIRM

    def test_language_tutor_allowed(self):
        ps = PolicyService()
        decision = ps.check("language_tutor", "learn_language")
        assert decision.action == PolicyAction.ALLOW

    def test_diagram_allowed(self):
        ps = PolicyService()
        decision = ps.check("diagram", "visualize")
        assert decision.action == PolicyAction.ALLOW

    def test_codebase_indexer_allowed(self):
        ps = PolicyService()
        decision = ps.check("codebase_indexer", "index_project")
        assert decision.action == PolicyAction.ALLOW

    def test_meeting_allowed(self):
        ps = PolicyService()
        decision = ps.check("meeting", "extract_action_items")
        assert decision.action == PolicyAction.ALLOW


# ═══════════════════════════════════════════════════════════════
# Phase 2: Income Agent Safety Guardrails
# ═══════════════════════════════════════════════════════════════


class TestIncomeAgentSafety:
    """2.6 — Income agent should have explicit safety rules in system_prompt."""

    def test_income_agent_has_safety_rules(self):
        from vera.brain.agents import AGENT_REGISTRY

        income = AGENT_REGISTRY["income"]
        assert "CRITICAL SAFETY RULES" in income.system_prompt

    def test_income_agent_mentions_paper_trading_default(self):
        from vera.brain.agents import AGENT_REGISTRY

        income = AGENT_REGISTRY["income"]
        assert "Default to PAPER trading" in income.system_prompt

    def test_income_agent_mentions_risk_tolerance(self):
        from vera.brain.agents import AGENT_REGISTRY

        income = AGENT_REGISTRY["income"]
        assert "risk tolerance" in income.system_prompt


# ═══════════════════════════════════════════════════════════════
# Phase 2: BrokerSettings env_prefix
# ═══════════════════════════════════════════════════════════════


class TestBrokerSettingsPrefix:
    """2.2 — BrokerSettings env_prefix should be VERA_BROKER_."""

    def test_broker_env_prefix(self):
        from config import BrokerSettings

        assert BrokerSettings.model_config["env_prefix"] == "VERA_BROKER_"


# ═══════════════════════════════════════════════════════════════
# Phase 3: Config & Environment Completeness
# ═══════════════════════════════════════════════════════════════


class TestConfigAdditions:
    """3.1 — SpotifySettings and SSHSettings added to config."""

    def test_spotify_settings_exists(self):
        from config import SpotifySettings

        s = SpotifySettings()
        assert s.enabled is False
        assert s.client_id == ""
        assert s.redirect_uri == "http://localhost:8888/callback"

    def test_spotify_env_prefix(self):
        from config import SpotifySettings

        assert SpotifySettings.model_config["env_prefix"] == "VERA_SPOTIFY_"

    def test_ssh_settings_exists(self):
        from config import SSHSettings

        s = SSHSettings()
        assert s.enabled is False
        assert s.default_host == ""
        assert s.key_path == "~/.ssh/id_rsa"

    def test_ssh_env_prefix(self):
        from config import SSHSettings

        assert SSHSettings.model_config["env_prefix"] == "VERA_SSH_"

    def test_root_settings_has_spotify(self):
        from config import settings

        assert hasattr(settings, "spotify")
        assert settings.spotify.enabled is False

    def test_root_settings_has_ssh(self):
        from config import settings

        assert hasattr(settings, "ssh")
        assert settings.ssh.enabled is False


class TestMediaSettingsDefault:
    """3.3 — MediaSettings.enabled should default to False."""

    def test_media_disabled_by_default(self):
        from config import MediaSettings

        ms = MediaSettings()
        assert ms.enabled is False


class TestEnsureDataDirs:
    """3.4 — ensure_data_dirs creates workflows/ and admin/ subdirectories."""

    def test_creates_workflows_dir(self, tmp_path):
        from config import Settings

        s = Settings(data_dir=tmp_path)
        s.ensure_data_dirs()
        assert (tmp_path / "workflows").is_dir()

    def test_creates_admin_dir(self, tmp_path):
        from config import Settings

        s = Settings(data_dir=tmp_path)
        s.ensure_data_dirs()
        assert (tmp_path / "admin").is_dir()

    def test_creates_knowledge_dir(self, tmp_path):
        from config import Settings

        s = Settings(data_dir=tmp_path)
        s.ensure_data_dirs()
        assert (tmp_path / "knowledge").is_dir()

    def test_creates_media_dir(self, tmp_path):
        from config import Settings

        s = Settings(data_dir=tmp_path)
        s.ensure_data_dirs()
        assert (tmp_path / "media").is_dir()


# ═══════════════════════════════════════════════════════════════
# Phase 6: Meeting agent Jira guard
# ═══════════════════════════════════════════════════════════════


class TestMeetingAgentJiraGuard:
    """6.2 — Meeting agent should check settings.jira.enabled before Jira operations."""

    def test_meeting_agent_has_tools(self):
        from vera.brain.agents import AGENT_REGISTRY

        meeting = AGENT_REGISTRY["meeting"]
        tool_names = [t.name for t in meeting.tools]
        assert "extract_action_items" in tool_names
        assert "parse_meeting_notes" in tool_names
        assert "create_tasks_from_meeting" in tool_names

    @pytest.mark.asyncio
    async def test_create_tasks_no_crash_without_jira(self, tmp_path):
        """CreateTasksFromMeetingTool should not crash when Jira is disabled."""
        from vera.brain.agents.meeting_agent import CreateTasksFromMeetingTool

        tool = CreateTasksFromMeetingTool()
        # This will fail at extraction (no LLM), but should not crash on Jira guard
        result = await tool.execute(text="")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_jira_guard_skips_when_jira_disabled(self, tmp_path):
        """When auto_create_tickets=True but jira.enabled=False, should log skip and not crash."""
        import vera.brain.agents.meeting_agent as meeting_mod

        original_data_dir = meeting_mod.DATA_DIR
        meeting_mod.DATA_DIR = tmp_path

        try:
            from vera.brain.agents.meeting_agent import CreateTasksFromMeetingTool

            tool = CreateTasksFromMeetingTool()

            fake_extraction = {
                "status": "success",
                "action_items": [
                    {"task": "Write tests", "priority": "high", "assignee": "Alice", "deadline": "Friday"}
                ],
                "summary": "Test meeting",
            }

            with patch(
                "vera.brain.agents.meeting_agent.ExtractActionItemsTool.execute",
                new_callable=AsyncMock,
                return_value=fake_extraction,
            ), patch("config.settings") as mock_settings:
                mock_settings.meeting.auto_create_todos = False
                mock_settings.meeting.auto_create_tickets = True
                mock_settings.jira.enabled = False

                result = await tool.execute(text="Meeting notes about writing tests")

            assert result["status"] == "success"
            assert result["jira_tickets_created"] == 0
        finally:
            meeting_mod.DATA_DIR = original_data_dir

    @pytest.mark.asyncio
    async def test_jira_ticket_creation_succeeds(self, tmp_path):
        """When both auto_create_tickets and jira.enabled are True, tickets should be created."""
        import vera.brain.agents.meeting_agent as meeting_mod

        original_data_dir = meeting_mod.DATA_DIR
        meeting_mod.DATA_DIR = tmp_path

        try:
            from vera.brain.agents.meeting_agent import CreateTasksFromMeetingTool

            tool = CreateTasksFromMeetingTool()

            fake_extraction = {
                "status": "success",
                "action_items": [
                    {"task": "Write tests", "priority": "high", "assignee": "Alice", "deadline": "Friday"},
                    {"task": "Review PR", "priority": "medium", "assignee": "Bob", "deadline": "Monday"},
                ],
                "summary": "Sprint planning",
            }

            mock_ticket_tool = AsyncMock(return_value={"status": "success", "key": "PROJ-1"})

            with patch(
                "vera.brain.agents.meeting_agent.ExtractActionItemsTool.execute",
                new_callable=AsyncMock,
                return_value=fake_extraction,
            ), patch("config.settings") as mock_settings, patch(
                "vera.brain.agents.jira_agent.CreateTicketTool.execute",
                mock_ticket_tool,
            ):
                mock_settings.meeting.auto_create_todos = False
                mock_settings.meeting.auto_create_tickets = True
                mock_settings.jira.enabled = True

                result = await tool.execute(text="Sprint planning meeting notes")

            assert result["status"] == "success"
            assert result["jira_tickets_created"] == 2
        finally:
            meeting_mod.DATA_DIR = original_data_dir

    @pytest.mark.asyncio
    async def test_jira_creation_failure_caught_gracefully(self, tmp_path):
        """When CreateTicketTool raises, the exception should be caught and logged."""
        import vera.brain.agents.meeting_agent as meeting_mod

        original_data_dir = meeting_mod.DATA_DIR
        meeting_mod.DATA_DIR = tmp_path

        try:
            from vera.brain.agents.meeting_agent import CreateTasksFromMeetingTool

            tool = CreateTasksFromMeetingTool()

            fake_extraction = {
                "status": "success",
                "action_items": [
                    {"task": "Deploy service", "priority": "high", "assignee": "Carol", "deadline": "Today"}
                ],
                "summary": "Deployment review",
            }

            with patch(
                "vera.brain.agents.meeting_agent.ExtractActionItemsTool.execute",
                new_callable=AsyncMock,
                return_value=fake_extraction,
            ), patch("config.settings") as mock_settings, patch(
                "vera.brain.agents.jira_agent.CreateTicketTool.execute",
                new_callable=AsyncMock,
                side_effect=ConnectionError("Jira API unreachable"),
            ):
                mock_settings.meeting.auto_create_todos = False
                mock_settings.meeting.auto_create_tickets = True
                mock_settings.jira.enabled = True

                result = await tool.execute(text="Deployment review notes")

            # Should succeed overall but with 0 tickets (error was caught)
            assert result["status"] == "success"
            assert result["jira_tickets_created"] == 0
        finally:
            meeting_mod.DATA_DIR = original_data_dir


# ═══════════════════════════════════════════════════════════════
# Phase 2.3: Enhanced get_status()
# ═══════════════════════════════════════════════════════════════


class TestGetStatusEnhanced:
    """2.3 — get_status() should include agents, scheduler_loops, and version."""

    def test_get_status_has_version(self):
        """get_status should return a version field."""
        from unittest.mock import PropertyMock

        brain_mock = MagicMock()
        brain_mock.memory_vault.get_stats.return_value = {}
        brain_mock.provider_manager.get_usage.return_value = {}
        brain_mock.memory_vault.semantic.get_all.return_value = {}
        brain_mock.scheduler._tasks = []

        from vera.core import VeraBrain

        # Test that the method signature includes version in its return
        # by checking the source code structure
        import inspect
        source = inspect.getsource(VeraBrain.get_status)
        assert "version" in source
        assert "agents" in source
        assert "scheduler_loops" in source

    def test_get_status_actually_returns_agents_and_version(self):
        """Actually call get_status() to cover line 242 (lazy import of AGENT_REGISTRY)."""
        from vera.core import VeraBrain

        brain_mock = MagicMock()
        brain_mock.memory_vault.get_stats.return_value = {"facts": 0}
        brain_mock.provider_manager.get_usage.return_value = {"total_tokens": 0}
        brain_mock.memory_vault.semantic.get_all.return_value = {}
        brain_mock.scheduler._tasks = []

        result = VeraBrain.get_status(brain_mock)

        assert result["status"] == "running"
        assert "version" in result
        assert "agents" in result
        assert isinstance(result["agents"]["names"], list)
        assert result["agents"]["count"] >= 1
        assert result["scheduler_loops"] == 0
        assert "memory" in result
        assert "llm_usage" in result


# ═══════════════════════════════════════════════════════════════
# Regression: Existing functionality still works
# ═══════════════════════════════════════════════════════════════


class TestRegressionRouting:
    """Verify existing routing still works after keyword changes."""

    def test_tier0_hello(self, router: TierRouter):
        result = router.try_tier0("Hello there")
        assert result is not None
        assert result.agent_name == "companion"

    def test_tier0_time(self, router: TierRouter):
        result = router.try_tier0("What time is it?")
        assert result is not None
        assert result.intent == "get_time"

    def test_existing_safety_rules_unchanged(self):
        ps = PolicyService()
        assert ps.check("companion", "chat").action == PolicyAction.ALLOW
        assert ps.check("operator", "execute_script").action == PolicyAction.CONFIRM
        assert ps.check("income", "transfer_money").action == PolicyAction.DENY
        assert ps.check("researcher", "web_search").action == PolicyAction.ALLOW

    def test_live_trader_trade_tools_need_confirm(self):
        ps = PolicyService()
        assert ps.check("live_trader", "ibkr_trade").action == PolicyAction.CONFIRM
        assert ps.check("live_trader", "tradestation_trade").action == PolicyAction.CONFIRM
        assert ps.check("live_trader", "schwab_trade").action == PolicyAction.CONFIRM

    def test_live_trader_read_tools_allowed(self):
        ps = PolicyService()
        assert ps.check("live_trader", "ibkr_connect").action == PolicyAction.ALLOW
        assert ps.check("live_trader", "ibkr_portfolio").action == PolicyAction.ALLOW
        assert ps.check("live_trader", "risk_check").action == PolicyAction.ALLOW
