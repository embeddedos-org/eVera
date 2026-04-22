"""Mobile Control Agent — sends commands to a connected mobile device via WebSocket.

The mobile app connects to /ws/mobile, registers capabilities, and receives
device_command messages.  This agent provides tools that dispatch commands
and await results through the WebSocket session.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from config import settings
from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

# Timeout for mobile command responses
_MOBILE_CMD_TIMEOUT = settings.mobile.command_timeout_s


async def _send_to_mobile(
    mobile_sessions: dict[str, Any],
    command: str,
    params: dict[str, Any] | None = None,
    timeout: float = _MOBILE_CMD_TIMEOUT,
) -> dict[str, Any]:
    """Find a connected mobile session and send a device_command.

    Returns the device_command_result or an error dict.
    """
    if not mobile_sessions:
        return {"status": "error", "message": "No mobile device connected. Connect via /ws/mobile."}

    # Use first available session
    session_id = next(iter(mobile_sessions))
    session = mobile_sessions[session_id]
    ws = session["websocket"]

    cmd_id = str(uuid.uuid4())[:8]
    future: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
    session.setdefault("pending", {})[cmd_id] = future

    try:
        await ws.send_json({
            "type": "device_command",
            "id": cmd_id,
            "command": command,
            "params": params or {},
        })

        result = await asyncio.wait_for(future, timeout=timeout)
        return {
            "status": "success" if result.get("success") else "error",
            "data": result.get("data"),
            "message": result.get("message", ""),
        }
    except asyncio.TimeoutError:
        session.get("pending", {}).pop(cmd_id, None)
        return {"status": "error", "message": f"Mobile command timed out ({timeout}s)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class SendNotificationTool(Tool):
    """Send a notification to the connected mobile device."""

    def __init__(self) -> None:
        super().__init__(
            name="send_mobile_notification",
            description="Send a push notification to the connected mobile device",
            parameters={
                "title": {"type": "str", "description": "Notification title"},
                "body": {"type": "str", "description": "Notification body text"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return await _send_to_mobile(
            self._mobile_sessions,
            "notification",
            {"title": kwargs.get("title", "Vera"), "body": kwargs.get("body", "")},
        )


class OpenAppTool(Tool):
    """Open an app on the connected mobile device."""

    def __init__(self) -> None:
        super().__init__(
            name="open_mobile_app",
            description="Open an application on the connected mobile device",
            parameters={
                "app_name": {"type": "str", "description": "App name or package ID to open"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return await _send_to_mobile(
            self._mobile_sessions,
            "open_app",
            {"app_name": kwargs.get("app_name", "")},
        )


class SetAlarmTool(Tool):
    """Set an alarm on the connected mobile device."""

    def __init__(self) -> None:
        super().__init__(
            name="set_mobile_alarm",
            description="Set an alarm on the connected mobile device",
            parameters={
                "time": {"type": "str", "description": "Alarm time in HH:MM format"},
                "label": {"type": "str", "description": "Alarm label (optional)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return await _send_to_mobile(
            self._mobile_sessions,
            "set_alarm",
            {"time": kwargs.get("time", ""), "label": kwargs.get("label", "")},
        )


class ToggleSettingTool(Tool):
    """Toggle a setting on the connected mobile device."""

    def __init__(self) -> None:
        super().__init__(
            name="toggle_mobile_setting",
            description="Toggle a device setting (wifi, bluetooth, flashlight, etc.)",
            parameters={
                "setting": {"type": "str", "description": "Setting to toggle: wifi, bluetooth, flashlight, airplane_mode, dnd"},
                "enabled": {"type": "bool", "description": "True to enable, False to disable"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return await _send_to_mobile(
            self._mobile_sessions,
            "toggle_setting",
            {"setting": kwargs.get("setting", ""), "enabled": kwargs.get("enabled", True)},
        )


class ClipboardTool(Tool):
    """Read or write the mobile device clipboard."""

    def __init__(self) -> None:
        super().__init__(
            name="mobile_clipboard",
            description="Read or write the clipboard on the connected mobile device",
            parameters={
                "action": {"type": "str", "description": "read or write"},
                "text": {"type": "str", "description": "Text to write (only for write action)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "read")
        return await _send_to_mobile(
            self._mobile_sessions,
            "clipboard",
            {"action": action, "text": kwargs.get("text", "")},
        )


class DeviceInfoTool(Tool):
    """Get device information from the connected mobile device."""

    def __init__(self) -> None:
        super().__init__(
            name="mobile_device_info",
            description="Get device info (battery, storage, OS, etc.) from the connected mobile device",
            parameters={},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return await _send_to_mobile(
            self._mobile_sessions,
            "device_info",
            {},
        )


class MobileControlAgent(BaseAgent):
    """Controls a connected mobile device via WebSocket commands."""

    name = "mobile_controller"
    description = "Control a connected mobile device: notifications, apps, alarms, settings, clipboard"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a mobile device controller. You can send notifications, "
        "open apps, set alarms, toggle device settings (wifi, bluetooth, "
        "flashlight), read/write the clipboard, and get device info. "
        "The mobile device must be connected via the /ws/mobile WebSocket."
    )

    offline_responses = {
        "notification": "📱 Sending that notification!",
        "alarm": "⏰ Setting an alarm!",
        "open": "📱 Opening that app!",
    }

    def __init__(self, mobile_sessions: dict[str, Any] | None = None) -> None:
        self._mobile_sessions_ref = mobile_sessions or {}
        super().__init__()

    def _setup_tools(self) -> None:
        tools = [
            SendNotificationTool(),
            OpenAppTool(),
            SetAlarmTool(),
            ToggleSettingTool(),
            ClipboardTool(),
            DeviceInfoTool(),
        ]
        # Inject mobile sessions reference into each tool
        for tool in tools:
            tool._mobile_sessions = self._mobile_sessions_ref
        self._tools = tools
