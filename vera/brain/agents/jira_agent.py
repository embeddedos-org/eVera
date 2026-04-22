"""Jira Agent — ticket management, sprint tracking, and issue automation.

@file vera/brain/agents/jira_agent.py
@brief REST API integration for Jira Cloud (and other ticket providers).

Provides tools for fetching, creating, updating, searching tickets,
and managing sprints via the Jira Cloud REST API.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


def _get_jira_settings():
    from config import settings
    return settings.jira


async def _jira_request(method: str, endpoint: str, **kwargs) -> dict[str, Any]:
    """Make an authenticated request to the Jira REST API."""
    cfg = _get_jira_settings()

    if not cfg.base_url or not cfg.api_token or not cfg.username:
        return {
            "status": "error",
            "message": (
                "Jira not configured. Set VERA_JIRA_BASE_URL, VERA_JIRA_USERNAME, "
                "and VERA_JIRA_API_TOKEN in your .env file."
            ),
        }

    url = f"{cfg.base_url.rstrip('/')}{endpoint}"
    credentials = base64.b64encode(f"{cfg.username}:{cfg.api_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
            if response.status_code >= 400:
                return {
                    "status": "error",
                    "http_status": response.status_code,
                    "message": response.text[:500],
                }
            data = response.json() if response.text else {}
            return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _format_issue(issue: dict) -> dict[str, Any]:
    """Extract readable fields from a Jira issue."""
    fields = issue.get("fields", {})
    return {
        "key": issue.get("key", ""),
        "summary": fields.get("summary", ""),
        "status": fields.get("status", {}).get("name", ""),
        "priority": fields.get("priority", {}).get("name", ""),
        "type": fields.get("issuetype", {}).get("name", ""),
        "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
        "reporter": (fields.get("reporter") or {}).get("displayName", ""),
        "created": fields.get("created", ""),
        "updated": fields.get("updated", ""),
        "description": (fields.get("description") or "")[:500],
        "labels": fields.get("labels", []),
    }


class GetTicketTool(Tool):
    def __init__(self):
        super().__init__(
            name="get_ticket",
            description="Get details of a specific Jira ticket by ID (e.g. PROJ-123)",
            parameters={"ticket_id": {"type": "str", "description": "Ticket ID (e.g. PROJ-123)"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        ticket_id = kwargs.get("ticket_id", "")
        if not ticket_id:
            return {"status": "error", "message": "ticket_id is required"}

        result = await _jira_request("GET", f"/rest/api/3/issue/{ticket_id}")
        if result["status"] != "success":
            return result
        return {"status": "success", "ticket": _format_issue(result["data"])}


class GetMyTicketsTool(Tool):
    def __init__(self):
        super().__init__(
            name="get_my_tickets",
            description="Get tickets assigned to the current user, optionally filtered by status",
            parameters={"status": {"type": "str", "description": "Filter by status (e.g. 'In Progress', 'To Do')"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        jql = "assignee=currentUser() ORDER BY updated DESC"
        status_filter = kwargs.get("status", "")
        if status_filter:
            jql = f'assignee=currentUser() AND status="{status_filter}" ORDER BY updated DESC'

        result = await _jira_request("GET", "/rest/api/3/search", params={"jql": jql, "maxResults": 20})
        if result["status"] != "success":
            return result

        issues = result["data"].get("issues", [])
        return {
            "status": "success",
            "total": result["data"].get("total", 0),
            "tickets": [_format_issue(i) for i in issues],
        }


class ListSprintTicketsTool(Tool):
    def __init__(self):
        super().__init__(
            name="list_sprint_tickets",
            description="List tickets in the current active sprint",
            parameters={"board_id": {"type": "str", "description": "Agile board ID (uses default if not set)"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        cfg = _get_jira_settings()
        board_id = kwargs.get("board_id", "") or cfg.board_id
        if not board_id:
            return {"status": "error", "message": "board_id is required — set VERA_JIRA_BOARD_ID or pass it directly"}

        sprints_result = await _jira_request("GET", f"/rest/agile/1.0/board/{board_id}/sprint", params={"state": "active"})
        if sprints_result["status"] != "success":
            return sprints_result

        sprints = sprints_result["data"].get("values", [])
        if not sprints:
            return {"status": "success", "message": "No active sprint found", "tickets": []}

        sprint_id = sprints[0]["id"]
        sprint_name = sprints[0].get("name", "")

        issues_result = await _jira_request(
            "GET", f"/rest/agile/1.0/sprint/{sprint_id}/issue", params={"maxResults": 50},
        )
        if issues_result["status"] != "success":
            return issues_result

        issues = issues_result["data"].get("issues", [])
        return {
            "status": "success",
            "sprint": sprint_name,
            "total": len(issues),
            "tickets": [_format_issue(i) for i in issues],
        }


class CreateTicketTool(Tool):
    def __init__(self):
        super().__init__(
            name="create_ticket",
            description="Create a new Jira ticket",
            parameters={
                "summary": {"type": "str", "description": "Ticket title/summary"},
                "description": {"type": "str", "description": "Ticket description"},
                "type": {"type": "str", "description": "Issue type: Task, Bug, Story, Epic (default: Task)"},
                "priority": {"type": "str", "description": "Priority: Highest, High, Medium, Low, Lowest (default: Medium)"},
                "project_key": {"type": "str", "description": "Project key (uses default if not set)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        cfg = _get_jira_settings()
        summary = kwargs.get("summary", "")
        if not summary:
            return {"status": "error", "message": "summary is required"}

        project_key = kwargs.get("project_key", "") or cfg.project_key
        if not project_key:
            return {"status": "error", "message": "project_key is required — set VERA_JIRA_PROJECT_KEY"}

        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": kwargs.get("description", "")}]}],
                },
                "issuetype": {"name": kwargs.get("type", "Task")},
                "priority": {"name": kwargs.get("priority", "Medium")},
            },
        }

        result = await _jira_request("POST", "/rest/api/3/issue", json=payload)
        if result["status"] != "success":
            return result

        return {
            "status": "success",
            "key": result["data"].get("key", ""),
            "id": result["data"].get("id", ""),
            "url": f"{cfg.base_url}/browse/{result['data'].get('key', '')}",
        }


class UpdateTicketStatusTool(Tool):
    def __init__(self):
        super().__init__(
            name="update_ticket_status",
            description="Update the status/transition of a Jira ticket",
            parameters={
                "ticket_id": {"type": "str", "description": "Ticket ID (e.g. PROJ-123)"},
                "status": {"type": "str", "description": "Target status name (e.g. 'In Progress', 'Done')"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        ticket_id = kwargs.get("ticket_id", "")
        target_status = kwargs.get("status", "")
        if not ticket_id or not target_status:
            return {"status": "error", "message": "ticket_id and status are required"}

        transitions_result = await _jira_request("GET", f"/rest/api/3/issue/{ticket_id}/transitions")
        if transitions_result["status"] != "success":
            return transitions_result

        transitions = transitions_result["data"].get("transitions", [])
        target = next((t for t in transitions if t["name"].lower() == target_status.lower()), None)

        if not target:
            available = [t["name"] for t in transitions]
            return {"status": "error", "message": f"Status '{target_status}' not available. Options: {available}"}

        result = await _jira_request(
            "POST", f"/rest/api/3/issue/{ticket_id}/transitions",
            json={"transition": {"id": target["id"]}},
        )
        if result["status"] != "success":
            return result

        return {"status": "success", "ticket_id": ticket_id, "new_status": target_status}


class AddCommentTool(Tool):
    def __init__(self):
        super().__init__(
            name="add_comment",
            description="Add a comment to a Jira ticket",
            parameters={
                "ticket_id": {"type": "str", "description": "Ticket ID (e.g. PROJ-123)"},
                "comment": {"type": "str", "description": "Comment text to add"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        ticket_id = kwargs.get("ticket_id", "")
        comment = kwargs.get("comment", "")
        if not ticket_id or not comment:
            return {"status": "error", "message": "ticket_id and comment are required"}

        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}],
            },
        }

        result = await _jira_request("POST", f"/rest/api/3/issue/{ticket_id}/comment", json=payload)
        if result["status"] != "success":
            return result

        return {"status": "success", "ticket_id": ticket_id, "comment_id": result["data"].get("id", "")}


class SearchTicketsTool(Tool):
    def __init__(self):
        super().__init__(
            name="search_tickets",
            description="Search Jira tickets using JQL or plain text",
            parameters={"query": {"type": "str", "description": "JQL query or search text"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        query = kwargs.get("query", "")
        if not query:
            return {"status": "error", "message": "query is required"}

        jql = query if any(kw in query.lower() for kw in ["=", "and", "or", "order by"]) else f'text ~ "{query}" ORDER BY updated DESC'

        result = await _jira_request("GET", "/rest/api/3/search", params={"jql": jql, "maxResults": 15})
        if result["status"] != "success":
            return result

        issues = result["data"].get("issues", [])
        return {
            "status": "success",
            "total": result["data"].get("total", 0),
            "tickets": [_format_issue(i) for i in issues],
        }


class JiraAgent(BaseAgent):
    """Jira ticket management, sprint tracking, and issue automation."""

    name = "jira"
    description = "Jira ticket management — view, create, update, search tickets and sprints"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a Jira/ticket management assistant. You can fetch ticket details, "
        "list assigned tickets, view sprint boards, create new tickets, update statuses, "
        "add comments, and search issues. Always show ticket keys and summaries clearly. "
        "When creating tickets, confirm the details with the user first."
    )

    offline_responses = {
        "jira": "🎫 I can help with Jira tickets! What do you need?",
        "ticket": "🎫 Let me look up that ticket for you!",
        "sprint": "🏃 Checking the sprint board!",
        "backlog": "📋 Let me check the backlog!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            GetTicketTool(),
            GetMyTicketsTool(),
            ListSprintTicketsTool(),
            CreateTicketTool(),
            UpdateTicketStatusTool(),
            AddCommentTool(),
            SearchTicketsTool(),
        ]
