"""Screen Vision — capture screen and analyze with vision LLM."""

from __future__ import annotations

import base64
import logging
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from voca.brain.agents.base import Tool

logger = logging.getLogger(__name__)

SYSTEM = platform.system()


class ScreenCaptureTool(Tool):
    """Capture a screenshot and return the image path."""

    def __init__(self) -> None:
        super().__init__(
            name="capture_screen",
            description="Capture a screenshot of the current screen",
            parameters={"region": {"type": "str", "description": "Region: full or window (default: full)"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        region = kwargs.get("region", "full")
        screenshot_path = Path(tempfile.gettempdir()) / "voca_screen.png"

        try:
            if SYSTEM == "Windows":
                # Use PowerShell to capture screen
                ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save('{screenshot_path}')
$graphics.Dispose()
$bitmap.Dispose()
"""
                subprocess.run(
                    ["powershell", "-Command", ps_script],
                    capture_output=True, timeout=10,
                )
            elif SYSTEM == "Darwin":
                subprocess.run(
                    ["screencapture", "-x", str(screenshot_path)],
                    capture_output=True, timeout=10,
                )
            else:
                # Linux — try multiple tools
                for cmd in [
                    ["gnome-screenshot", "-f", str(screenshot_path)],
                    ["scrot", str(screenshot_path)],
                    ["import", "-window", "root", str(screenshot_path)],
                ]:
                    try:
                        subprocess.run(cmd, capture_output=True, timeout=10)
                        if screenshot_path.exists():
                            break
                    except FileNotFoundError:
                        continue

            if screenshot_path.exists():
                return {
                    "status": "success",
                    "path": str(screenshot_path),
                    "size": screenshot_path.stat().st_size,
                }
            return {"status": "error", "message": "Screenshot capture failed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class AnalyzeScreenTool(Tool):
    """Analyze a screenshot using a vision-capable LLM."""

    def __init__(self) -> None:
        super().__init__(
            name="analyze_screen",
            description="Analyze what's currently on the screen using AI vision",
            parameters={
                "question": {"type": "str", "description": "What to look for or analyze on screen"},
            },
        )
        self._capture = ScreenCaptureTool()

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        question = kwargs.get("question", "Describe what you see on the screen")

        # First capture the screen
        capture_result = await self._capture.execute()
        if capture_result.get("status") != "success":
            return capture_result

        screenshot_path = capture_result["path"]

        try:
            # Read and encode the image
            with open(screenshot_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Call vision LLM via litellm
            import litellm

            from config import settings

            # Try GPT-4o first (best vision), then Gemini
            vision_models = []
            if settings.llm.openai_api_key:
                vision_models.append("gpt-4o")
            if settings.llm.gemini_api_key:
                vision_models.append("gemini/gemini-2.0-flash")

            if not vision_models:
                return {
                    "status": "error",
                    "message": "No vision-capable LLM configured. Set VOCA_LLM_OPENAI_API_KEY or VOCA_LLM_GEMINI_API_KEY in .env",
                    "screenshot": screenshot_path,
                }

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}",
                            },
                        },
                    ],
                }
            ]

            last_error = None
            for model in vision_models:
                try:
                    response = await litellm.acompletion(
                        model=model,
                        messages=messages,
                        max_tokens=1024,
                    )
                    analysis = response.choices[0].message.content
                    return {
                        "status": "success",
                        "analysis": analysis,
                        "model": model,
                        "screenshot": screenshot_path,
                    }
                except Exception as e:
                    logger.warning("Vision model %s failed: %s", model, e)
                    last_error = e
                    continue

            return {"status": "error", "message": f"All vision models failed: {last_error}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class OCRScreenTool(Tool):
    """Read text from the screen (OCR via vision LLM)."""

    def __init__(self) -> None:
        super().__init__(
            name="read_screen_text",
            description="Read and extract all text visible on the screen",
            parameters={},
        )
        self._analyzer = AnalyzeScreenTool()

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return await self._analyzer.execute(
            question="Extract ALL text visible on the screen. Return it exactly as shown, preserving layout where possible."
        )
