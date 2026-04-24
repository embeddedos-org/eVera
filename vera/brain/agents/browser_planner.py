"""Browser Task Planner — decomposes natural language into browser steps.

Uses LLM to plan a sequence of browser actions from a user's intent,
mapping each step to existing BrowserAgent tools.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from vera.providers.manager import ProviderManager
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

PLANNING_PROMPT = """You are a browser automation planner. Given the user's task, decompose it into a sequence of browser actions.

Available browser actions (use these exact names):
- navigate: Go to a URL. Args: url, wait_for (load/domcontentloaded/networkidle)
- click: Click an element. Args: target (text/CSS/role), selector_type (text/css/role)
- type_text: Type text into a field. Args: selector (CSS), text, clear_first (bool)
- scroll: Scroll the page. Args: direction (up/down), amount (pixels, default 500)
- screenshot: Take a screenshot. Args: (none)
- extract_text: Get text from page/element. Args: selector (optional CSS)
- wait_for_element: Wait for element. Args: selector (CSS), timeout (ms)
- execute_js: Run JavaScript. Args: script
- go_back: Navigate back. Args: (none)
- select_option: Select from dropdown. Args: selector (CSS), value
- fill_form: Fill multiple fields. Args: fields (dict of selector→value)

For each step, provide:
1. action: The action name from above
2. args: Dictionary of arguments
3. description: Human-readable description
4. verify: Optional verification step (screenshot + expected text)
5. on_fail: What to do if this step fails (retry/skip/abort)

Respond with ONLY a JSON array of steps:
[
  {{"action": "navigate", "args": {{"url": "..."}}, "description": "...", "on_fail": "abort"}},
  ...
]

User task: {task}"""

CONDITIONAL_PROMPT = """The previous step result was:
{result}

Based on this result, do we need to modify the remaining plan? If yes, provide updated remaining steps as JSON array. If no, respond with "CONTINUE".

Remaining steps: {remaining_steps}"""


@dataclass
class BrowserStep:
    """A single planned browser action."""

    action: str
    args: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    verify: str | None = None
    on_fail: str = "abort"  # retry, skip, abort, replan


@dataclass
class BrowserPlan:
    """A complete browser automation plan."""

    task: str
    steps: list[BrowserStep] = field(default_factory=list)
    status: str = "planned"  # planned, executing, completed, failed


class BrowserPlanner:
    """Plans browser automation tasks using LLM."""

    def __init__(self, provider: ProviderManager) -> None:
        self._provider = provider

    async def plan(self, task: str) -> BrowserPlan:
        """Decompose a natural language task into browser steps."""
        prompt = PLANNING_PROMPT.format(task=task)

        result = await self._provider.complete(
            messages=[{"role": "user", "content": prompt}],
            tier=ModelTier.STRATEGIST,
            max_tokens=2048,
            temperature=0.3,
        )

        steps = self._parse_steps(result.content)
        plan = BrowserPlan(task=task, steps=steps)

        logger.info("Planned %d steps for task: %s", len(steps), task[:80])
        return plan

    async def replan(
        self,
        original_plan: BrowserPlan,
        step_index: int,
        step_result: dict[str, Any],
    ) -> list[BrowserStep]:
        """Re-plan remaining steps based on a step's result."""
        remaining = original_plan.steps[step_index + 1 :]
        remaining_json = json.dumps(
            [{"action": s.action, "args": s.args, "description": s.description} for s in remaining]
        )

        prompt = CONDITIONAL_PROMPT.format(
            result=json.dumps(step_result, indent=2)[:1000],
            remaining_steps=remaining_json,
        )

        result = await self._provider.complete(
            messages=[{"role": "user", "content": prompt}],
            tier=ModelTier.SPECIALIST,
            max_tokens=1024,
            temperature=0.3,
        )

        content = result.content.strip()
        if content.upper() == "CONTINUE":
            return remaining

        return self._parse_steps(content)

    def _parse_steps(self, content: str) -> list[BrowserStep]:
        """Parse LLM output into BrowserStep objects."""
        try:
            # Try to extract JSON from response
            content = content.strip()
            if content.startswith("```"):
                # Strip markdown code fences
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            parsed = json.loads(content)
            if not isinstance(parsed, list):
                parsed = [parsed]

            steps = []
            for item in parsed:
                steps.append(
                    BrowserStep(
                        action=item.get("action", ""),
                        args=item.get("args", {}),
                        description=item.get("description", ""),
                        verify=item.get("verify"),
                        on_fail=item.get("on_fail", "abort"),
                    )
                )

            return steps
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse plan: %s", e)
            return []
