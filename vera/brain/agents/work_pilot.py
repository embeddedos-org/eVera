"""Work Pilot Agent — autonomous ticket-to-PR workflow orchestration.

@file vera/brain/agents/work_pilot.py
@brief Coordinates existing agents (Jira, Git, Coder) to autonomously
work through tickets: fetch ticket → create branch → code → commit → PR → update Jira.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
WORK_ITEMS_PATH = DATA_DIR / "work_items.json"


def _load_work_items() -> list[dict]:
    try:
        return json.loads(WORK_ITEMS_PATH.read_text()) if WORK_ITEMS_PATH.exists() else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_work_items(items: list[dict]) -> None:
    WORK_ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WORK_ITEMS_PATH.write_text(json.dumps(items, indent=2, default=str))


def _find_work_item(work_id: str, items: list[dict]) -> dict | None:
    for item in items:
        if item.get("work_id") == work_id or item.get("ticket_id") == work_id:
            return item
    return None


class StartWorkOnTicketTool(Tool):
    def __init__(self):
        super().__init__(
            name="start_work_on_ticket",
            description="Start working on a Jira ticket — fetches details, creates a feature branch, and tracks state",
            parameters={
                "ticket_id": {"type": "str", "description": "Jira ticket ID (e.g. PROJ-123)"},
                "repo_path": {"type": "str", "description": "Path to the git repository"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        ticket_id = kwargs.get("ticket_id", "")
        repo_path = kwargs.get("repo_path", ".")
        if not ticket_id:
            return {"status": "error", "message": "ticket_id is required"}

        # Check for duplicate
        items = _load_work_items()
        existing = _find_work_item(ticket_id, items)
        if existing and existing.get("status") not in ("completed", "abandoned"):
            return {
                "status": "error",
                "message": f"Work already in progress for {ticket_id} (work_id: {existing['work_id']}, status: {existing['status']})",
            }

        # 1. Fetch ticket details from Jira
        from vera.brain.agents.jira_agent import GetTicketTool
        ticket_tool = GetTicketTool()
        ticket_result = await ticket_tool.execute(ticket_id=ticket_id)

        if ticket_result.get("status") != "success":
            return {"status": "error", "message": f"Failed to fetch ticket: {ticket_result.get('message', 'unknown error')}"}

        ticket = ticket_result.get("ticket", {})

        # 2. Create feature branch
        branch_name = f"feature/{ticket_id.lower()}"
        from vera.brain.agents.git_agent import GitBranchTool
        branch_tool = GitBranchTool()
        branch_result = await branch_tool.execute(action="create", name=branch_name, repo_path=repo_path)

        if branch_result.get("status") != "success":
            return {"status": "error", "message": f"Failed to create branch: {branch_result.get('error', branch_result.get('message', ''))}"}

        # 3. Update Jira status to "In Progress"
        from vera.brain.agents.jira_agent import UpdateTicketStatusTool
        status_tool = UpdateTicketStatusTool()
        await status_tool.execute(ticket_id=ticket_id, status="In Progress")

        # 4. Store work item state
        work_id = f"work-{uuid.uuid4().hex[:8]}"
        work_item = {
            "work_id": work_id,
            "ticket_id": ticket_id,
            "branch": branch_name,
            "repo_path": str(Path(repo_path).resolve()),
            "status": "in_progress",
            "ticket_summary": ticket.get("summary", ""),
            "ticket_type": ticket.get("type", ""),
            "created_at": datetime.now().isoformat(),
        }
        items.append(work_item)
        _save_work_items(items)

        return {
            "status": "success",
            "work_id": work_id,
            "ticket_id": ticket_id,
            "branch": branch_name,
            "summary": ticket.get("summary", ""),
            "message": f"Branch '{branch_name}' created and ready for coding. Ticket moved to In Progress.",
        }


class CheckWorkStatusTool(Tool):
    def __init__(self):
        super().__init__(
            name="check_work_status",
            description="Check the status of a work item (by work_id or ticket_id)",
            parameters={"work_id": {"type": "str", "description": "Work item ID or ticket ID"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        work_id = kwargs.get("work_id", "")
        if not work_id:
            return {"status": "error", "message": "work_id is required"}

        items = _load_work_items()
        item = _find_work_item(work_id, items)

        if not item:
            all_items = [{"work_id": i["work_id"], "ticket_id": i["ticket_id"], "status": i["status"]} for i in items]
            return {"status": "error", "message": f"Work item '{work_id}' not found", "all_items": all_items}

        # Get git status for the repo
        from vera.brain.agents.git_agent import GitStatusTool
        git_status = await GitStatusTool().execute(repo_path=item.get("repo_path", "."))

        return {
            "status": "success",
            "work_item": item,
            "git_status": git_status.get("output", ""),
        }


class CompleteWorkItemTool(Tool):
    def __init__(self):
        super().__init__(
            name="complete_work_item",
            description="Complete a work item — commit, push, create PR, and update Jira",
            parameters={
                "work_id": {"type": "str", "description": "Work item ID or ticket ID"},
                "commit_message": {"type": "str", "description": "Commit message (auto-generated if not set)"},
                "pr_title": {"type": "str", "description": "PR title (auto-generated if not set)"},
                "pr_body": {"type": "str", "description": "PR description"},
                "reviewers": {"type": "str", "description": "Comma-separated reviewer usernames"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        work_id = kwargs.get("work_id", "")
        if not work_id:
            return {"status": "error", "message": "work_id is required"}

        items = _load_work_items()
        item = _find_work_item(work_id, items)

        if not item:
            return {"status": "error", "message": f"Work item '{work_id}' not found"}
        if item.get("status") == "completed":
            return {"status": "error", "message": f"Work item already completed (PR: {item.get('pr_url', 'N/A')})"}

        repo = item.get("repo_path", ".")
        ticket_id = item["ticket_id"]
        branch = item["branch"]
        summary = item.get("ticket_summary", ticket_id)

        # 1. Check for changes
        from vera.brain.agents.git_agent import GitStatusTool, GitCommitTool, GitPushTool, GitCreatePRTool
        status_result = await GitStatusTool().execute(repo_path=repo)
        if status_result.get("status") == "success" and not status_result.get("output", "").strip():
            return {"status": "error", "message": "No changes to commit. Make code changes first."}

        # 2. Commit
        commit_msg = kwargs.get("commit_message", "") or f"feat({ticket_id}): {summary}"
        commit_result = await GitCommitTool().execute(message=commit_msg, repo_path=repo, all=True)
        if commit_result.get("status") != "success":
            return {"status": "error", "message": f"Commit failed: {commit_result.get('error', '')}"}

        # 3. Push
        push_result = await GitPushTool().execute(repo_path=repo, branch=branch)
        if push_result.get("status") != "success":
            return {"status": "error", "message": f"Push failed: {push_result.get('error', '')}"}

        # 4. Create PR
        pr_title = kwargs.get("pr_title", "") or f"[{ticket_id}] {summary}"
        pr_body = kwargs.get("pr_body", "") or f"Resolves {ticket_id}\n\n{summary}"
        reviewers = kwargs.get("reviewers", "")

        pr_result = await GitCreatePRTool().execute(
            title=pr_title, body=pr_body, head_branch=branch, reviewers=reviewers, repo_path=repo,
        )

        pr_url = pr_result.get("pr_url", "")

        # 5. Update Jira — move to "In Review"
        from vera.brain.agents.jira_agent import UpdateTicketStatusTool, AddCommentTool
        await UpdateTicketStatusTool().execute(ticket_id=ticket_id, status="In Review")

        # 6. Add PR link as Jira comment
        if pr_url:
            await AddCommentTool().execute(ticket_id=ticket_id, comment=f"PR created: {pr_url}")

        # 7. Update work item state
        item["status"] = "completed"
        item["pr_url"] = pr_url
        item["completed_at"] = datetime.now().isoformat()
        _save_work_items(items)

        return {
            "status": "success",
            "work_id": item["work_id"],
            "ticket_id": ticket_id,
            "branch": branch,
            "commit_message": commit_msg,
            "pr_url": pr_url,
            "message": f"Work complete! PR created and Jira updated to In Review.",
        }


class WorkPilotAgent(BaseAgent):
    """Autonomous work pipeline — ticket → branch → code → PR → Jira update."""

    name = "work_pilot"
    description = "Autonomous ticket-to-PR workflow — start work, track progress, complete with PR and Jira updates"
    tier = ModelTier.STRATEGIST
    system_prompt = (
        "You are a work automation pilot. You orchestrate the full development workflow: "
        "fetch a Jira ticket, create a feature branch, track work progress, and complete "
        "by committing, pushing, creating a PR, and updating Jira. Guide the user through "
        "each step and confirm before completing."
    )

    offline_responses = {
        "work_on": "🚀 Let me set up the work environment for that ticket!",
        "start_work": "🏗️ I'll create a branch and get everything ready!",
        "complete": "✅ Let me wrap up — commit, PR, and Jira update!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            StartWorkOnTicketTool(),
            CheckWorkStatusTool(),
            CompleteWorkItemTool(),
        ]
