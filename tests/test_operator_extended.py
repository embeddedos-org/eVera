"""Tests for OperatorAgent.run() — policy checks, direct actions, app name extraction."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vera.safety.policy import PolicyAction, PolicyDecision


@pytest.fixture
def operator_agent():
    """Create an OperatorAgent instance."""
    from vera.brain.agents.operator import OperatorAgent
    return OperatorAgent()


class TestOperatorRun:
    """Tests for OperatorAgent.run() override — policy-checked direct actions."""

    @pytest.mark.asyncio
    async def test_open_app_allow_success(self, operator_agent):
        state = {
            "transcript": "open chrome",
            "intent": "open_app",
            "user_name": "Srikanth",
        }

        allow_decision = PolicyDecision(
            action=PolicyAction.ALLOW,
            reason="Allowed",
            agent_name="operator",
            tool_name="open_application",
        )

        mock_tool = AsyncMock()
        mock_tool.execute = AsyncMock(return_value={"status": "success"})

        with patch("vera.safety.policy.PolicyService") as mock_policy_service:
            mock_policy_service.return_value.check.return_value = allow_decision
            operator_agent.get_tool = MagicMock(return_value=mock_tool)

            result = await operator_agent.run(state)

            assert "Done" in result["agent_response"] or "chrome" in result["agent_response"].lower()
            assert result["mood"] == "happy"

    @pytest.mark.asyncio
    async def test_open_app_deny_returns_error(self, operator_agent):
        state = {
            "transcript": "open chrome",
            "intent": "open_app",
            "user_name": "",
        }

        deny_decision = PolicyDecision(
            action=PolicyAction.DENY,
            reason="Not allowed during lockdown",
            agent_name="operator",
            tool_name="open_application",
        )

        with patch("vera.safety.policy.PolicyService") as mock_policy_service:
            mock_policy_service.return_value.check.return_value = deny_decision

            result = await operator_agent.run(state)

            assert result["mood"] == "error"
            assert "Sorry" in result["agent_response"] or "can't open" in result["agent_response"].lower()

    @pytest.mark.asyncio
    async def test_open_app_confirm_not_approved(self, operator_agent):
        state = {
            "transcript": "open notepad",
            "intent": "open_app",
            "user_name": "Test",
            "safety_approved": False,
        }

        confirm_decision = PolicyDecision(
            action=PolicyAction.CONFIRM,
            reason="Needs confirmation",
            agent_name="operator",
            tool_name="open_application",
        )

        with patch("vera.safety.policy.PolicyService") as mock_policy_service:
            mock_policy_service.return_value.check.return_value = confirm_decision

            result = await operator_agent.run(state)

            assert result["mood"] == "thinking"
            assert result.get("needs_confirmation") is True
            assert "notepad" in result["agent_response"].lower()

    @pytest.mark.asyncio
    async def test_screenshot_allow_success(self, operator_agent):
        state = {
            "transcript": "take a screenshot",
            "intent": "screenshot",
            "user_name": "",
        }

        allow_decision = PolicyDecision(
            action=PolicyAction.ALLOW,
            reason="Allowed",
            agent_name="operator",
            tool_name="take_screenshot",
        )

        mock_tool = AsyncMock()
        mock_tool.execute = AsyncMock(return_value={"status": "success"})

        with patch("vera.safety.policy.PolicyService") as mock_policy_service:
            mock_policy_service.return_value.check.return_value = allow_decision
            operator_agent.get_tool = MagicMock(return_value=mock_tool)

            result = await operator_agent.run(state)

            assert result["mood"] == "happy"
            assert "📸" in result["agent_response"] or "screenshot" in result["agent_response"].lower()

    @pytest.mark.asyncio
    async def test_screenshot_deny(self, operator_agent):
        state = {
            "transcript": "take screenshot",
            "intent": "screenshot",
            "user_name": "",
        }

        deny_decision = PolicyDecision(
            action=PolicyAction.DENY,
            reason="Screenshots disabled",
            agent_name="operator",
            tool_name="take_screenshot",
        )

        with patch("vera.safety.policy.PolicyService") as mock_policy_service:
            mock_policy_service.return_value.check.return_value = deny_decision

            result = await operator_agent.run(state)

            assert result["mood"] == "error"
            assert "not allowed" in result["agent_response"].lower() or "Sorry" in result["agent_response"]

    @pytest.mark.asyncio
    async def test_open_app_tool_failure(self, operator_agent):
        state = {
            "transcript": "open some_weird_app",
            "intent": "open_app",
            "user_name": "",
        }

        allow_decision = PolicyDecision(
            action=PolicyAction.ALLOW,
            reason="OK",
            agent_name="operator",
            tool_name="open_application",
        )

        mock_tool = AsyncMock()
        mock_tool.execute = AsyncMock(return_value={"status": "error", "message": "App not found"})

        with patch("vera.safety.policy.PolicyService") as mock_policy_service:
            mock_policy_service.return_value.check.return_value = allow_decision
            operator_agent.get_tool = MagicMock(return_value=mock_tool)

            result = await operator_agent.run(state)

            assert result["mood"] == "error"
            assert "Hmm" in result["agent_response"] or "couldn't" in result["agent_response"].lower()


class TestExtractAppName:
    """Tests for OperatorAgent._extract_app_name()."""

    def test_known_app_chrome(self, operator_agent):
        result = operator_agent._extract_app_name("open chrome please")
        assert result == "chrome"

    def test_known_app_notepad(self, operator_agent):
        result = operator_agent._extract_app_name("can you start notepad")
        assert result == "notepad"

    def test_known_app_calculator(self, operator_agent):
        result = operator_agent._extract_app_name("launch the calculator")
        assert result in ("calculator", "calc")

    def test_unknown_app_regex_fallback(self, operator_agent):
        result = operator_agent._extract_app_name("open my_custom_app")
        assert result is not None
        assert "my_custom_app" in result

    def test_empty_transcript(self, operator_agent):
        result = operator_agent._extract_app_name("open")
        # After removing trigger words, might return None or empty cleaned text
        assert result is None or isinstance(result, str)
