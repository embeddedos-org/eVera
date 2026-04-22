"""Operator Agent — controls PC operations, file management, and automation.

@file vera/brain/agents/operator.py
@brief OperatorAgent with 20 tools for desktop automation, GUI control,
       file management, system administration, and screen vision.

Supports Windows, macOS, and Linux via platform-specific implementations.
Includes mouse/keyboard automation (pyautogui), window management
(pygetwindow), process/service management (psutil), and clipboard access.
"""

from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from config import settings
from vera.brain.agents.base import BaseAgent, Tool
from vera.brain.agents.vision import AnalyzeScreenTool, OCRScreenTool, ScreenCaptureTool
from vera.brain.state import VeraState
from vera.providers.models import ModelTier

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
                        # ms-settings: URIs need cmd /c start — no shell=True
                        subprocess.Popen(["cmd", "/c", "start", "", exe])
                    else:
                        os.startfile(exe)
                else:
                    # Unknown app — only attempt if it passed the regex sanitization above.
                    # Use os.startfile which searches PATH without a shell.
                    try:
                        os.startfile(app_name)
                    except OSError:
                        # Fallback: use cmd /c start with empty title to avoid shell injection
                        subprocess.Popen(["cmd", "/c", "start", "", app_name])
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



# --- Hard-blocked admin commands (never allowed even with admin_enabled) ---
ADMIN_HARD_BLOCK = [
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=/dev/zero",
    ":(){ :|:& };:", "format c:", "> /dev/sda", "shred /dev",
]


class ElevatedScriptTool(Tool):
    """Execute a command with elevated (admin/root) privileges.

    Gated behind VERA_SAFETY_ADMIN_ENABLED.  Commands must match at least one
    pattern in VERA_SAFETY_ADMIN_ALLOWED_COMMANDS (fnmatch).  Every execution
    is logged to the audit file.
    """

    def __init__(self) -> None:
        super().__init__(
            name="elevated_script",
            description="Execute a command with admin/root privileges (sudo / RunAs)",
            parameters={
                "command": {"type": "str", "description": "Command to execute with elevated privileges"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        import fnmatch
        import json as _json
        from datetime import datetime

        command = kwargs.get("command", "")
        if not command:
            return {"status": "error", "message": "No command provided"}

        if not settings.safety.admin_enabled:
            return {"status": "denied", "message": "Admin commands disabled. Set VERA_SAFETY_ADMIN_ENABLED=true"}

        # Hard-block check
        lower = command.lower().strip()
        for blocked in ADMIN_HARD_BLOCK:
            if blocked in lower:
                return {"status": "denied", "message": f"Command matches hard-block pattern: {blocked}"}

        # Whitelist check
        allowed_patterns = settings.safety.admin_allowed_commands
        if allowed_patterns:
            matched = any(fnmatch.fnmatch(command, pat) for pat in allowed_patterns)
            if not matched:
                return {
                    "status": "denied",
                    "message": f"Command not in allowed patterns: {allowed_patterns}",
                }

        # Execute with elevation
        try:
            if SYSTEM in ("Linux", "Darwin"):
                result = subprocess.run(
                    ["sudo", "-S"] + command.split(),
                    capture_output=True, text=True, timeout=60,
                )
            else:
                ps_cmd = f'Start-Process -FilePath "cmd.exe" -ArgumentList "/c {command}" -Verb RunAs -Wait -PassThru'
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True, text=True, timeout=60,
                )

            # Audit log
            audit_entry = {
                "timestamp": datetime.now().isoformat(),
                "command": command,
                "exit_code": result.returncode,
                "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
            }
            audit_path = Path(settings.safety.admin_audit_log)
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            with open(audit_path, "a", encoding="utf-8") as f:
                f.write(_json.dumps(audit_entry) + "\n")

            return {
                "status": "success" if result.returncode == 0 else "error",
                "exit_code": result.returncode,
                "output": (result.stdout or "")[:2000],
                "error": (result.stderr or "")[:500],
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Admin command timed out (60s)"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# --- GUI Tools (tkinter) ---

class ShowMessageBoxTool(Tool):
    """Show an info/warning/error message dialog."""

    def __init__(self) -> None:
        super().__init__(
            name="show_message_box",
            description="Show a native message box dialog (info, warning, or error)",
            parameters={
                "title": {"type": "str", "description": "Dialog title"},
                "message": {"type": "str", "description": "Message text"},
                "level": {"type": "str", "description": "info, warning, or error (default: info)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from vera.utils.gui_runner import run_in_gui_thread
        title = kwargs.get("title", "Vera")
        message = kwargs.get("message", "")
        level = kwargs.get("level", "info").lower()

        def _show():
            import tkinter.messagebox as mb
            if level == "warning":
                mb.showwarning(title, message)
            elif level == "error":
                mb.showerror(title, message)
            else:
                mb.showinfo(title, message)
            return "shown"

        result = await run_in_gui_thread(_show)
        return {"status": "success", "result": result}


class ShowInputDialogTool(Tool):
    """Show an input dialog to get text from the user."""

    def __init__(self) -> None:
        super().__init__(
            name="show_input_dialog",
            description="Show a native input dialog to collect text from the user",
            parameters={
                "title": {"type": "str", "description": "Dialog title"},
                "prompt": {"type": "str", "description": "Prompt text"},
                "input_type": {"type": "str", "description": "string, integer, or float (default: string)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from vera.utils.gui_runner import run_in_gui_thread
        title = kwargs.get("title", "Input")
        prompt = kwargs.get("prompt", "Enter value:")
        input_type = kwargs.get("input_type", "string").lower()

        def _ask():
            import tkinter.simpledialog as sd
            if input_type == "integer":
                return sd.askinteger(title, prompt)
            elif input_type == "float":
                return sd.askfloat(title, prompt)
            return sd.askstring(title, prompt)

        value = await run_in_gui_thread(_ask)
        if value is None:
            return {"status": "cancelled", "value": None}
        return {"status": "success", "value": value}


class ShowFileChooserTool(Tool):
    """Show a file open/save/directory chooser dialog."""

    def __init__(self) -> None:
        super().__init__(
            name="show_file_chooser",
            description="Show a native file chooser dialog (open, save, or directory)",
            parameters={
                "mode": {"type": "str", "description": "open, save, or directory (default: open)"},
                "title": {"type": "str", "description": "Dialog title"},
                "filetypes": {"type": "str", "description": "File type filter e.g. '*.py *.txt' (optional)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from vera.utils.gui_runner import run_in_gui_thread
        mode = kwargs.get("mode", "open").lower()
        title = kwargs.get("title", "Choose file")
        filetypes_str = kwargs.get("filetypes", "")

        ftypes = [("All files", "*.*")]
        if filetypes_str:
            for ext in filetypes_str.split():
                ftypes.insert(0, (ext, ext))

        def _choose():
            import tkinter.filedialog as fd
            if mode == "save":
                return fd.asksaveasfilename(title=title, filetypes=ftypes)
            elif mode == "directory":
                return fd.askdirectory(title=title)
            return fd.askopenfilename(title=title, filetypes=ftypes)

        path = await run_in_gui_thread(_choose)
        if not path:
            return {"status": "cancelled", "path": None}
        return {"status": "success", "path": path}


class ShowProgressBarTool(Tool):
    """Show a progress bar window."""

    def __init__(self) -> None:
        super().__init__(
            name="show_progress_bar",
            description="Show a native progress bar dialog",
            parameters={
                "title": {"type": "str", "description": "Window title"},
                "message": {"type": "str", "description": "Label text"},
                "duration_s": {"type": "int", "description": "Auto-close after N seconds (default: 10)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from vera.utils.gui_runner import run_in_gui_thread
        title = kwargs.get("title", "Progress")
        message = kwargs.get("message", "Working...")
        duration = kwargs.get("duration_s", 10)

        def _progress():
            import tkinter as tk
            from tkinter import ttk
            root = tk.Tk()
            root.title(title)
            root.geometry("400x120")
            root.resizable(False, False)
            tk.Label(root, text=message, font=("Segoe UI", 11)).pack(pady=10)
            bar = ttk.Progressbar(root, mode="indeterminate", length=350)
            bar.pack(pady=5)
            bar.start(15)
            root.after(duration * 1000, root.destroy)
            root.mainloop()
            return "completed"

        result = await run_in_gui_thread(_progress)
        return {"status": "success", "result": result}


class ShowFormTool(Tool):
    """Show a dynamic form from a JSON field specification."""

    def __init__(self) -> None:
        super().__init__(
            name="show_form",
            description="Show a native form dialog with dynamic fields. Returns collected values.",
            parameters={
                "title": {"type": "str", "description": "Form window title"},
                "fields": {"type": "str", "description": 'JSON array of field specs: [{"label":"Name","type":"text"},{"label":"Age","type":"number"}]'},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        import json as _json
        from vera.utils.gui_runner import run_in_gui_thread
        title = kwargs.get("title", "Form")
        fields_raw = kwargs.get("fields", "[]")
        try:
            fields = _json.loads(fields_raw) if isinstance(fields_raw, str) else fields_raw
        except _json.JSONDecodeError:
            return {"status": "error", "message": "Invalid fields JSON"}

        def _form():
            import tkinter as tk
            result = {}
            root = tk.Tk()
            root.title(title)
            entries = {}
            for i, field in enumerate(fields):
                lbl = field.get("label", f"Field {i}")
                tk.Label(root, text=lbl, font=("Segoe UI", 10)).grid(row=i, column=0, padx=10, pady=5, sticky="w")
                ent = tk.Entry(root, width=40)
                ent.grid(row=i, column=1, padx=10, pady=5)
                entries[lbl] = ent

            def _submit():
                nonlocal result
                for lbl, ent in entries.items():
                    result[lbl] = ent.get()
                root.destroy()

            tk.Button(root, text="Submit", command=_submit).grid(row=len(fields), column=0, columnspan=2, pady=10)
            root.mainloop()
            return result

        values = await run_in_gui_thread(_form)
        if not values:
            return {"status": "cancelled", "values": {}}
        return {"status": "success", "values": values}


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
                subprocess.Popen(["screencapture", "-i", "/tmp/vera_screenshot.png"])
                return {"status": "success", "saved": "/tmp/vera_screenshot.png"}
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


# ============================================================
# NEW — Mouse & GUI Automation Tools
# ============================================================

class MouseClickTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="mouse_click", description="Click the mouse at screen coordinates (x, y)", parameters={
            "x": {"type": "int", "description": "X coordinate"}, "y": {"type": "int", "description": "Y coordinate"},
            "button": {"type": "str", "description": "Button: left, right, middle (default: left)"},
            "clicks": {"type": "int", "description": "Number of clicks (1=single, 2=double)"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        x, y = int(kwargs.get("x", 0)), int(kwargs.get("y", 0))
        button = kwargs.get("button", "left").lower()
        clicks = int(kwargs.get("clicks", 1))
        try:
            import pyautogui
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            return {"status": "success", "clicked": {"x": x, "y": y, "button": button, "clicks": clicks}}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class MouseMoveTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="mouse_move", description="Move mouse cursor to screen coordinates", parameters={
            "x": {"type": "int", "description": "X coordinate"}, "y": {"type": "int", "description": "Y coordinate"},
            "duration": {"type": "float", "description": "Movement duration in seconds (default: 0.25)"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            import pyautogui
            pyautogui.moveTo(x=int(kwargs.get("x", 0)), y=int(kwargs.get("y", 0)), duration=float(kwargs.get("duration", 0.25)))
            return {"status": "success", "moved_to": {"x": kwargs.get("x"), "y": kwargs.get("y")}}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class MouseDragTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="mouse_drag", description="Click and drag from (x1,y1) to (x2,y2)", parameters={
            "x1": {"type": "int", "description": "Start X"}, "y1": {"type": "int", "description": "Start Y"},
            "x2": {"type": "int", "description": "End X"}, "y2": {"type": "int", "description": "End Y"},
            "button": {"type": "str", "description": "Mouse button (default: left)"},
            "duration": {"type": "float", "description": "Drag duration in seconds (default: 0.5)"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        x1, y1 = int(kwargs.get("x1", 0)), int(kwargs.get("y1", 0))
        x2, y2 = int(kwargs.get("x2", 0)), int(kwargs.get("y2", 0))
        try:
            import pyautogui
            pyautogui.moveTo(x1, y1)
            pyautogui.drag(x2 - x1, y2 - y1, duration=float(kwargs.get("duration", 0.5)), button=kwargs.get("button", "left"))
            return {"status": "success", "dragged": {"from": [x1, y1], "to": [x2, y2]}}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ScrollTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="scroll", description="Scroll mouse wheel up/down", parameters={
            "amount": {"type": "int", "description": "Scroll amount (positive=up, negative=down)"},
            "x": {"type": "int", "description": "Optional X coordinate"}, "y": {"type": "int", "description": "Optional Y coordinate"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        amount = int(kwargs.get("amount", 3))
        try:
            import pyautogui
            x, y = kwargs.get("x"), kwargs.get("y")
            if x is not None and y is not None:
                pyautogui.scroll(amount, x=int(x), y=int(y))
            else:
                pyautogui.scroll(amount)
            return {"status": "success", "scrolled": "up" if amount > 0 else "down", "amount": abs(amount)}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class HotkeyTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="press_hotkey", description="Press a keyboard shortcut (e.g. Ctrl+C, Alt+Tab)", parameters={
            "keys": {"type": "str", "description": "Key combination separated by + (e.g. 'ctrl+c', 'alt+tab')"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        keys = kwargs.get("keys", "")
        if not keys:
            return {"status": "error", "message": "No keys provided"}
        key_map = {"ctrl": "ctrl", "control": "ctrl", "alt": "alt", "option": "alt", "shift": "shift",
                   "win": "win", "windows": "win", "cmd": "command", "command": "command",
                   "tab": "tab", "enter": "enter", "return": "enter", "esc": "escape",
                   "space": "space", "delete": "delete", "del": "delete", "backspace": "backspace"}
        mapped = [key_map.get(k.strip().lower(), k.strip().lower()) for k in keys.split("+")]
        try:
            import pyautogui
            pyautogui.hotkey(*mapped)
            return {"status": "success", "pressed": keys}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class WindowManageTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="manage_window", description="Manage windows: list, focus, minimize, maximize, close", parameters={
            "action": {"type": "str", "description": "Action: list, focus, minimize, maximize, close"},
            "title": {"type": "str", "description": "Window title (partial match)"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "list").lower()
        title = kwargs.get("title", "")
        try:
            if SYSTEM == "Windows":
                import pygetwindow as gw
                if action == "list":
                    windows = [{"title": w.title} for w in gw.getAllWindows() if w.title.strip()]
                    return {"status": "success", "windows": windows[:30]}
                if not title:
                    return {"status": "error", "message": "Window title required"}
                matches = [w for w in gw.getAllWindows() if title.lower() in w.title.lower()]
                if not matches:
                    return {"status": "error", "message": f"No window matching '{title}'"}
                win = matches[0]
                if action == "focus": win.activate()
                elif action == "minimize": win.minimize()
                elif action == "maximize": win.maximize()
                elif action == "close": win.close()
                return {"status": "success", "action": action, "window": win.title}
            elif SYSTEM == "Darwin":
                if action == "list":
                    result = subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of every process whose visible is true'], capture_output=True, text=True, timeout=10)
                    return {"status": "success", "windows": [a.strip() for a in result.stdout.split(",")][:30]}
                if not title:
                    return {"status": "error", "message": "Window title required"}
                scripts = {"focus": f'tell application "{title}" to activate', "close": f'tell application "{title}" to close first window'}
                if action in scripts:
                    subprocess.run(["osascript", "-e", scripts[action]], timeout=10)
                return {"status": "success", "action": action, "window": title}
            else:
                if action == "list":
                    result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=10)
                    windows = [{"title": " ".join(l.split()[3:])} for l in result.stdout.split("\n") if l.strip()]
                    return {"status": "success", "windows": windows[:30]}
                cmds = {"focus": ["wmctrl", "-a", title], "close": ["wmctrl", "-c", title]}
                if action in cmds:
                    subprocess.run(cmds[action], timeout=10)
                return {"status": "success", "action": action, "window": title}
        except ImportError as e:
            return {"status": "error", "message": f"Missing dependency: {e}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ============================================================
# NEW — System Admin Tools
# ============================================================

class ProcessManagerTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="manage_process", description="List processes, kill by name/PID, get process info", parameters={
            "action": {"type": "str", "description": "Action: list, info, kill"},
            "name": {"type": "str", "description": "Process name filter or target"},
            "pid": {"type": "int", "description": "Process ID"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "list").lower()
        try:
            import psutil
            if action == "list":
                name_filter = kwargs.get("name", "").lower()
                procs = []
                for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                    try:
                        info = p.info
                        if name_filter and name_filter not in info["name"].lower():
                            continue
                        procs.append({"pid": info["pid"], "name": info["name"], "cpu": round(info.get("cpu_percent", 0) or 0, 1), "mem": round(info.get("memory_percent", 0) or 0, 1)})
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                procs.sort(key=lambda p: p.get("cpu", 0), reverse=True)
                return {"status": "success", "processes": procs[:30], "total": len(procs)}
            elif action == "info":
                pid = int(kwargs.get("pid", 0))
                if not pid:
                    return {"status": "error", "message": "PID required"}
                p = psutil.Process(pid)
                return {"status": "success", "pid": pid, "name": p.name(), "cpu": p.cpu_percent(), "mem_mb": round(p.memory_info().rss / 1024**2, 1), "status": p.status()}
            elif action == "kill":
                pid, name = kwargs.get("pid"), kwargs.get("name", "")
                killed = []
                if pid:
                    p = psutil.Process(int(pid)); p.terminate(); killed.append({"pid": int(pid), "name": p.name()})
                elif name:
                    for p in psutil.process_iter(["pid", "name"]):
                        if name.lower() in p.info["name"].lower():
                            p.terminate(); killed.append({"pid": p.info["pid"], "name": p.info["name"]})
                else:
                    return {"status": "error", "message": "Provide PID or name"}
                return {"status": "success", "killed": killed}
            return {"status": "error", "message": f"Unknown action: {action}"}
        except ImportError:
            return {"status": "error", "message": "psutil not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class SystemInfoTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="system_info", description="Get CPU, memory, disk, battery, OS details", parameters={
            "category": {"type": "str", "description": "Category: all, cpu, memory, disk, battery, os (default: all)"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        category = kwargs.get("category", "all").lower()
        try:
            import psutil
            info: dict[str, Any] = {}
            if category in ("all", "os"):
                info["os"] = {"system": SYSTEM, "release": platform.release(), "machine": platform.machine(), "hostname": platform.node()}
            if category in ("all", "cpu"):
                info["cpu"] = {"percent": psutil.cpu_percent(interval=0.5), "cores": psutil.cpu_count(), "physical": psutil.cpu_count(logical=False)}
            if category in ("all", "memory"):
                m = psutil.virtual_memory()
                info["memory"] = {"total_gb": round(m.total / 1024**3, 1), "used_gb": round(m.used / 1024**3, 1), "percent": m.percent}
            if category in ("all", "disk"):
                disks = []
                for part in psutil.disk_partitions():
                    try:
                        u = psutil.disk_usage(part.mountpoint)
                        disks.append({"device": part.device, "total_gb": round(u.total / 1024**3, 1), "free_gb": round(u.free / 1024**3, 1), "percent": u.percent})
                    except (PermissionError, OSError):
                        pass
                info["disk"] = disks
            if category in ("all", "battery"):
                bat = psutil.sensors_battery()
                info["battery"] = {"percent": bat.percent, "plugged": bat.power_plugged} if bat else None
            return {"status": "success", **info}
        except ImportError:
            return {"status": "error", "message": "psutil not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ServiceManagerTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="manage_service", description="List/start/stop/restart system services", parameters={
            "action": {"type": "str", "description": "Action: list, start, stop, restart, status"},
            "name": {"type": "str", "description": "Service name"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action, name = kwargs.get("action", "list").lower(), kwargs.get("name", "")
        try:
            if SYSTEM == "Windows":
                if action == "list":
                    r = subprocess.run(["sc", "query", "state=", "all"], capture_output=True, text=True, timeout=15)
                    return {"status": "success", "output": r.stdout[:2000]}
                if not name:
                    return {"status": "error", "message": "Service name required"}
                cmds = {"start": ["sc", "start", name], "stop": ["sc", "stop", name], "status": ["sc", "query", name]}
                if action == "restart":
                    subprocess.run(["sc", "stop", name], capture_output=True, timeout=15)
                    import time; time.sleep(2)
                    r = subprocess.run(["sc", "start", name], capture_output=True, text=True, timeout=15)
                else:
                    cmd = cmds.get(action)
                    if not cmd:
                        return {"status": "error", "message": f"Unknown action: {action}"}
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                return {"status": "success", "action": action, "service": name, "output": r.stdout[:500]}
            elif SYSTEM == "Linux":
                if action == "list":
                    r = subprocess.run(["systemctl", "list-units", "--type=service", "--no-pager", "-q"], capture_output=True, text=True, timeout=15)
                    return {"status": "success", "output": r.stdout[:2000]}
                if not name:
                    return {"status": "error", "message": "Service name required"}
                cmds = {"start": ["sudo", "systemctl", "start", name], "stop": ["sudo", "systemctl", "stop", name], "restart": ["sudo", "systemctl", "restart", name], "status": ["systemctl", "status", name]}
                cmd = cmds.get(action)
                if not cmd:
                    return {"status": "error", "message": f"Unknown action: {action}"}
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                return {"status": "success", "action": action, "service": name, "output": r.stdout[:500]}
            else:
                if action == "list":
                    r = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=15)
                    return {"status": "success", "output": r.stdout[:2000]}
                if not name:
                    return {"status": "error", "message": "Service name required"}
                cmds = {"start": ["launchctl", "start", name], "stop": ["launchctl", "stop", name], "status": ["launchctl", "list", name]}
                if action == "restart":
                    subprocess.run(["launchctl", "stop", name], capture_output=True, timeout=15)
                    import time; time.sleep(1)
                    r = subprocess.run(["launchctl", "start", name], capture_output=True, text=True, timeout=15)
                else:
                    cmd = cmds.get(action)
                    if not cmd:
                        return {"status": "error", "message": f"Unknown action: {action}"}
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                return {"status": "success", "action": action, "service": name, "output": r.stdout[:500]}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class NetworkInfoTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="network_info", description="Get IP, DNS, connections, ping", parameters={
            "action": {"type": "str", "description": "Action: info, connections, ping"},
            "host": {"type": "str", "description": "Host to ping"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "info").lower()
        try:
            import psutil
            if action == "info":
                addrs = {}
                for iface, snics in psutil.net_if_addrs().items():
                    for snic in snics:
                        if snic.family.name == "AF_INET":
                            addrs[iface] = snic.address
                c = psutil.net_io_counters()
                return {"status": "success", "interfaces": addrs, "sent_mb": round(c.bytes_sent / 1024**2, 1), "recv_mb": round(c.bytes_recv / 1024**2, 1)}
            elif action == "connections":
                conns = [{"local": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "", "remote": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "", "status": c.status} for c in psutil.net_connections(kind="inet")[:20]]
                return {"status": "success", "connections": conns}
            elif action == "ping":
                host = kwargs.get("host", "8.8.8.8")
                flag = "-n" if SYSTEM == "Windows" else "-c"
                r = subprocess.run(["ping", flag, "4", host], capture_output=True, text=True, timeout=15)
                return {"status": "success", "host": host, "output": r.stdout[:500]}
            return {"status": "error", "message": f"Unknown action: {action}"}
        except ImportError:
            return {"status": "error", "message": "psutil not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ClipboardTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="clipboard", description="Read or write system clipboard", parameters={
            "action": {"type": "str", "description": "Action: read, write"},
            "text": {"type": "str", "description": "Text to write (for write action)"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "read").lower()
        try:
            import pyperclip
            if action == "read":
                return {"status": "success", "content": pyperclip.paste()[:2000]}
            elif action == "write":
                text = kwargs.get("text", "")
                if not text:
                    return {"status": "error", "message": "No text provided"}
                pyperclip.copy(text)
                return {"status": "success", "written": text[:100]}
            return {"status": "error", "message": f"Unknown action: {action}"}
        except ImportError:
            return {"status": "error", "message": "pyperclip not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class NotificationTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="send_notification", description="Send OS-level desktop notification", parameters={
            "title": {"type": "str", "description": "Notification title"},
            "message": {"type": "str", "description": "Notification body"},
        })

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        title = kwargs.get("title", "Vera")
        message = kwargs.get("message", "")
        if not message:
            return {"status": "error", "message": "No message provided"}
        try:
            if SYSTEM == "Windows":
                ps = f'Add-Type -AssemblyName System.Windows.Forms; $n = New-Object System.Windows.Forms.NotifyIcon; $n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; $n.ShowBalloonTip(5000, "{title}", "{message}", [System.Windows.Forms.ToolTipIcon]::Info)'
                subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=10)
            elif SYSTEM == "Darwin":
                subprocess.run(["osascript", "-e", f'display notification "{message}" with title "{title}"'], timeout=10)
            else:
                subprocess.run(["notify-send", title, message], timeout=10)
            return {"status": "success", "sent": {"title": title, "message": message[:100]}}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class OperatorAgent(BaseAgent):
    """Controls PC operations, file management, GUI automation, and system admin.

    The Operator is the most tool-rich agent with 20 tools spanning:
    - App launching (cross-platform app maps)
    - Shell command execution (with dangerous pattern blocking)
    - File operations (copy, move, delete, list, mkdir)
    - Mouse automation (click, move, drag, scroll)
    - Keyboard shortcuts (hotkey combos)
    - Window management (list, focus, minimize, maximize, close)
    - Process management (list, info, kill)
    - System info (CPU, memory, disk, battery, OS)
    - Service management (list, start, stop, restart)
    - Network info (IP, connections, ping)
    - Clipboard access (read, write)
    - Desktop notifications
    - Screen capture and AI vision analysis
    """

    name = "operator"
    description = "Controls PC operations, file management, GUI automation, and system admin"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a PC automation operator. You can open apps, execute scripts, "
        "manage files, take screenshots, type text, capture the screen and analyze "
        "what's visible using AI vision. You can also control the mouse (click, move, drag, scroll), "
        "press keyboard shortcuts, manage windows, manage processes, get system info, "
        "manage services, check network, access clipboard, and send notifications. "
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
            # Mouse & GUI automation
            MouseClickTool(),
            MouseMoveTool(),
            MouseDragTool(),
            ScrollTool(),
            HotkeyTool(),
            WindowManageTool(),
            # System admin
            ProcessManagerTool(),
            SystemInfoTool(),
            ServiceManagerTool(),
            NetworkInfoTool(),
            ClipboardTool(),
            NotificationTool(),
            # GUI tools (tkinter)
            ShowMessageBoxTool(),
            ShowInputDialogTool(),
            ShowFileChooserTool(),
            ShowProgressBarTool(),
            ShowFormTool(),
        ]

        # Conditionally add elevated script tool
        if settings.safety.admin_enabled:
            self._tools.append(ElevatedScriptTool())

    async def run(self, state: VeraState) -> VeraState:
        """Handle operator actions — direct execution for simple commands, LLM for complex.

        Simple commands (open_app, screenshot) are executed directly without LLM
        but still go through safety policy verification.
        """
        from vera.safety.policy import PolicyAction, PolicyService

        transcript = state.get("transcript", "").lower()
        intent = state.get("intent", "")
        user_name = state.get("user_name", "")
        name_part = f", {user_name}" if user_name else ""

        policy = PolicyService()

        # Direct app opening — no LLM needed
        if intent == "open_app" or re.search(r'\b(?:open|launch|start)\b', transcript):
            app_name = self._extract_app_name(transcript)
            if app_name:
                decision = policy.check(self.name, "open_application")
                if decision.action == PolicyAction.DENY:
                    state["agent_response"] = f"Sorry{name_part}, I can't open apps right now. {decision.reason}"
                    state["mood"] = "error"
                    return state
                if decision.action == PolicyAction.CONFIRM and not state.get("safety_approved"):
                    state["agent_response"] = (
                        f"Hey{name_part}! I'd like to open {app_name} for you. "
                        "Should I go ahead? 🤔 (yes/no)"
                    )
                    state["mood"] = "thinking"
                    state["needs_confirmation"] = True
                    return state

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
            decision = policy.check(self.name, "take_screenshot")
            if decision.action == PolicyAction.DENY:
                state["agent_response"] = f"Sorry{name_part}, screenshots are not allowed. {decision.reason}"
                state["mood"] = "error"
                return state

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
