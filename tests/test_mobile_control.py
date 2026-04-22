"""Tests for Feature 9: Mobile device control."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestMobileControlAgent:
    def test_agent_creation(self):
        from vera.brain.agents.mobile import MobileControlAgent
        agent = MobileControlAgent(mobile_sessions={})
        assert agent.name == "mobile_controller"
        assert len(agent._tools) == 6

    def test_tools_have_mobile_sessions(self):
        sessions = {"test": {}}
        from vera.brain.agents.mobile import MobileControlAgent
        agent = MobileControlAgent(mobile_sessions=sessions)
        for tool in agent._tools:
            assert hasattr(tool, "_mobile_sessions")
            assert tool._mobile_sessions is sessions


class TestSendToMobile:
    @pytest.mark.asyncio
    async def test_no_sessions(self):
        from vera.brain.agents.mobile import _send_to_mobile
        result = await _send_to_mobile({}, "test_cmd")
        assert result["status"] == "error"
        assert "no mobile" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_command_serialization(self):
        ws_mock = AsyncMock()
        ws_mock.send_json = AsyncMock()

        sessions = {
            "mobile-1": {
                "websocket": ws_mock,
                "capabilities": ["notification"],
                "platform": "android",
                "pending": {},
            }
        }

        from vera.brain.agents.mobile import _send_to_mobile

        async def patched_send(msg):
            cmd_id = msg["id"]
            pending_future = sessions["mobile-1"]["pending"].get(cmd_id)
            if pending_future and not pending_future.done():
                pending_future.set_result({"success": True, "data": {"key": "value"}})

        ws_mock.send_json = patched_send

        result = await _send_to_mobile(sessions, "notification", {"title": "Test"}, timeout=2)
        assert result["status"] == "success"
        assert result["data"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_timeout(self):
        ws_mock = AsyncMock()
        ws_mock.send_json = AsyncMock()

        sessions = {
            "mobile-1": {
                "websocket": ws_mock,
                "capabilities": [],
                "platform": "ios",
                "pending": {},
            }
        }

        from vera.brain.agents.mobile import _send_to_mobile
        result = await _send_to_mobile(sessions, "slow_cmd", timeout=0.1)
        assert result["status"] == "error"
        assert "timed out" in result["message"].lower()


class TestMobileTools:
    def test_notification_tool(self):
        from vera.brain.agents.mobile import SendNotificationTool
        tool = SendNotificationTool()
        assert tool.name == "send_mobile_notification"

    def test_open_app_tool(self):
        from vera.brain.agents.mobile import OpenAppTool
        tool = OpenAppTool()
        assert tool.name == "open_mobile_app"

    def test_set_alarm_tool(self):
        from vera.brain.agents.mobile import SetAlarmTool
        tool = SetAlarmTool()
        assert tool.name == "set_mobile_alarm"

    def test_toggle_setting_tool(self):
        from vera.brain.agents.mobile import ToggleSettingTool
        tool = ToggleSettingTool()
        assert tool.name == "toggle_mobile_setting"

    def test_clipboard_tool(self):
        from vera.brain.agents.mobile import ClipboardTool
        tool = ClipboardTool()
        assert tool.name == "mobile_clipboard"

    def test_device_info_tool(self):
        from vera.brain.agents.mobile import DeviceInfoTool
        tool = DeviceInfoTool()
        assert tool.name == "mobile_device_info"
