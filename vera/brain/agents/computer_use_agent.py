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
        import sys

        try:
            app, args = kw.get("app_name", ""), kw.get("args", "")
            if sys.platform == "win32":
                subprocess.Popen(f"start {app} {args}", shell=True)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", app] + (args.split() if args else []))
            else:
                subprocess.Popen([app] + (args.split() if args else []))
            return {"status": "success", "launched": app}
        except Exception as e:
            return {"status": "error", "message": str(e)}


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
        ]
