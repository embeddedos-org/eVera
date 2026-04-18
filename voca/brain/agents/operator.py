"""Operator Agent — controls PC operations, file management, and automation."""

from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from voca.brain.agents.base import BaseAgent, Tool
from voca.brain.agents.vision import AnalyzeScreenTool, OCRScreenTool, ScreenCaptureTool
from voca.brain.state import VocaState
from voca.providers.models import ModelTier

logger = logging.getLogger(__name__)

SYSTEM = platform.system()  # "Windows", "Linux", "Darwin"

# --- Cross-platform app maps ---

APP_MAP_WINDOWS = {
    "word": "winword", "ms word": "winword", "microsoft word": "winword",
    "excel": "excel", "ms excel": "excel",
    "powerpoint": "powerpnt", "ms powerpoint": "powerpnt",
    "notepad": "notepad", "calculator": "calc", "calc": "calc",
    "paint": "mspaint", "chrome": "chrome", "google chrome": "chrome",
    "firefox": "firefox", "edge": "msedge", "microsoft edge": "msedge",
    "explorer": "explorer", "file explorer": "explorer",
    "outlook": "outlook", "teams": "msteams", "microsoft teams": "msteams",
    "code": "code", "vscode": "code", "vs code": "code",
    "terminal": "wt", "windows terminal": "wt", "cmd": "cmd",
    "command prompt": "cmd", "powershell": "powershell",
    "spotify": "spotify", "discord": "discord", "slack": "slack", "zoom": "zoom",
    "task manager": "taskmgr", "settings": "ms-settings:",
    "control panel": "control", "snipping tool": "snippingtool",
}

APP_MAP_LINUX = {
    "files": "nautilus", "file manager": "nautilus",
    "terminal": "gnome-terminal", "code": "code", "vscode": "code", "vs code": "code",
    "chrome": "google-chrome", "google chrome": "google-chrome",
    "firefox": "firefox", "calculator": "gnome-calculator", "calc": "gnome-calculator",
    "settings": "gnome-control-center", "text editor": "gedit", "notepad": "gedit",
    "spotify": "spotify", "discord": "discord", "slack": "slack", "zoom": "zoom",
    "libreoffice": "libreoffice", "writer": "libreoffice --writer",
    "spreadsheet": "libreoffice --calc",
}

APP_MAP_MACOS = {
    "finder": "Finder", "terminal": "Terminal", "safari": "Safari",
    "chrome": "Google Chrome", "google chrome": "Google Chrome",
    "firefox": "Firefox", "code": "Visual Studio Code", "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code", "notes": "Notes", "calculator": "Calculator",
    "calc": "Calculator", "settings": "System Preferences", "preferences": "System Preferences",
    "mail": "Mail", "calendar": "Calendar", "music": "Music", "spotify": "Spotify",
    "discord": "Discord", "slack": "Slack", "zoom": "zoom.us",
    "word": "Microsoft Word", "excel": "Microsoft Excel", "powerpoint": "Microsoft PowerPoint",
    "teams": "Microsoft Teams", "outlook": "Microsoft Outlook",
    "pages": "Pages", "numbers": "Numbers", "keynote": "Keynote",
    "preview": "Preview", "photos": "Photos",
}

APP_MAP = {
    "Windows": APP_MAP_WINDOWS,
    "Linux": APP_MAP_LINUX,
    "Darwin": APP_MAP_MACOS,
}.get(SYSTEM, APP_MAP_WINDOWS)


# --- Concrete tool implementations ---

class OpenAppTool(Tool):
    """Open an application by name."""

    def __init__(self) -> None:
        super().__init__(
            name="open_application",
            description="Open an application by name",
            parameters={"app_name": {"type": "str", "description": "Name of the application to open"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        app_name = kwargs.get("app_name", "").lower().strip()
        if not app_name:
            return {"status": "error", "message": "No app name provided"}

        # Sanitize: only allow alphanumeric, spaces, and hyphens
        import re as _re
        if not _re.match(r'^[a-z0-9 \-]+$', app_name):
            return {"status": "error", "message": "Invalid app name characters"}

        exe = APP_MAP.get(app_name)

        try:
            if SYSTEM == "Windows":
                if exe:
                    if exe.startswith("ms-"):
                        subprocess.Popen(["start", exe], shell=True)
                    else:
                        os.startfile(exe)
                else:
                    subprocess.Popen(["start", app_name], shell=True)
            elif SYSTEM == "Darwin":
                target = exe or app_name
                subprocess.Popen(["open", "-a", target])
            else:  # Linux
                target = exe or app_name
                parts = target.split()
                subprocess.Popen(parts, start_new_session=True)

            return {"status": "success", "opened": exe or app_name}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ExecuteScriptTool(Tool):
    """Execute a shell command or script."""

    def __init__(self) -> None:
        super().__init__(
            name="execute_script",
            description="Execute a shell command or script safely",
            parameters={
                "command": {"type": "str", "description": "Shell command to execute"},
                "language": {"type": "str", "description": "Language: shell, python, powershell (default: shell)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        command = kwargs.get("command", kwargs.get("script", ""))
        language = kwargs.get("language", "shell").lower()

        if not command:
            return {"status": "error", "message": "No command provided"}

        # Safety: comprehensive dangerous pattern blocking
        dangerous_patterns = [
            "rm -rf", "rm -fr", "rmdir /s", "del /s", "del /f", "del /q",
            "format c:", "format d:", "mkfs", "dd if=", ":()", "fork bomb",
            "> /dev/sda", "shred", "wipefs",
            "curl|bash", "curl|sh", "wget|bash", "wget|sh",
            "|bash", "|sh", "|powershell",
            "base64 -d|", "base64 --decode|",
            "nc -e", "ncat -e", "netcat",
            "chmod 777 /", "chown root",
            "shutdown", "reboot", "halt", "init 0", "init 6",
            "reg delete", "reg add",
            "bcdedit", "bootrec",
            "Remove-Item C:\\", "Remove-Item -Recurse -Force C:\\",
        ]
        lower_cmd = command.lower().replace(" ", "")
        for d in dangerous_patterns:
            if d.replace(" ", "") in lower_cmd:
                return {"status": "denied", "message": "Blocked potentially dangerous command pattern. Ask the user to run it manually."}

        # Block shell metacharacter injection for non-shell languages
        if language in ("python", "powershell"):
            # Check for obvious injection attempts
            shell_chars = [";", "&&", "||", "`", "$("]
            for char in shell_chars:
                if char in command and language == "python":
                    return {"status": "denied", "message": f"Suspicious character '{char}' in Python command"}

        try:
            import shlex

            if language == "python":
                result = subprocess.run(
                    ["python", "-c", command],
                    capture_output=True, text=True, timeout=30,
                )
            elif language == "powershell":
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", command],
                    capture_output=True, text=True, timeout=30,
                )
            else:
                # Use shlex.split to avoid shell=True where possible
                try:
                    cmd_parts = shlex.split(command)
                    result = subprocess.run(
                        cmd_parts,
                        capture_output=True, text=True, timeout=30,
                    )
                except ValueError:
                    # Complex commands that shlex can't parse — use shell with warning
                    result = subprocess.run(
                        command, shell=True,
                        capture_output=True, text=True, timeout=30,
                    )

            output = result.stdout[:2000] if result.stdout else ""
            error = result.stderr[:500] if result.stderr else ""

            return {
                "status": "success" if result.returncode == 0 else "error",
                "exit_code": result.returncode,
                "output": output,
                "error": error,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Command timed out after 30 seconds"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ManageFilesTool(Tool):
    """File operations: copy, move, delete, list, create directory."""

    def __init__(self) -> None:
        super().__init__(
            name="manage_files",
            description="File operations: copy, move, delete, list, mkdir",
            parameters={
                "action": {"type": "str", "description": "Action: copy, move, delete, list, mkdir, info"},
                "path": {"type": "str", "description": "Source file/directory path"},
                "destination": {"type": "str", "description": "Destination path (for copy/move)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "").lower()
        path_str = kwargs.get("path", "")
        dest_str = kwargs.get("destination", "")

        if not path_str:
            return {"status": "error", "message": "No path provided"}

        path = Path(path_str).expanduser()

        try:
            if action == "list":
                if not path.exists():
                    return {"status": "error", "message": f"Path not found: {path}"}
                if path.is_dir():
                    items = [{"name": p.name, "type": "dir" if p.is_dir() else "file", "size": p.stat().st_size if p.is_file() else 0} for p in sorted(path.iterdir())[:50]]
                    return {"status": "success", "path": str(path), "items": items, "count": len(items)}
                return {"status": "success", "path": str(path), "type": "file", "size": path.stat().st_size}

            elif action == "info":
                if not path.exists():
                    return {"status": "error", "message": f"Path not found: {path}"}
                stat = path.stat()
                return {
                    "status": "success", "path": str(path),
                    "exists": True, "is_file": path.is_file(), "is_dir": path.is_dir(),
                    "size": stat.st_size, "name": path.name,
                }

            elif action == "mkdir":
                path.mkdir(parents=True, exist_ok=True)
                return {"status": "success", "created": str(path)}

            elif action == "copy":
                if not dest_str:
                    return {"status": "error", "message": "No destination provided"}
                dest = Path(dest_str).expanduser()
                if path.is_dir():
                    shutil.copytree(str(path), str(dest))
                else:
                    shutil.copy2(str(path), str(dest))
                return {"status": "success", "copied": str(path), "to": str(dest)}

            elif action == "move":
                if not dest_str:
                    return {"status": "error", "message": "No destination provided"}
                dest = Path(dest_str).expanduser()
                shutil.move(str(path), str(dest))
                return {"status": "success", "moved": str(path), "to": str(dest)}

            elif action == "delete":
                if not path.exists():
                    return {"status": "error", "message": f"Path not found: {path}"}
                if path.is_dir():
                    shutil.rmtree(str(path))
                else:
                    path.unlink()
                return {"status": "success", "deleted": str(path)}

            else:
                return {"status": "error", "message": f"Unknown action: {action}. Use: copy, move, delete, list, mkdir, info"}

        except PermissionError:
            return {"status": "error", "message": f"Permission denied: {path}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ScreenshotTool(Tool):
    """Take a screenshot."""

    def __init__(self) -> None:
        super().__init__(
            name="take_screenshot",
            description="Take a screenshot of the screen",
            parameters={"region": {"type": "str", "description": "Region: full, selection (default: full)"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            if SYSTEM == "Windows":
                subprocess.Popen(["snippingtool"])
                return {"status": "success", "tool": "Snipping Tool opened"}
            elif SYSTEM == "Darwin":
                subprocess.Popen(["screencapture", "-i", "/tmp/voca_screenshot.png"])
                return {"status": "success", "saved": "/tmp/voca_screenshot.png"}
            else:
                for tool in ["gnome-screenshot", "scrot", "xfce4-screenshooter"]:
                    if shutil.which(tool):
                        subprocess.Popen([tool])
                        return {"status": "success", "tool": tool}
                return {"status": "error", "message": "No screenshot tool found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class TypeTextTool(Tool):
    """Type text using keyboard simulation."""

    def __init__(self) -> None:
        super().__init__(
            name="type_text",
            description="Type text into the currently focused window",
            parameters={"text": {"type": "str", "description": "Text to type"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        text = kwargs.get("text", "")
        if not text:
            return {"status": "error", "message": "No text provided"}

        # Limit text length and block injection characters
        if len(text) > 500:
            return {"status": "error", "message": "Text too long (max 500 chars)"}

        try:
            if SYSTEM == "Windows":
                # Use PowerShell with proper escaping — write text to temp file to avoid injection
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                    f.write(text)
                    tmp_path = f.name
                ps_cmd = (
                    f"Add-Type -AssemblyName System.Windows.Forms; "
                    f"$text = Get-Content -Raw '{tmp_path}'; "
                    f"[System.Windows.Forms.SendKeys]::SendWait($text); "
                    f"Remove-Item '{tmp_path}'"
                )
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=10)
                return {"status": "success", "typed": text[:50]}
            elif SYSTEM == "Darwin":
                subprocess.run(["osascript", "-e",
                    f'tell application "System Events" to keystroke "{text.replace(chr(34), "")}"'], timeout=10)
                return {"status": "success", "typed": text[:50]}
            else:
                if shutil.which("xdotool"):
                    subprocess.run(["xdotool", "type", "--", text], timeout=10)
                    return {"status": "success", "typed": text[:50]}
                return {"status": "error", "message": "xdotool not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class OperatorAgent(BaseAgent):
    """Controls PC operations, file management, and automation."""

    name = "operator"
    description = "Controls PC operations, file management, and automation"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a PC automation operator. You can open apps, execute scripts, "
        "manage files, take screenshots, type text, capture the screen and analyze "
        "what's visible using AI vision. For simple requests like "
        "'open chrome', use tools directly. For complex automation, chain multiple tools. "
        f"Current platform: {SYSTEM}. "
        "When the user asks 'what's on my screen' or 'what do you see', use analyze_screen. "
        "Always confirm destructive operations before proceeding."
    )

    offline_responses = {
        "open_app": "",
        "screenshot": "",
        "manage_files": "I'll help you manage that file! 📁",
        "execute_script": "I'll execute that for you! ⚡",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            OpenAppTool(),
            ExecuteScriptTool(),
            ManageFilesTool(),
            ScreenshotTool(),
            TypeTextTool(),
            ScreenCaptureTool(),
            AnalyzeScreenTool(),
            OCRScreenTool(),
        ]

    async def run(self, state: VocaState) -> VocaState:
        """Handle operator actions — direct execution for simple commands, LLM for complex."""
        transcript = state.get("transcript", "").lower()
        intent = state.get("intent", "")
        user_name = state.get("user_name", "")
        name_part = f", {user_name}" if user_name else ""

        # Direct app opening — no LLM needed
        if intent == "open_app" or re.search(r'\b(?:open|launch|start)\b', transcript):
            app_name = self._extract_app_name(transcript)
            if app_name:
                tool = self.get_tool("open_application")
                result = await tool.execute(app_name=app_name)
                if result.get("status") == "success":
                    state["agent_response"] = f"Done{name_part}! ✅ Opening {app_name} for you! 🚀"
                    state["mood"] = "happy"
                else:
                    state["agent_response"] = f"Hmm{name_part}, couldn't open {app_name} — {result.get('message', 'unknown error')} 😕"
                    state["mood"] = "error"
                state["metadata"] = state.get("metadata", {})
                state["metadata"]["tier_used"] = ModelTier.REFLEX
                state["tool_results"] = [{"tool": "open_application", "result": result}]
                return state

        # Direct screenshot
        if intent == "screenshot" or "screenshot" in transcript:
            tool = self.get_tool("take_screenshot")
            result = await tool.execute()
            if result.get("status") == "success":
                state["agent_response"] = f"Got it{name_part}! 📸 Screenshot tool is ready!"
                state["mood"] = "happy"
            else:
                state["agent_response"] = f"Couldn't take a screenshot{name_part} 😕 {result.get('message', '')}"
                state["mood"] = "error"
            state["metadata"] = state.get("metadata", {})
            state["metadata"]["tier_used"] = ModelTier.REFLEX
            state["tool_results"] = [{"tool": "take_screenshot", "result": result}]
            return state

        # Complex operations — use LLM with tool execution pipeline
        return await super().run(state)

    def _extract_app_name(self, transcript: str) -> str | None:
        """Extract application name from transcript."""
        lower = transcript.lower()
        sorted_apps = sorted(APP_MAP.keys(), key=len, reverse=True)
        for app in sorted_apps:
            if app in lower:
                return app

        # Fallback: remove trigger words and use what's left
        cleaned = re.sub(
            r'\b(?:open|launch|start|run|please|can\s+you|could\s+you|the|a|an|for\s+me)\b',
            '', lower, flags=re.I
        ).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned if cleaned else None
