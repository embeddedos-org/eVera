"""Life Manager Agent — manages calendar, email, reminders, and to-do lists."""

from __future__ import annotations

import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from voca.brain.agents.base import BaseAgent, Tool
from voca.brain.state import VocaState
from voca.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


def _ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _load_json(filename: str) -> list[dict]:
    path = _ensure_data_dir() / filename
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_json(filename: str, data: list[dict]) -> None:
    path = _ensure_data_dir() / filename
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# --- Concrete tool implementations ---

class CheckCalendarTool(Tool):
    """Check calendar events for a given date."""

    def __init__(self) -> None:
        super().__init__(
            name="check_calendar",
            description="Check calendar events for a given date",
            parameters={"date": {"type": "str", "description": "Date (YYYY-MM-DD) or 'today', 'tomorrow'"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        date_str = kwargs.get("date", "today").lower().strip()

        if date_str == "today":
            target = datetime.now().strftime("%Y-%m-%d")
        elif date_str == "tomorrow":
            target = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            target = date_str

        events = _load_json("calendar.json")
        matching = [e for e in events if e.get("date") == target]
        matching.sort(key=lambda e: e.get("time", "00:00"))

        return {
            "status": "success",
            "date": target,
            "events": matching,
            "count": len(matching),
        }


class AddEventTool(Tool):
    """Add a calendar event."""

    def __init__(self) -> None:
        super().__init__(
            name="add_event",
            description="Add a calendar event",
            parameters={
                "title": {"type": "str", "description": "Event title"},
                "date": {"type": "str", "description": "Date (YYYY-MM-DD) or 'today', 'tomorrow'"},
                "time": {"type": "str", "description": "Start time (HH:MM)"},
                "duration": {"type": "str", "description": "Duration (e.g. '1h', '30m')"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        title = kwargs.get("title", "")
        date_str = kwargs.get("date", "today").lower().strip()
        time_str = kwargs.get("time", "")
        duration = kwargs.get("duration", "1h")

        if not title:
            return {"status": "error", "message": "No event title provided"}

        if date_str == "today":
            date_str = datetime.now().strftime("%Y-%m-%d")
        elif date_str == "tomorrow":
            date_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        event = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "title": title,
            "date": date_str,
            "time": time_str,
            "duration": duration,
            "created": datetime.now().isoformat(),
        }

        events = _load_json("calendar.json")
        events.append(event)
        _save_json("calendar.json", events)

        return {"status": "success", "event": event}


class CreateReminderTool(Tool):
    """Set a reminder."""

    def __init__(self) -> None:
        super().__init__(
            name="create_reminder",
            description="Set a reminder for a specific time",
            parameters={
                "text": {"type": "str", "description": "Reminder text"},
                "when": {"type": "str", "description": "When: 'in 5m', 'in 1h', 'at 14:00', or ISO datetime"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        text = kwargs.get("text", "")
        when_str = kwargs.get("when", "in 1h")

        if not text:
            return {"status": "error", "message": "No reminder text provided"}

        # Parse relative time
        trigger_at = self._parse_when(when_str)

        reminder = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "text": text,
            "trigger_at": trigger_at.isoformat(),
            "created": datetime.now().isoformat(),
            "dismissed": False,
        }

        reminders = _load_json("reminders.json")
        reminders.append(reminder)
        _save_json("reminders.json", reminders)

        return {"status": "success", "reminder": reminder, "triggers_in": str(trigger_at - datetime.now())}

    def _parse_when(self, when_str: str) -> datetime:
        """Parse relative or absolute time."""
        import re
        lower = when_str.lower().strip()

        # "in Xm" / "in Xh" / "in X minutes" / "in X hours"
        match = re.match(r"in\s+(\d+)\s*(m|min|minute|minutes|h|hr|hour|hours|s|sec|seconds?)", lower)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)[0]
            if unit == "h":
                return datetime.now() + timedelta(hours=amount)
            elif unit == "m":
                return datetime.now() + timedelta(minutes=amount)
            elif unit == "s":
                return datetime.now() + timedelta(seconds=amount)

        # "at HH:MM"
        match = re.match(r"at\s+(\d{1,2}):(\d{2})", lower)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            target = datetime.now().replace(hour=h, minute=m, second=0)
            if target < datetime.now():
                target += timedelta(days=1)
            return target

        # ISO format
        try:
            return datetime.fromisoformat(when_str)
        except ValueError:
            return datetime.now() + timedelta(hours=1)


class ListTodosTool(Tool):
    """List and manage to-do items."""

    def __init__(self) -> None:
        super().__init__(
            name="list_todos",
            description="List, add, or complete to-do items",
            parameters={
                "action": {"type": "str", "description": "Action: list, add, complete, delete"},
                "text": {"type": "str", "description": "Todo text (for add)"},
                "category": {"type": "str", "description": "Category filter: work, personal, all"},
                "todo_id": {"type": "str", "description": "Todo ID (for complete/delete)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "list").lower()
        text = kwargs.get("text", "")
        category = kwargs.get("category", "all").lower()
        todo_id = kwargs.get("todo_id", "")

        todos = _load_json("todos.json")

        if action == "add":
            if not text:
                return {"status": "error", "message": "No todo text provided"}
            todo = {
                "id": str(len(todos) + 1),
                "text": text,
                "category": category if category != "all" else "personal",
                "done": False,
                "created": datetime.now().isoformat(),
            }
            todos.append(todo)
            _save_json("todos.json", todos)
            return {"status": "success", "action": "added", "todo": todo}

        elif action == "complete":
            for t in todos:
                if t.get("id") == todo_id:
                    t["done"] = True
                    _save_json("todos.json", todos)
                    return {"status": "success", "action": "completed", "todo": t}
            return {"status": "error", "message": f"Todo #{todo_id} not found"}

        elif action == "delete":
            original_len = len(todos)
            todos = [t for t in todos if t.get("id") != todo_id]
            if len(todos) < original_len:
                _save_json("todos.json", todos)
                return {"status": "success", "action": "deleted", "todo_id": todo_id}
            return {"status": "error", "message": f"Todo #{todo_id} not found"}

        else:  # list
            if category != "all":
                filtered = [t for t in todos if t.get("category") == category and not t.get("done")]
            else:
                filtered = [t for t in todos if not t.get("done")]
            return {"status": "success", "todos": filtered, "count": len(filtered)}


class SendEmailTool(Tool):
    """Draft and send an email via SMTP."""

    def __init__(self) -> None:
        super().__init__(
            name="send_email",
            description="Draft and send an email (requires SMTP config in .env)",
            parameters={
                "to": {"type": "str", "description": "Recipient email address"},
                "subject": {"type": "str", "description": "Email subject line"},
                "body": {"type": "str", "description": "Email body content"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        to = kwargs.get("to", "")
        subject = kwargs.get("subject", "")
        body = kwargs.get("body", "")

        if not to or not subject:
            return {"status": "error", "message": "Both 'to' and 'subject' are required"}

        # Check for SMTP config
        import os
        smtp_host = os.getenv("VOCA_SMTP_HOST", "")
        smtp_port = int(os.getenv("VOCA_SMTP_PORT", "587"))
        smtp_user = os.getenv("VOCA_SMTP_USER", "")
        smtp_pass = os.getenv("VOCA_SMTP_PASS", "")

        if not smtp_host or not smtp_user:
            # Save as draft instead
            drafts = _load_json("email_drafts.json")
            draft = {
                "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                "to": to, "subject": subject, "body": body,
                "created": datetime.now().isoformat(),
                "status": "draft",
            }
            drafts.append(draft)
            _save_json("email_drafts.json", drafts)
            return {
                "status": "draft_saved",
                "message": "SMTP not configured — email saved as draft. Set VOCA_SMTP_HOST, VOCA_SMTP_USER, VOCA_SMTP_PASS in .env",
                "draft": draft,
            }

        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = smtp_user
            msg["To"] = to

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            return {"status": "success", "sent_to": to, "subject": subject}
        except Exception as e:
            return {"status": "error", "message": f"Failed to send email: {e}"}


class LifeManagerAgent(BaseAgent):
    """Manages calendar, email, reminders, and to-do lists."""

    name = "life_manager"
    description = "Manages calendar, email, reminders, and to-do lists"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a personal life management assistant. You handle scheduling, "
        "emails, reminders, and task tracking. Use your tools to actually create events, "
        "set reminders, manage todos, and send emails. Be concise and action-oriented. "
        "When the user asks to schedule something, use add_event. "
        "When they ask about their schedule, use check_calendar. "
        "When they want a reminder, use create_reminder. "
        "When they mention todos/tasks, use list_todos. "
        "When they want to email someone, use send_email."
    )

    offline_responses = {
        "schedule": "📅 I'll schedule that for you!",
        "calendar": "📅 Let me check your calendar!",
        "email": "📧 I'll draft that email!",
        "reminder": "⏰ Setting a reminder for you!",
        "todo": "✅ I'll add that to your list!",
        "meeting": "📅 I'll set up that meeting!",
        "appointment": "📅 I'll add that appointment!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            CheckCalendarTool(),
            AddEventTool(),
            CreateReminderTool(),
            ListTodosTool(),
            SendEmailTool(),
        ]
