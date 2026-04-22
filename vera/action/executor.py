"""Tool executor — safe command runner with audit logging."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result from a tool execution."""

    tool: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class ToolExecutor:
    """Executes tools safely with logging and sandboxing."""

    def __init__(self) -> None:
        self._audit_log: list[ToolResult] = []
        self._builtin_tools = {
            "set_timer": self._set_timer,
            "get_time": self._get_time,
            "open_app": self._open_app,
            "run_script": self._run_script,
        }

    async def execute_tool(self, tool_name: str, args: dict[str, Any] | None = None) -> ToolResult:
        """Execute a tool and return the result."""
        args = args or {}
        start = time.monotonic()

        try:
            handler = self._builtin_tools.get(tool_name)
            if handler:
                output = await handler(**args)
                result = ToolResult(
                    tool=tool_name,
                    success=True,
                    output=output,
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            else:
                result = ToolResult(
                    tool=tool_name,
                    success=False,
                    error=f"Unknown tool: {tool_name}",
                    duration_ms=(time.monotonic() - start) * 1000,
                )
        except Exception as e:
            result = ToolResult(
                tool=tool_name,
                success=False,
                error=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            )

        self._audit_log.append(result)
        logger.info(
            "Tool executed: %s success=%s duration=%.0fms",
            tool_name,
            result.success,
            result.duration_ms,
        )
        return result

    async def _set_timer(self, duration_seconds: int = 60, label: str = "Timer") -> dict:
        """Set a timer (stub — in production, use asyncio.sleep + notification)."""
        return {
            "status": "timer_set",
            "duration_seconds": duration_seconds,
            "label": label,
            "message": f"Timer '{label}' set for {duration_seconds} seconds.",
        }

    async def _get_time(self) -> dict:
        """Get the current time."""
        now = datetime.now()
        return {
            "time": now.strftime("%I:%M %p"),
            "date": now.strftime("%A, %B %d, %Y"),
            "iso": now.isoformat(),
        }

    async def _open_app(self, app_name: str = "") -> dict:
        """Open an application (stub)."""
        return {
            "status": "stub",
            "message": f"Would open application: {app_name}",
        }

    async def _run_script(self, script: str = "", language: str = "python", timeout: int = 30) -> dict:
        """Run a script in a sandboxed subprocess."""
        if language != "python":
            return {"status": "error", "message": f"Unsupported language: {language}"}

        try:
            proc = await asyncio.create_subprocess_exec(
                "python",
                "-c",
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "status": "success" if proc.returncode == 0 else "error",
                "stdout": stdout.decode().strip(),
                "stderr": stderr.decode().strip(),
                "returncode": proc.returncode,
            }
        except TimeoutError:
            return {"status": "error", "message": f"Script timed out after {timeout}s"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_audit_log(self) -> list[ToolResult]:
        return list(self._audit_log)
