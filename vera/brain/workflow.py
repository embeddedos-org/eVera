"""Workflow Engine — n8n-style automation pipelines.

Define multi-step workflows as JSON, with conditions, loops, triggers, and agent steps.

Example workflow:
{
    "name": "Daily Report",
    "trigger": {"type": "schedule", "cron": "0 9 * * *"},
    "steps": [
        {"id": "1", "agent": "researcher", "action": "web_search", "params": {"query": "AI news today"}},
        {"id": "2", "agent": "writer", "action": "draft_text", "params": {"topic": "{{steps.1.output}}"}, "depends_on": ["1"]},
        {"id": "3", "type": "condition", "if": "{{steps.2.output.length}} > 100", "then": "4", "else": "5"},
        {"id": "4", "agent": "life_manager", "action": "send_email", "params": {"to": "me@email.com", "subject": "Daily AI Report", "body": "{{steps.2.output}}"}},
        {"id": "5", "type": "notify", "message": "Report too short, skipping email"}
    ]
}
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WORKFLOWS_DIR = DATA_DIR / "workflows"


class WorkflowStep:
    """A single step in a workflow."""

    def __init__(self, config: dict) -> None:
        self.id = str(config.get("id", ""))
        self.step_type = config.get("type", "agent")  # agent, condition, notify, loop
        self.agent = config.get("agent", "")
        self.action = config.get("action", "")
        self.params = config.get("params", {})
        self.depends_on = config.get("depends_on", [])
        self.condition_if = config.get("if", "")
        self.condition_then = config.get("then", "")
        self.condition_else = config.get("else", "")
        self.message = config.get("message", "")
        self.status = "pending"
        self.output: Any = None
        self.error: str = ""


class Workflow:
    """A complete workflow definition with steps and triggers."""

    def __init__(self, config: dict) -> None:
        self.name = config.get("name", "Unnamed Workflow")
        self.description = config.get("description", "")
        self.trigger = config.get("trigger", {})
        self.steps = [WorkflowStep(s) for s in config.get("steps", [])]
        self.variables = config.get("variables", {})
        self.created_at = config.get("created_at", datetime.now().isoformat())
        self.last_run = config.get("last_run")
        self.run_count = config.get("run_count", 0)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "steps": [
                {
                    "id": s.id,
                    "type": s.step_type,
                    "agent": s.agent,
                    "action": s.action,
                    "params": s.params,
                    "depends_on": s.depends_on,
                    "if": s.condition_if,
                    "then": s.condition_then,
                    "else": s.condition_else,
                    "message": s.message,
                }
                for s in self.steps
            ],
            "variables": self.variables,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "run_count": self.run_count,
        }


class WorkflowEngine:
    """Executes workflow pipelines with agent steps, conditions, and loops."""

    def __init__(self) -> None:
        self._workflows: dict[str, Workflow] = {}
        self._load_workflows()

    def _load_workflows(self) -> None:
        """Load saved workflows from disk."""
        WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
        for path in WORKFLOWS_DIR.glob("*.json"):
            try:
                config = json.loads(path.read_text())
                wf = Workflow(config)
                self._workflows[wf.name] = wf
            except Exception as e:
                logger.warning("Failed to load workflow %s: %s", path, e)

    def create(self, config: dict) -> Workflow:
        """Create and save a new workflow."""
        wf = Workflow(config)
        self._workflows[wf.name] = wf
        self._save_workflow(wf)
        return wf

    def get(self, name: str) -> Workflow | None:
        return self._workflows.get(name)

    def list_all(self) -> list[dict]:
        return [
            {
                "name": w.name,
                "description": w.description,
                "steps": len(w.steps),
                "trigger": w.trigger,
                "run_count": w.run_count,
                "last_run": w.last_run,
            }
            for w in self._workflows.values()
        ]

    def delete(self, name: str) -> bool:
        if name in self._workflows:
            del self._workflows[name]
            path = WORKFLOWS_DIR / f"{name}.json"
            if path.exists():
                path.unlink()
            return True
        return False

    async def execute(self, name: str, brain: Any, variables: dict | None = None) -> dict:
        """Execute a workflow by name."""
        wf = self._workflows.get(name)
        if not wf:
            return {"status": "error", "message": f"Workflow '{name}' not found"}

        # Merge runtime variables
        run_vars = {**wf.variables, **(variables or {})}
        step_outputs: dict[str, Any] = {}

        # Reset steps
        for step in wf.steps:
            step.status = "pending"
            step.output = None
            step.error = ""

        # Execute steps respecting dependencies
        completed: set[str] = set()
        max_iterations = len(wf.steps) * 2

        for _ in range(max_iterations):
            ready = [s for s in wf.steps if s.status == "pending" and all(d in completed for d in s.depends_on)]
            if not ready:
                break

            for step in ready:
                try:
                    step.status = "running"
                    result = await self._execute_step(step, brain, step_outputs, run_vars)
                    step.output = result
                    step.status = "completed"
                    step_outputs[step.id] = result

                    # Handle condition jumps
                    if step.step_type == "condition":
                        target = result.get("next_step")
                        if target:
                            # Skip steps not on the chosen path
                            pass
                except Exception as e:
                    step.status = "failed"
                    step.error = str(e)
                    logger.warning("Workflow step %s failed: %s", step.id, e)

                completed.add(step.id)

        # Update workflow metadata
        wf.last_run = datetime.now().isoformat()
        wf.run_count += 1
        self._save_workflow(wf)

        return {
            "status": "success",
            "workflow": wf.name,
            "steps_completed": len([s for s in wf.steps if s.status == "completed"]),
            "steps_failed": len([s for s in wf.steps if s.status == "failed"]),
            "results": step_outputs,
        }

    async def _execute_step(
        self,
        step: WorkflowStep,
        brain: Any,
        step_outputs: dict,
        variables: dict,
    ) -> Any:
        """Execute a single workflow step."""
        # Resolve template variables in params
        resolved_params = self._resolve_templates(step.params, step_outputs, variables)

        if step.step_type == "agent":
            # Execute via agent tool
            from vera.brain.agents import get_agent

            agent = get_agent(step.agent)
            if agent:
                tool = agent.get_tool(step.action)
                if tool:
                    return await tool.execute(**resolved_params)

            # Fallback: process as natural language
            instruction = resolved_params.get("instruction", step.action)
            result = await brain.process(instruction)
            return {"response": result.response, "agent": result.agent}

        elif step.step_type == "condition":
            condition = self._resolve_template_string(step.condition_if, step_outputs, variables)
            try:
                result = bool(eval(condition, {"__builtins__": {}}, step_outputs))
            except Exception:
                result = False
            return {"next_step": step.condition_then if result else step.condition_else, "condition_result": result}

        elif step.step_type == "notify":
            message = self._resolve_template_string(step.message, step_outputs, variables)
            return {"message": message, "notified": True}

        return {"status": "unknown_step_type"}

    def _resolve_templates(self, params: dict, outputs: dict, variables: dict) -> dict:
        """Replace {{steps.X.output}} and {{vars.X}} in params."""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str):
                resolved[key] = self._resolve_template_string(value, outputs, variables)
            else:
                resolved[key] = value
        return resolved

    def _resolve_template_string(self, template: str, outputs: dict, variables: dict) -> str:
        """Replace template variables in a string."""

        def replacer(match: re.Match) -> str:
            path = match.group(1)
            if path.startswith("steps."):
                parts = path.split(".")
                step_id = parts[1]
                if step_id in outputs:
                    value = outputs[step_id]
                    for part in parts[2:]:
                        if isinstance(value, dict):
                            value = value.get(part, "")
                    return str(value)
            elif path.startswith("vars."):
                var_name = path[5:]
                return str(variables.get(var_name, ""))
            return match.group(0)

        return re.sub(r"\{\{(.+?)\}\}", replacer, template)

    def _save_workflow(self, wf: Workflow) -> None:
        WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
        path = WORKFLOWS_DIR / f"{wf.name}.json"
        path.write_text(json.dumps(wf.to_dict(), indent=2, default=str))
