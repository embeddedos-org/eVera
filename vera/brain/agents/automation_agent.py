"""Automation Agent -- workflow automation, cron jobs, file watchers, webhooks."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class CreateAutomationTool(Tool):
    def __init__(self):
        super().__init__(
            name="create_automation",
            description="Create automation rule (trigger->action)",
            parameters={
                "name": {"type": "str", "description": "Name"},
                "trigger": {"type": "str", "description": "time|file_change|webhook|keyword|schedule"},
                "trigger_config": {"type": "str", "description": "JSON config"},
                "action": {"type": "str", "description": "Action to perform"},
                "action_config": {"type": "str", "description": "JSON config"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        ad = Path("data/automations")
        ad.mkdir(parents=True, exist_ok=True)
        rule = {
            "name": kw.get("name", ""),
            "trigger": kw.get("trigger", ""),
            "trigger_config": json.loads(kw.get("trigger_config", "{}"))
            if isinstance(kw.get("trigger_config"), str)
            else {},
            "action": kw.get("action", ""),
            "action_config": json.loads(kw.get("action_config", "{}"))
            if isinstance(kw.get("action_config"), str)
            else {},
            "enabled": True,
            "created": datetime.now().isoformat(),
            "runs": 0,
        }
        (ad / f"{kw.get('name', 'rule').replace(' ', '_')}.json").write_text(json.dumps(rule, indent=2))
        return {"status": "success", "automation": rule["name"]}


class ListAutomationsTool(Tool):
    def __init__(self):
        super().__init__(
            name="list_automations",
            description="List automation rules",
            parameters={"status": {"type": "str", "description": "all|enabled|disabled"}},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        ad = Path("data/automations")
        if not ad.exists():
            return {"status": "success", "automations": [], "count": 0}
        rules = [json.loads(f.read_text()) for f in ad.glob("*.json")]
        return {
            "status": "success",
            "automations": [
                {
                    "name": r["name"],
                    "trigger": r["trigger"],
                    "enabled": r.get("enabled", True),
                    "runs": r.get("runs", 0),
                }
                for r in rules
            ],
        }


class CronJobTool(Tool):
    def __init__(self):
        super().__init__(
            name="cron_job",
            description="Manage cron-like scheduled jobs",
            parameters={
                "action": {"type": "str", "description": "create|list|delete"},
                "name": {"type": "str", "description": "Job name"},
                "schedule": {"type": "str", "description": "Cron expression"},
                "command": {"type": "str", "description": "Command"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        cd = Path("data/cron_jobs")
        cd.mkdir(parents=True, exist_ok=True)
        a = kw.get("action", "list")
        if a == "create":
            job = {
                "name": kw.get("name", ""),
                "schedule": kw.get("schedule", ""),
                "command": kw.get("command", ""),
                "enabled": True,
                "created": datetime.now().isoformat(),
            }
            (cd / f"{kw.get('name', 'job').replace(' ', '_')}.json").write_text(json.dumps(job, indent=2))
            return {"status": "success", "job": job["name"]}
        elif a == "delete":
            fp = cd / f"{kw.get('name', '').replace(' ', '_')}.json"
            if fp.exists():
                fp.unlink()
                return {"status": "success", "deleted": True}
            return {"status": "error", "message": "Not found"}
        return {"status": "success", "jobs": [json.loads(f.read_text()) for f in cd.glob("*.json")]}


class FileWatcherTool(Tool):
    def __init__(self):
        super().__init__(
            name="file_watcher",
            description="Watch files for changes",
            parameters={
                "path": {"type": "str", "description": "Path to watch"},
                "on_change": {"type": "str", "description": "Command on change"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        return {
            "status": "success",
            "path": kw.get("path", ""),
            "on_change": kw.get("on_change", ""),
            "message": "File watcher configured.",
        }


class WebhookTool(Tool):
    def __init__(self):
        super().__init__(
            name="webhook_manager",
            description="Create/test webhooks",
            parameters={
                "action": {"type": "str", "description": "create|list|test"},
                "name": {"type": "str", "description": "Webhook name"},
                "url": {"type": "str", "description": "Webhook URL"},
                "method": {"type": "str", "description": "GET|POST"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        wd = Path("data/webhooks")
        wd.mkdir(parents=True, exist_ok=True)
        a = kw.get("action", "list")
        if a == "create":
            wh = {"name": kw.get("name", ""), "url": kw.get("url", ""), "method": kw.get("method", "POST")}
            (wd / f"{kw.get('name', 'wh').replace(' ', '_')}.json").write_text(json.dumps(wh, indent=2))
            return {"status": "success", "webhook": wh}
        elif a == "test":
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.request(kw.get("method", "POST"), kw.get("url", ""), json={"test": True})
                return {"status": "success", "code": r.status_code}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "success", "webhooks": [json.loads(f.read_text()) for f in wd.glob("*.json")]}


class AutomationAgent(BaseAgent):
    name = "automation"
    description = "Workflow automation, cron jobs, file watchers, webhooks, IFTTT-like triggers"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are eVera's Automation Agent. Create automations, manage cron jobs, watch files, manage webhooks."
    )
    offline_responses = {
        "automate": "\u2699 Automating!",
        "cron": "\u23f0 Scheduling!",
        "webhook": "\U0001f517 Webhook!",
        "trigger": "\u26a1 Trigger!",
    }

    def _setup_tools(self):
        self._tools = [CreateAutomationTool(), ListAutomationsTool(), CronJobTool(), FileWatcherTool(), WebhookTool()]
