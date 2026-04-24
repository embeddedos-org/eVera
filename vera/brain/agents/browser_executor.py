"""Browser Task Executor — runs planned browser steps with verification.

Executes BrowserPlan steps sequentially, takes screenshots for verification,
retries on failure, and streams progress via callbacks.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from vera.brain.agents.browser_planner import BrowserPlan, BrowserPlanner, BrowserStep
from vera.providers.manager import ProviderManager

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result from executing a single browser step."""

    step_index: int
    action: str
    status: str  # success, failed, skipped, retried
    result: dict[str, Any] = field(default_factory=dict)
    screenshot_b64: str | None = None
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class ExecutionResult:
    """Result from executing a complete browser plan."""

    task_id: str
    task: str
    status: str  # completed, failed, partial
    steps_completed: int = 0
    steps_total: int = 0
    step_results: list[StepResult] = field(default_factory=list)
    total_duration_ms: float = 0.0


class BrowserExecutor:
    """Executes browser automation plans with monitoring and recovery."""

    def __init__(self, provider: ProviderManager) -> None:
        self._provider = provider
        self._planner = BrowserPlanner(provider)
        self._active_tasks: dict[str, ExecutionResult] = {}

    async def execute_plan(
        self,
        plan: BrowserPlan,
        progress_callback: Callable[[StepResult], Any] | None = None,
        max_retries: int = 2,
    ) -> ExecutionResult:
        """Execute a browser plan step by step."""
        from vera.brain.agents.browser import (
            ClickTool,
            ExtractTextTool,
            FillFormTool,
            GoBackTool,
            NavigateTool,
            ScreenshotTool,
            ScrollTool,
            SelectOptionTool,
            TypeTextTool,
        )

        task_id = str(uuid.uuid4())[:8]
        exec_result = ExecutionResult(
            task_id=task_id,
            task=plan.task,
            status="executing",
            steps_total=len(plan.steps),
        )
        self._active_tasks[task_id] = exec_result

        # Map action names to tool instances
        tool_map: dict[str, Any] = {
            "navigate": NavigateTool(),
            "click": ClickTool(),
            "type_text": TypeTextTool(),
            "scroll": ScrollTool(),
            "screenshot": ScreenshotTool(),
            "extract_text": ExtractTextTool(),
            "go_back": GoBackTool(),
            "select_option": SelectOptionTool(),
            "fill_form": FillFormTool(),
            "wait_for_element": WaitForElementTool(),
            "execute_js": ExecuteJSTool(),
        }

        start_time = time.monotonic()

        for i, step in enumerate(plan.steps):
            step_start = time.monotonic()

            tool = tool_map.get(step.action)
            if not tool:
                step_result = StepResult(
                    step_index=i,
                    action=step.action,
                    status="failed",
                    error=f"Unknown action: {step.action}",
                    duration_ms=0,
                )
                exec_result.step_results.append(step_result)

                if step.on_fail == "abort":
                    exec_result.status = "failed"
                    break
                continue

            # Execute with retries
            result = None
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    result = await tool.execute(**step.args)
                    if result.get("status") == "success":
                        break
                    last_error = result.get("message", "Unknown error")
                except Exception as e:
                    last_error = str(e)
                    if attempt < max_retries:
                        await asyncio.sleep(1)

            duration = (time.monotonic() - step_start) * 1000

            # Take verification screenshot
            screenshot_b64 = None
            try:
                ss_tool = tool_map["screenshot"]
                ss_result = await ss_tool.execute()
                screenshot_b64 = ss_result.get("screenshot_b64")
            except Exception:
                pass

            if result and result.get("status") == "success":
                step_result = StepResult(
                    step_index=i,
                    action=step.action,
                    status="success",
                    result=result,
                    screenshot_b64=screenshot_b64,
                    duration_ms=duration,
                )
            else:
                step_result = StepResult(
                    step_index=i,
                    action=step.action,
                    status="failed",
                    result=result or {},
                    screenshot_b64=screenshot_b64,
                    duration_ms=duration,
                    error=last_error,
                )

            exec_result.step_results.append(step_result)
            exec_result.steps_completed = i + 1

            if progress_callback:
                try:
                    await progress_callback(step_result)
                except Exception:
                    pass

            if step_result.status == "failed":
                if step.on_fail == "abort":
                    exec_result.status = "failed"
                    break
                elif step.on_fail == "replan":
                    # Re-plan remaining steps
                    try:
                        new_steps = await self._planner.replan(plan, i, result or {})
                        plan.steps = plan.steps[: i + 1] + new_steps
                        exec_result.steps_total = len(plan.steps)
                    except Exception as e:
                        logger.warning("Re-planning failed: %s", e)
                elif step.on_fail == "skip":
                    continue

        total_duration = (time.monotonic() - start_time) * 1000
        exec_result.total_duration_ms = total_duration

        if exec_result.status == "executing":
            exec_result.status = "completed"

        del self._active_tasks[task_id]
        return exec_result

    async def plan_and_execute(
        self,
        task: str,
        progress_callback: Callable[[StepResult], Any] | None = None,
    ) -> ExecutionResult:
        """Plan and execute a browser task from natural language."""
        plan = await self._planner.plan(task)
        if not plan.steps:
            return ExecutionResult(
                task_id="none",
                task=task,
                status="failed",
                steps_total=0,
            )
        return await self.execute_plan(plan, progress_callback)

    def get_task_status(self, task_id: str) -> ExecutionResult | None:
        return self._active_tasks.get(task_id)


# --- Additional tools referenced by the executor ---


class WaitForElementTool:
    """Wait for an element to appear on the page."""

    name = "wait_for_element"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from vera.brain.agents.browser import _get_page

        selector = kwargs.get("selector", "")
        timeout = kwargs.get("timeout", 10000)

        if not selector:
            return {"status": "error", "message": "No selector provided"}

        try:
            page = await _get_page()
            await page.wait_for_selector(selector, timeout=timeout)
            return {"status": "success", "selector": selector}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ExecuteJSTool:
    """Execute JavaScript on the page."""

    name = "execute_js"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from vera.brain.agents.browser import _get_page

        script = kwargs.get("script", "")
        if not script:
            return {"status": "error", "message": "No script provided"}

        try:
            page = await _get_page()
            result = await page.evaluate(script)
            return {"status": "success", "result": str(result)[:2000] if result else None}
        except Exception as e:
            return {"status": "error", "message": str(e)}
