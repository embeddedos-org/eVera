"""Computer Use Agent -- direct GUI automation, screen control, OCR, clipboard.

Only eVera has this: Claude-level computer use with screenshot analysis,
mouse/keyboard control, OCR, window management, and app launching.
"""

from __future__ import annotations

import logging
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class ScreenshotTool(Tool):
    """Capture screenshots."""

    def __init__(self):
        super().__init__(
            name="take_screenshot",
            description="Capture screenshot of screen or region",
            parameters={
                "region": {"type": "str", "description": "x,y,w,h or empty for full screen"},
                "output": {"type": "str", "description": "Output path"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import pyautogui

            out = kw.get("output", "screenshot.png")
            region = kw.get("region", "")
            img = pyautogui.screenshot(region=tuple(int(x) for x in region.split(",")) if region else None)
            img.save(out)
            return {"status": "success", "output": out, "size": f"{img.width}x{img.height}"}
        except ImportError:
            return {"status": "error", "message": "pip install pyautogui"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class MouseControlTool(Tool):
    """Control mouse cursor."""

    def __init__(self):
        super().__init__(
            name="mouse_control",
            description="Mouse: move/click/double_click/right_click/scroll/drag",
            parameters={
                "action": {"type": "str", "description": "move|click|double_click|right_click|scroll|drag"},
                "x": {"type": "int", "description": "X coord"},
                "y": {"type": "int", "description": "Y coord"},
                "scroll_amount": {"type": "int", "description": "Scroll amount"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        a, x, y = kw.get("action", "click"), kw.get("x", 0), kw.get("y", 0)
        try:
            import pyautogui

            pyautogui.FAILSAFE = True
            if a == "move":
                pyautogui.moveTo(x, y, duration=0.3)
            elif a == "click":
                pyautogui.click(x, y)
            elif a == "double_click":
                pyautogui.doubleClick(x, y)
            elif a == "right_click":
                pyautogui.rightClick(x, y)
            elif a == "scroll":
                pyautogui.scroll(kw.get("scroll_amount", 3), x, y)
            elif a == "drag":
                pyautogui.moveTo(x, y)
                pyautogui.drag(kw.get("drag_to_x", 0) - x, kw.get("drag_to_y", 0) - y, duration=0.5)
            return {"status": "success", "action": a, "pos": f"{x},{y}"}
        except ImportError:
            return {"status": "error", "message": "pip install pyautogui"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class KeyboardControlTool(Tool):
    """Control keyboard."""

    def __init__(self):
        super().__init__(
            name="keyboard_control",
            description="Type text, press keys, hotkeys (Ctrl+C etc)",
            parameters={
                "action": {"type": "str", "description": "type|press|hotkey"},
                "text": {"type": "str", "description": "Text or key name"},
                "keys": {"type": "str", "description": "Comma-separated keys for hotkey"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        a, text, keys = kw.get("action", "type"), kw.get("text", ""), kw.get("keys", "")
        try:
            import pyautogui

            if a == "type":
                pyautogui.write(text)
            elif a == "press":
                pyautogui.press(text)
            elif a == "hotkey":
                pyautogui.hotkey(*[k.strip() for k in keys.split(",")])
            return {"status": "success", "action": a}
        except ImportError:
            return {"status": "error", "message": "pip install pyautogui"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class OCRTool(Tool):
    """Extract text from screen/image via OCR."""

    def __init__(self):
        super().__init__(
            name="ocr_extract",
            description="Extract text from screenshot/image via OCR",
            parameters={
                "image_path": {"type": "str", "description": "Image path or 'screen'"},
                "language": {"type": "str", "description": "OCR language (default eng)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from PIL import Image

            if kw.get("image_path", "screen") == "screen":
                import pyautogui

                img = pyautogui.screenshot()
            else:
                img = Image.open(kw["image_path"])
            try:
                import pytesseract

                text = pytesseract.image_to_string(img, lang=kw.get("language", "eng"))
            except ImportError:
                import easyocr

                reader = easyocr.Reader(["en"])
                img.save("/tmp/_ocr.png")
                text = " ".join([r[1] for r in reader.readtext("/tmp/_ocr.png")])
            return {"status": "success", "text": text.strip(), "length": len(text.strip())}
        except ImportError:
            return {"status": "error", "message": "pip install pytesseract Pillow"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ClipboardTool(Tool):
    """Read/write system clipboard."""

    def __init__(self):
        super().__init__(
            name="clipboard",
            description="Read/write system clipboard",
            parameters={
                "action": {"type": "str", "description": "read|write|clear"},
                "text": {"type": "str", "description": "Text to write"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import pyperclip

            a = kw.get("action", "read")
            if a == "read":
                return {"status": "success", "content": pyperclip.paste()[:5000]}
            elif a == "write":
                pyperclip.copy(kw.get("text", ""))
                return {"status": "success", "action": "written"}
            elif a == "clear":
                pyperclip.copy("")
                return {"status": "success", "action": "cleared"}
        except ImportError:
            return {"status": "error", "message": "pip install pyperclip"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class FindOnScreenTool(Tool):
    """Find image template on screen."""

    def __init__(self):
        super().__init__(
            name="find_on_screen",
            description="Find image template on screen",
            parameters={
                "image_path": {"type": "str", "description": "Template image path"},
                "confidence": {"type": "float", "description": "Match confidence 0-1"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import pyautogui

            loc = pyautogui.locateOnScreen(kw["image_path"], confidence=kw.get("confidence", 0.8))
            if loc:
                c = pyautogui.center(loc)
                return {"status": "success", "found": True, "x": c.x, "y": c.y}
            return {"status": "success", "found": False}
        except ImportError:
            return {"status": "error", "message": "pip install pyautogui opencv-python"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class WindowManagerTool(Tool):
    """Manage application windows."""

    def __init__(self):
        super().__init__(
            name="window_manager",
            description="List/focus/minimize/maximize/close windows",
            parameters={
                "action": {"type": "str", "description": "list|focus|minimize|maximize|close"},
                "title": {"type": "str", "description": "Window title"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import pygetwindow as gw

            a, t = kw.get("action", "list"), kw.get("title", "")
            if a == "list":
                return {
                    "status": "success",
                    "windows": [{"title": w.title} for w in gw.getAllWindows() if w.title.strip()],
                }
            ws = gw.getWindowsWithTitle(t)
            if not ws:
                return {"status": "error", "message": f"Window '{t}' not found"}
            w = ws[0]
            if a == "focus":
                w.activate()
            elif a == "minimize":
                w.minimize()
            elif a == "maximize":
                w.maximize()
            elif a == "close":
                w.close()
            return {"status": "success", "action": a, "window": w.title}
        except ImportError:
            return {"status": "error", "message": "pip install PyGetWindow"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class AppLauncherTool(Tool):
    """Launch applications by name."""

    def __init__(self):
        super().__init__(
            name="app_launcher",
            description="Launch application by name",
            parameters={
                "app_name": {"type": "str", "description": "App name"},
                "args": {"type": "str", "description": "Arguments"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import subprocess
        import shlex
        import sys

        try:
            app, args = kw.get("app_name", ""), kw.get("args", "")
            # SECURITY: avoid shell=True; pass argv list and let the OS resolve the app.
            arg_list = shlex.split(args) if args else []
            if sys.platform == "win32":
                # Windows: use the `start` builtin via cmd.exe but pass args as a list
                # to avoid f-string-into-shell command injection.
                subprocess.Popen(["cmd.exe", "/c", "start", "", app, *arg_list], shell=False)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", app, *arg_list], shell=False)
            else:
                subprocess.Popen([app, *arg_list], shell=False)
            return {"status": "success", "launched": app}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class FileManagerTool(Tool):
    """File system operations: list, read, write, copy, move, delete, search."""

    def __init__(self):
        super().__init__(
            name="file_manager",
            description="File operations: list directory, read file, write file, copy, move, delete, search, mkdir",
            parameters={
                "action": {"type": "str", "description": "list|read|write|copy|move|delete|search|mkdir"},
                "path": {"type": "str", "description": "File or directory path"},
                "destination": {"type": "str", "description": "Destination path for copy/move"},
                "content": {"type": "str", "description": "Content to write"},
                "pattern": {"type": "str", "description": "Search pattern (glob or text)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import os
        import shutil
        import glob as _glob

        action = kw.get("action", "list")
        path = kw.get("path", ".")
        try:
            if action == "list":
                entries = []
                for e in sorted(os.scandir(path), key=lambda x: (not x.is_dir(), x.name.lower())):
                    entries.append({"name": e.name, "type": "dir" if e.is_dir() else "file",
                                    "size": e.stat().st_size if e.is_file() else None})
                return {"status": "success", "path": path, "entries": entries[:100]}
            elif action == "read":
                with open(path, "r", errors="replace") as f:
                    content = f.read(8192)
                return {"status": "success", "path": path, "content": content}
            elif action == "write":
                with open(path, "w") as f:
                    f.write(kw.get("content", ""))
                return {"status": "success", "path": path, "written": len(kw.get("content", ""))}
            elif action == "copy":
                dest = kw.get("destination", "")
                shutil.copy2(path, dest)
                return {"status": "success", "copied": path, "to": dest}
            elif action == "move":
                dest = kw.get("destination", "")
                shutil.move(path, dest)
                return {"status": "success", "moved": path, "to": dest}
            elif action == "delete":
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                return {"status": "success", "deleted": path}
            elif action == "mkdir":
                os.makedirs(path, exist_ok=True)
                return {"status": "success", "created": path}
            elif action == "search":
                pattern = kw.get("pattern", "*")
                matches = _glob.glob(os.path.join(path, "**", pattern), recursive=True)[:50]
                return {"status": "success", "matches": matches}
            return {"status": "error", "message": f"Unknown action: {action}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ProcessManagerTool(Tool):
    """List, kill, and inspect running processes."""

    def __init__(self):
        super().__init__(
            name="process_manager",
            description="List running processes, kill by PID or name, get CPU/RAM/disk usage",
            parameters={
                "action": {"type": "str", "description": "list|kill|top"},
                "pid": {"type": "int", "description": "Process ID to kill"},
                "name": {"type": "str", "description": "Process name filter"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import psutil
        except ImportError:
            return {"status": "error", "message": "pip install psutil"}
        action = kw.get("action", "list")
        try:
            if action == "list":
                name_filter = kw.get("name", "").lower()
                procs = []
                for p in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_info"]):
                    try:
                        info = p.info
                        if name_filter and name_filter not in (info["name"] or "").lower():
                            continue
                        procs.append({
                            "pid": info["pid"], "name": info["name"],
                            "status": info["status"],
                            "cpu": info["cpu_percent"],
                            "mem_mb": round(info["memory_info"].rss / 1024 / 1024, 1) if info["memory_info"] else 0,
                        })
                    except Exception:
                        pass
                procs.sort(key=lambda x: x["mem_mb"], reverse=True)
                return {"status": "success", "processes": procs[:50]}
            elif action == "kill":
                pid = kw.get("pid")
                name = kw.get("name", "")
                killed = []
                if pid:
                    psutil.Process(int(pid)).terminate()
                    killed.append(pid)
                elif name:
                    for p in psutil.process_iter(["pid", "name"]):
                        if name.lower() in (p.info["name"] or "").lower():
                            p.terminate()
                            killed.append(p.info["pid"])
                return {"status": "success", "killed": killed}
            elif action == "top":
                cpu = psutil.cpu_percent(interval=0.5)
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage("/")
                return {
                    "status": "success",
                    "cpu_pct": cpu,
                    "mem_used_gb": round(mem.used / 1e9, 2),
                    "mem_total_gb": round(mem.total / 1e9, 2),
                    "disk_used_gb": round(disk.used / 1e9, 2),
                    "disk_total_gb": round(disk.total / 1e9, 2),
                }
            return {"status": "error", "message": f"Unknown action: {action}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class SystemInfoTool(Tool):
    """Get system information: OS, hardware, network interfaces, battery."""

    def __init__(self):
        super().__init__(
            name="system_info",
            description="Get system info: OS, CPU, RAM, disk, network interfaces, battery, uptime",
            parameters={},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import platform
        import socket
        import time

        try:
            import psutil

            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            net = psutil.net_if_addrs()
            interfaces = {
                iface: [a.address for a in addrs if a.family == socket.AF_INET]
                for iface, addrs in net.items()
            }
            battery = None
            try:
                b = psutil.sensors_battery()
                if b:
                    battery = {"percent": b.percent, "plugged": b.power_plugged}
            except Exception:
                pass
            return {
                "status": "success",
                "os": platform.system(),
                "os_version": platform.version(),
                "hostname": socket.gethostname(),
                "cpu": platform.processor(),
                "cpu_cores": psutil.cpu_count(),
                "cpu_pct": psutil.cpu_percent(interval=0.3),
                "ram_total_gb": round(mem.total / 1e9, 2),
                "ram_used_gb": round(mem.used / 1e9, 2),
                "disk_total_gb": round(disk.total / 1e9, 2),
                "disk_used_gb": round(disk.used / 1e9, 2),
                "network_interfaces": interfaces,
                "battery": battery,
                "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
            }
        except ImportError:
            return {
                "status": "success",
                "os": platform.system(),
                "os_version": platform.version(),
                "hostname": socket.gethostname(),
                "cpu": platform.processor(),
            }


class ComputerUseAgent(BaseAgent):
    """Direct GUI automation -- screen control, OCR, clipboard, windows."""

    name = "computer_use"
    description = "GUI automation: screenshots, mouse/keyboard, OCR, clipboard, window management, app launcher"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's Computer Use Agent. Take screenshots, control mouse/keyboard, extract text via OCR, manage clipboard, find images on screen, manage windows, launch apps."
    offline_responses = {
        "screenshot": "\U0001f4f8 Capturing!",
        "click": "\U0001f5b1 Clicking!",
        "type": "\u2328 Typing!",
        "open": "\U0001f680 Opening!",
    }

    def _setup_tools(self):
        self._tools = [
            ScreenshotTool(),
            MouseControlTool(),
            KeyboardControlTool(),
            OCRTool(),
            ClipboardTool(),
            FindOnScreenTool(),
            WindowManagerTool(),
            AppLauncherTool(),
            FileManagerTool(),
            ProcessManagerTool(),
            SystemInfoTool(),
        ]


# ---------------------------------------------------------------------------
# Audio Control
# ---------------------------------------------------------------------------

class AudioControlTool(Tool):
    """Control system audio: volume, mute, list devices."""

    def __init__(self):
        super().__init__(
            name="audio_control",
            description="Control system audio: get/set volume, mute/unmute, list audio devices",
            parameters={
                "action": {"type": "str", "description": "get_volume|set_volume|mute|unmute|toggle_mute|list_devices"},
                "volume": {"type": "int", "description": "Volume level 0-100"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import platform
        import subprocess
        action = kw.get("action", "get_volume")
        _os = platform.system()
        try:
            if _os == "Linux":
                if action == "get_volume":
                    r = subprocess.run(["amixer", "get", "Master"], capture_output=True, text=True)
                    import re
                    m = re.search(r"\[(\d+)%\]", r.stdout)
                    vol = int(m.group(1)) if m else None
                    muted = "[off]" in r.stdout
                    return {"status": "success", "volume": vol, "muted": muted}
                elif action == "set_volume":
                    vol = kw.get("volume", 50)
                    subprocess.run(["amixer", "set", "Master", f"{vol}%"])
                    return {"status": "success", "volume": vol}
                elif action == "mute":
                    subprocess.run(["amixer", "set", "Master", "mute"])
                    return {"status": "success", "muted": True}
                elif action == "unmute":
                    subprocess.run(["amixer", "set", "Master", "unmute"])
                    return {"status": "success", "muted": False}
                elif action == "toggle_mute":
                    subprocess.run(["amixer", "set", "Master", "toggle"])
                    return {"status": "success"}
                elif action == "list_devices":
                    r = subprocess.run(["pactl", "list", "sinks", "short"], capture_output=True, text=True)
                    return {"status": "success", "devices": r.stdout}
            elif _os == "Darwin":
                if action == "get_volume":
                    r = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"], capture_output=True, text=True)
                    vol = int(r.stdout.strip()) if r.stdout.strip().isdigit() else None
                    return {"status": "success", "volume": vol}
                elif action == "set_volume":
                    vol = kw.get("volume", 50)
                    subprocess.run(["osascript", "-e", f"set volume output volume {vol}"])
                    return {"status": "success", "volume": vol}
                elif action == "mute":
                    subprocess.run(["osascript", "-e", "set volume with output muted"])
                    return {"status": "success", "muted": True}
                elif action == "unmute":
                    subprocess.run(["osascript", "-e", "set volume without output muted"])
                    return {"status": "success", "muted": False}
            elif _os == "Windows":
                try:
                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
                    from ctypes import cast, POINTER
                    from comtypes import CLSCTX_ALL  # type: ignore
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    volume = cast(interface, POINTER(IAudioEndpointVolume))
                    if action == "get_volume":
                        return {"status": "success", "volume": int(volume.GetMasterVolumeLevelScalar() * 100), "muted": bool(volume.GetMute())}
                    elif action == "set_volume":
                        volume.SetMasterVolumeLevelScalar(int(kw.get("volume", 50)) / 100, None)
                        return {"status": "success", "volume": kw.get("volume")}
                    elif action == "mute":
                        volume.SetMute(1, None)
                        return {"status": "success", "muted": True}
                    elif action == "unmute":
                        volume.SetMute(0, None)
                        return {"status": "success", "muted": False}
                except ImportError:
                    return {"status": "error", "message": "pycaw not installed. Run: pip install pycaw"}
            return {"status": "error", "message": f"Action '{action}' not supported on {_os}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Power Control
# ---------------------------------------------------------------------------

class PowerControlTool(Tool):
    """Sleep, hibernate, shutdown, restart, or lock the screen."""

    def __init__(self):
        super().__init__(
            name="power_control",
            description="Sleep, hibernate, shutdown, restart, lock screen, or get power/battery status",
            parameters={
                "action": {"type": "str", "description": "sleep|hibernate|shutdown|restart|lock|status|cancel_shutdown"},
                "delay_seconds": {"type": "int", "description": "Delay before action (default 0)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import platform
        import subprocess
        _os = platform.system()
        action = kw.get("action", "status")
        delay = int(kw.get("delay_seconds", 0))
        try:
            if action == "status":
                try:
                    import psutil
                    bat = psutil.sensors_battery()
                    return {
                        "status": "success",
                        "battery_percent": bat.percent if bat else None,
                        "plugged_in": bat.power_plugged if bat else None,
                        "platform": _os,
                    }
                except ImportError:
                    return {"status": "success", "platform": _os}
            if _os == "Linux":
                cmds = {
                    "sleep": ["systemctl", "suspend"],
                    "hibernate": ["systemctl", "hibernate"],
                    "shutdown": ["shutdown", "-h", "now"],
                    "restart": ["shutdown", "-r", "now"],
                    "lock": ["loginctl", "lock-session"],
                    "cancel_shutdown": ["shutdown", "-c"],
                }
            elif _os == "Darwin":
                cmds = {
                    "sleep": ["pmset", "sleepnow"],
                    "shutdown": ["shutdown", "-h", "now"],
                    "restart": ["shutdown", "-r", "now"],
                    "lock": ["osascript", "-e", 'tell application "System Events" to keystroke "q" using {command down, control down}'],
                }
            elif _os == "Windows":
                cmds = {
                    "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                    "hibernate": ["shutdown", "/h"],
                    "shutdown": ["shutdown", "/s", "/t", str(delay)],
                    "restart": ["shutdown", "/r", "/t", str(delay)],
                    "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
                    "cancel_shutdown": ["shutdown", "/a"],
                }
            else:
                return {"status": "error", "message": f"Unsupported OS: {_os}"}
            if action not in cmds:
                return {"status": "error", "message": f"Action '{action}' not supported on {_os}"}
            r = subprocess.run(cmds[action], capture_output=True, text=True)
            return {"status": "success" if r.returncode == 0 else "error", "action": action, "message": r.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Desktop Notification
# ---------------------------------------------------------------------------

class NotificationTool(Tool):
    """Send a desktop notification."""

    def __init__(self):
        super().__init__(
            name="notify",
            description="Send a desktop notification to the user",
            parameters={
                "title": {"type": "str", "description": "Notification title"},
                "message": {"type": "str", "description": "Notification body"},
                "urgency": {"type": "str", "description": "low|normal|critical"},
                "duration": {"type": "int", "description": "Duration in seconds (default 5)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import platform
        import subprocess
        _os = platform.system()
        title = kw.get("title", "eVera")
        message = kw.get("message", "")
        urgency = kw.get("urgency", "normal")
        duration = int(kw.get("duration", 5))
        try:
            if _os == "Linux":
                r = subprocess.run(["notify-send", "-u", urgency, "-t", str(duration * 1000), title, message], capture_output=True)
                return {"status": "success" if r.returncode == 0 else "error"}
            elif _os == "Darwin":
                script = f'display notification "{message}" with title "{title}"'
                r = subprocess.run(["osascript", "-e", script], capture_output=True)
                return {"status": "success" if r.returncode == 0 else "error"}
            elif _os == "Windows":
                try:
                    from win10toast import ToastNotifier  # type: ignore
                    ToastNotifier().show_toast(title, message, duration=duration)
                    return {"status": "success"}
                except ImportError:
                    ps = f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show("{message}", "{title}")'
                    subprocess.Popen(["powershell", "-Command", ps])
                    return {"status": "success", "method": "messagebox"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Service Manager
# ---------------------------------------------------------------------------

class ServiceManagerTool(Tool):
    """Manage system services (systemd / launchd / Windows Services)."""

    def __init__(self):
        super().__init__(
            name="service_manager",
            description="List, start, stop, restart, enable, or disable system services",
            parameters={
                "action": {"type": "str", "description": "list|status|start|stop|restart|enable|disable"},
                "service": {"type": "str", "description": "Service name"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import platform
        import subprocess
        _os = platform.system()
        action = kw.get("action", "list")
        service = kw.get("service", "")
        try:
            if _os == "Linux":
                if action == "list":
                    r = subprocess.run(["systemctl", "list-units", "--type=service", "--no-pager", "--plain"], capture_output=True, text=True)
                    return {"status": "success", "services": r.stdout[:3000]}
                else:
                    r = subprocess.run(["systemctl", action, service], capture_output=True, text=True)
                    return {"status": "success" if r.returncode == 0 else "error", "output": r.stdout + r.stderr}
            elif _os == "Darwin":
                if action == "list":
                    r = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
                    return {"status": "success", "services": r.stdout[:3000]}
                elif action in ("start", "stop"):
                    r = subprocess.run(["launchctl", action, service], capture_output=True, text=True)
                    return {"status": "success" if r.returncode == 0 else "error"}
            elif _os == "Windows":
                cmd_map = {
                    "list": ["sc", "query"],
                    "start": ["sc", "start", service],
                    "stop": ["sc", "stop", service],
                    "status": ["sc", "query", service],
                    "restart": ["powershell", "-Command", f"Restart-Service {service}"],
                }
                r = subprocess.run(cmd_map.get(action, ["sc", "query"]), capture_output=True, text=True)
                return {"status": "success", "output": r.stdout[:3000]}
            return {"status": "error", "message": f"Unsupported OS: {_os}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Network Control
# ---------------------------------------------------------------------------

class NetworkControlTool(Tool):
    """Manage network: interfaces, WiFi, ping, traceroute, DNS, firewall."""

    def __init__(self):
        super().__init__(
            name="network_control",
            description="List network interfaces, WiFi networks, connect/disconnect WiFi, ping, traceroute, check firewall",
            parameters={
                "action": {"type": "str", "description": "list_interfaces|wifi_list|wifi_connect|wifi_disconnect|get_ip|ping|traceroute|firewall_status|dns_lookup"},
                "interface": {"type": "str", "description": "Network interface name"},
                "ssid": {"type": "str", "description": "WiFi network name"},
                "password": {"type": "str", "description": "WiFi password"},
                "host": {"type": "str", "description": "Host to ping/traceroute/lookup"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import platform
        import subprocess
        import socket
        _os = platform.system()
        action = kw.get("action", "list_interfaces")
        try:
            if action == "list_interfaces":
                try:
                    import psutil
                    interfaces = {}
                    for name, addrs in psutil.net_if_addrs().items():
                        interfaces[name] = [{"family": a.family.name, "address": a.address} for a in addrs]
                    return {"status": "success", "interfaces": interfaces}
                except ImportError:
                    r = subprocess.run(["ip", "addr"] if _os == "Linux" else ["ifconfig"], capture_output=True, text=True)
                    return {"status": "success", "output": r.stdout[:3000]}

            elif action == "wifi_list":
                if _os == "Linux":
                    r = subprocess.run(["nmcli", "dev", "wifi", "list"], capture_output=True, text=True)
                    return {"status": "success", "networks": r.stdout}
                elif _os == "Darwin":
                    r = subprocess.run(["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-s"], capture_output=True, text=True)
                    return {"status": "success", "networks": r.stdout}
                elif _os == "Windows":
                    r = subprocess.run(["netsh", "wlan", "show", "networks"], capture_output=True, text=True)
                    return {"status": "success", "networks": r.stdout}

            elif action == "wifi_connect":
                ssid, password = kw.get("ssid", ""), kw.get("password", "")
                if _os == "Linux":
                    r = subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password], capture_output=True, text=True)
                    return {"status": "success" if r.returncode == 0 else "error", "output": r.stdout}
                elif _os == "Windows":
                    r = subprocess.run(["netsh", "wlan", "connect", f"name={ssid}"], capture_output=True, text=True)
                    return {"status": "success" if r.returncode == 0 else "error"}

            elif action == "get_ip":
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                return {"status": "success", "hostname": hostname, "local_ip": local_ip}

            elif action == "ping":
                host = kw.get("host", "8.8.8.8")
                count_flag = "-c" if _os != "Windows" else "-n"
                r = subprocess.run(["ping", count_flag, "4", host], capture_output=True, text=True, timeout=15)
                return {"status": "success", "output": r.stdout, "reachable": r.returncode == 0}

            elif action == "traceroute":
                host = kw.get("host", "8.8.8.8")
                cmd = "traceroute" if _os != "Windows" else "tracert"
                r = subprocess.run([cmd, host], capture_output=True, text=True, timeout=30)
                return {"status": "success", "output": r.stdout}

            elif action == "dns_lookup":
                host = kw.get("host", "")
                try:
                    ip = socket.gethostbyname(host)
                    return {"status": "success", "host": host, "ip": ip}
                except socket.gaierror as e:
                    return {"status": "error", "message": str(e)}

            elif action == "firewall_status":
                if _os == "Linux":
                    r = subprocess.run(["ufw", "status"], capture_output=True, text=True)
                    return {"status": "success", "output": r.stdout}
                elif _os == "Darwin":
                    r = subprocess.run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"], capture_output=True, text=True)
                    return {"status": "success", "output": r.stdout}
                elif _os == "Windows":
                    r = subprocess.run(["netsh", "advfirewall", "show", "allprofiles"], capture_output=True, text=True)
                    return {"status": "success", "output": r.stdout}

            return {"status": "error", "message": f"Unknown action: {action}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Terminal Executor
# ---------------------------------------------------------------------------

class TerminalExecTool(Tool):
    """Execute any shell command on the computer."""

    def __init__(self):
        super().__init__(
            name="terminal_exec",
            description="Execute any shell command or script on the computer and return the output",
            parameters={
                "command": {"type": "str", "description": "Shell command to execute"},
                "working_dir": {"type": "str", "description": "Working directory (optional)"},
                "timeout": {"type": "int", "description": "Timeout in seconds (default 30)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import subprocess
        command = kw.get("command", "")
        if not command:
            return {"status": "error", "message": "command is required"}
        working_dir = kw.get("working_dir") or None
        timeout = int(kw.get("timeout", 30))
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=working_dir,
            )
            return {
                "status": "success" if result.returncode == 0 else "error",
                "returncode": result.returncode,
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:2000],
                "command": command,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Display Control
# ---------------------------------------------------------------------------

class DisplayControlTool(Tool):
    """Control display: brightness, resolution, list monitors."""

    def __init__(self):
        super().__init__(
            name="display_control",
            description="Control display brightness, list monitors, get/set screen resolution",
            parameters={
                "action": {"type": "str", "description": "get_brightness|set_brightness|list_displays|get_resolution"},
                "brightness": {"type": "int", "description": "Brightness level 0-100"},
                "display": {"type": "str", "description": "Display name or index"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import platform
        import subprocess
        _os = platform.system()
        action = kw.get("action", "list_displays")
        try:
            if action == "get_brightness":
                if _os == "Linux":
                    r = subprocess.run(["brightnessctl", "g"], capture_output=True, text=True)
                    r_max = subprocess.run(["brightnessctl", "m"], capture_output=True, text=True)
                    if r.returncode == 0 and r_max.returncode == 0:
                        pct = round(int(r.stdout.strip()) / int(r_max.stdout.strip()) * 100)
                        return {"status": "success", "brightness": pct}
                return {"status": "error", "message": "brightnessctl not found"}

            elif action == "set_brightness":
                brightness = int(kw.get("brightness", 50))
                if _os == "Linux":
                    r = subprocess.run(["brightnessctl", "s", f"{brightness}%"], capture_output=True, text=True)
                    return {"status": "success" if r.returncode == 0 else "error", "brightness": brightness}
                elif _os == "Darwin":
                    # Use osascript to set brightness via System Preferences
                    r = subprocess.run(["osascript", "-e", f"tell application \"System Events\" to set value of slider 1 of group 1 of tab group 1 of window 1 of application process \"System Preferences\" to {brightness / 100}"], capture_output=True, text=True)
                    return {"status": "success", "brightness": brightness}

            elif action == "list_displays":
                if _os == "Linux":
                    r = subprocess.run(["xrandr", "--query"], capture_output=True, text=True)
                    return {"status": "success", "output": r.stdout}
                elif _os == "Darwin":
                    r = subprocess.run(["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True)
                    return {"status": "success", "output": r.stdout[:2000]}
                elif _os == "Windows":
                    r = subprocess.run(["powershell", "-Command", "Get-WmiObject -Class Win32_VideoController | Select-Object Name,CurrentHorizontalResolution,CurrentVerticalResolution | ConvertTo-Json"], capture_output=True, text=True)
                    return {"status": "success", "output": r.stdout}

            elif action == "get_resolution":
                try:
                    import pyautogui
                    size = pyautogui.size()
                    return {"status": "success", "width": size.width, "height": size.height}
                except ImportError:
                    if _os == "Linux":
                        r = subprocess.run(["xdpyinfo"], capture_output=True, text=True)
                        import re
                        m = re.search(r"dimensions:\s+(\d+x\d+)", r.stdout)
                        return {"status": "success", "resolution": m.group(1) if m else "unknown"}

            return {"status": "error", "message": f"Action '{action}' not supported on {_os}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Patch ComputerUseAgent to include all new tools
# ---------------------------------------------------------------------------

# Override _setup_tools to include all deep-control tools
_original_setup = ComputerUseAgent._setup_tools


def _enhanced_setup(self):
    _original_setup(self)
    self._tools.extend([
        AudioControlTool(),
        PowerControlTool(),
        NotificationTool(),
        ServiceManagerTool(),
        NetworkControlTool(),
        TerminalExecTool(),
        DisplayControlTool(),
    ])


ComputerUseAgent._setup_tools = _enhanced_setup
