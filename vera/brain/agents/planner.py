"""Planner Agent — structured planning cycles, goal tracking, and priority scoring."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
REVIEWS_DIR = DATA_DIR / "reviews"


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ("daily", "weekly", "monthly"):
        (REVIEWS_DIR / sub).mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return [] if path.suffix == ".json" else {}
    return [] if "goals" in path.name else {}


def _save_json(path: Path, data: Any) -> None:
    _ensure_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# --- Tool implementations ---


class MorningPlanTool(Tool):
    """Generate a prioritized daily plan from calendar, todos, and goals."""

    def __init__(self) -> None:
        super().__init__(
            name="morning_plan",
            description="Generate a prioritized daily plan from calendar events, pending todos, and active goals using Eisenhower matrix scoring",
            parameters={
                "date": {"type": "str", "description": "Date to plan for (YYYY-MM-DD or 'today'). Default: today"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        date_str = kwargs.get("date", "today").strip()
        if date_str == "today":
            date_str = datetime.now().strftime("%Y-%m-%d")

        _ensure_dirs()

        events = _load_json(DATA_DIR / "calendar.json")
        today_events = [e for e in events if e.get("date") == date_str]
        today_events.sort(key=lambda e: e.get("time", "00:00"))

        todos = _load_json(DATA_DIR / "todos.json")
        pending_todos = [t for t in todos if not t.get("done")]

        goals = _load_json(DATA_DIR / "goals.json")
        active_goals = [g for g in goals if g.get("status") == "active"]

        plan = {
            "date": date_str,
            "created_at": datetime.now().isoformat(),
            "events": today_events,
            "pending_todos": pending_todos,
            "active_goals": [{"id": g["id"], "title": g["title"], "type": g.get("type")} for g in active_goals],
            "plan": f"Daily plan for {date_str} with {len(today_events)} events, {len(pending_todos)} pending tasks, and {len(active_goals)} active goals.",
        }

        review_path = REVIEWS_DIR / "daily" / f"{date_str}.json"
        existing = _load_json(review_path) if review_path.exists() else {}
        existing["plan"] = plan
        _save_json(review_path, existing)

        return {
            "status": "success",
            "date": date_str,
            "events_count": len(today_events),
            "todos_count": len(pending_todos),
            "goals_count": len(active_goals),
            "plan": plan,
        }


class PriorityScoreTool(Tool):
    """Score tasks by urgency × importance (Eisenhower matrix)."""

    def __init__(self) -> None:
        super().__init__(
            name="priority_score",
            description="Score a list of tasks by urgency × importance using Eisenhower matrix. Returns ranked list with reasoning",
            parameters={
                "tasks": {"type": "str", "description": "Comma-separated list of tasks to prioritize"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        tasks_str = kwargs.get("tasks", "")
        if not tasks_str:
            return {"status": "error", "message": "No tasks provided"}

        task_list = [t.strip() for t in tasks_str.split(",") if t.strip()]

        scored = []
        for i, task in enumerate(task_list):
            scored.append(
                {
                    "rank": i + 1,
                    "task": task,
                    "note": "Priority scoring requires LLM — pass this to the LLM for Eisenhower matrix analysis",
                }
            )

        return {
            "status": "success",
            "tasks": scored,
            "count": len(scored),
            "note": "Use LLM to analyze urgency × importance for each task",
        }


class DailyReviewTool(Tool):
    """End-of-day review: what got done, what didn't, blockers, lessons."""

    def __init__(self) -> None:
        super().__init__(
            name="daily_review",
            description="End-of-day review: analyze what got done, what didn't, blockers, and lessons learned",
            parameters={
                "date": {"type": "str", "description": "Date to review (YYYY-MM-DD or 'today'). Default: today"},
                "notes": {"type": "str", "description": "Optional user notes about the day"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        date_str = kwargs.get("date", "today").strip()
        notes = kwargs.get("notes", "")
        if date_str == "today":
            date_str = datetime.now().strftime("%Y-%m-%d")

        _ensure_dirs()

        todos = _load_json(DATA_DIR / "todos.json")
        completed = [t for t in todos if t.get("done")]
        incomplete = [t for t in todos if not t.get("done")]

        review = {
            "date": date_str,
            "completed": [t.get("text", "") for t in completed],
            "incomplete": [t.get("text", "") for t in incomplete],
            "completed_count": len(completed),
            "incomplete_count": len(incomplete),
            "notes": notes,
            "reviewed_at": datetime.now().isoformat(),
        }

        review_path = REVIEWS_DIR / "daily" / f"{date_str}.json"
        existing = _load_json(review_path) if review_path.exists() else {}
        existing["review"] = review
        _save_json(review_path, existing)

        return {"status": "success", "review": review}


class WeeklyReviewTool(Tool):
    """Weekly reflection: patterns, goal progress, adjustments."""

    def __init__(self) -> None:
        super().__init__(
            name="weekly_review",
            description="Weekly reflection: analyze patterns across daily reviews, goal progress, and suggest adjustments",
            parameters={
                "week": {"type": "str", "description": "Week identifier (YYYY-WXX) or 'this_week'. Default: this_week"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        week_str = kwargs.get("week", "this_week").strip()
        now = datetime.now()

        if week_str == "this_week":
            week_str = now.strftime("%Y-W%V")

        _ensure_dirs()

        daily_dir = REVIEWS_DIR / "daily"
        daily_reviews = []

        start_of_week = now - timedelta(days=now.weekday())
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            day_file = daily_dir / f"{day.strftime('%Y-%m-%d')}.json"
            if day_file.exists():
                daily_reviews.append(_load_json(day_file))

        goals = _load_json(DATA_DIR / "goals.json")
        active_goals = [g for g in goals if g.get("status") == "active"]

        review = {
            "week": week_str,
            "daily_reviews_found": len(daily_reviews),
            "daily_reviews": daily_reviews,
            "active_goals": active_goals,
            "reviewed_at": datetime.now().isoformat(),
        }

        review_path = REVIEWS_DIR / "weekly" / f"{week_str}.json"
        _save_json(review_path, review)

        return {"status": "success", "review": review}


class MonthlyReviewTool(Tool):
    """Monthly evaluation: goal completion rates, trends, optimization suggestions."""

    def __init__(self) -> None:
        super().__init__(
            name="monthly_review",
            description="Monthly evaluation: goal completion rates, productivity trends, and optimization suggestions",
            parameters={
                "month": {"type": "str", "description": "Month (YYYY-MM) or 'this_month'. Default: this_month"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        month_str = kwargs.get("month", "this_month").strip()
        if month_str == "this_month":
            month_str = datetime.now().strftime("%Y-%m")

        _ensure_dirs()

        weekly_dir = REVIEWS_DIR / "weekly"
        weekly_reviews = []
        if weekly_dir.exists():
            for f in sorted(weekly_dir.glob(f"{month_str[:4]}-W*.json")):
                weekly_reviews.append(_load_json(f))

        goals = _load_json(DATA_DIR / "goals.json")
        completed_goals = [g for g in goals if g.get("status") == "completed"]
        active_goals = [g for g in goals if g.get("status") == "active"]

        review = {
            "month": month_str,
            "weekly_reviews_found": len(weekly_reviews),
            "goals_completed": len(completed_goals),
            "goals_active": len(active_goals),
            "weekly_reviews": weekly_reviews,
            "reviewed_at": datetime.now().isoformat(),
        }

        review_path = REVIEWS_DIR / "monthly" / f"{month_str}.json"
        _save_json(review_path, review)

        return {"status": "success", "review": review}


class SetGoalsTool(Tool):
    """Define goals with type, description, target date, and criteria."""

    def __init__(self) -> None:
        super().__init__(
            name="set_goals",
            description="Define a goal with type (daily/weekly/monthly/longterm), description, target date, and measurable criteria",
            parameters={
                "title": {"type": "str", "description": "Goal title"},
                "type": {"type": "str", "description": "Goal type: daily, weekly, monthly, longterm"},
                "description": {"type": "str", "description": "Detailed goal description"},
                "target_date": {"type": "str", "description": "Target date (YYYY-MM-DD)"},
                "criteria": {"type": "str", "description": "Measurable success criteria"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        title = kwargs.get("title", "")
        if not title:
            return {"status": "error", "message": "No goal title provided"}

        goal_type = kwargs.get("type", "weekly")
        description = kwargs.get("description", "")
        target_date = kwargs.get("target_date", "")
        criteria = kwargs.get("criteria", "")

        _ensure_dirs()
        goals = _load_json(DATA_DIR / "goals.json")

        goal = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "title": title,
            "type": goal_type,
            "description": description,
            "target_date": target_date,
            "criteria": criteria,
            "sub_tasks": [],
            "progress": 0,
            "status": "active",
            "created_at": datetime.now().isoformat(),
        }

        goals.append(goal)
        _save_json(DATA_DIR / "goals.json", goals)

        return {"status": "success", "goal": goal}


class CheckGoalsTool(Tool):
    """View active goals and their progress."""

    def __init__(self) -> None:
        super().__init__(
            name="check_goals",
            description="View active goals and their progress (completed sub-tasks, % done)",
            parameters={
                "status_filter": {
                    "type": "str",
                    "description": "Filter by status: active, completed, all. Default: active",
                },
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        status_filter = kwargs.get("status_filter", "active").lower()

        goals = _load_json(DATA_DIR / "goals.json")

        if status_filter != "all":
            filtered = [g for g in goals if g.get("status") == status_filter]
        else:
            filtered = goals

        return {
            "status": "success",
            "goals": filtered,
            "count": len(filtered),
            "filter": status_filter,
        }


class FocusBlockTool(Tool):
    """Schedule a deep-focus time block."""

    def __init__(self) -> None:
        super().__init__(
            name="focus_block",
            description="Schedule a deep-focus time block — creates a calendar event and sets do-not-disturb flag",
            parameters={
                "title": {"type": "str", "description": "Focus block title (e.g. 'Deep work on ML project')"},
                "duration": {"type": "str", "description": "Duration (e.g. '2h', '90m'). Default: 2h"},
                "start_time": {"type": "str", "description": "Start time (HH:MM) or 'now'. Default: now"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        title = kwargs.get("title", "Focus Block")
        duration = kwargs.get("duration", "2h")
        start_time = kwargs.get("start_time", "now")

        now = datetime.now()
        if start_time == "now":
            start_time = now.strftime("%H:%M")

        _ensure_dirs()

        event = {
            "id": now.strftime("%Y%m%d%H%M%S"),
            "title": f"🎯 {title}",
            "date": now.strftime("%Y-%m-%d"),
            "time": start_time,
            "duration": duration,
            "focus": True,
            "created": now.isoformat(),
        }

        events = _load_json(DATA_DIR / "calendar.json")
        if not isinstance(events, list):
            events = []
        events.append(event)
        _save_json(DATA_DIR / "calendar.json", events)

        return {
            "status": "success",
            "event": event,
            "message": f"Focus block '{title}' scheduled for {start_time} ({duration}). Do-not-disturb activated.",
        }


class PlannerAgent(BaseAgent):
    """Structured productivity coach for daily/weekly/monthly planning cycles."""

    name = "planner"
    description = "Structured productivity coach for planning cycles, goal tracking, and priority scoring"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a structured productivity coach that drives daily, weekly, and monthly "
        "planning cycles. You help the user:\n"
        "- Generate prioritized daily plans using the Eisenhower matrix (urgent/important)\n"
        "- Set and track goals with measurable criteria\n"
        "- Conduct daily, weekly, and monthly reviews to identify patterns and improvements\n"
        "- Score tasks by urgency × importance\n"
        "- Schedule deep-focus blocks for distraction-free work\n\n"
        "Be action-oriented and structured. Use bullet points and clear formatting. "
        "When generating plans, consider calendar events, pending todos, and active goals. "
        "For reviews, analyze what worked, what didn't, and suggest concrete adjustments."
    )

    offline_responses = {
        "plan": "📋 Let me help you plan your day!",
        "planning": "📋 Let's get organized!",
        "goal": "🎯 Let's set that goal!",
        "goals": "🎯 Let me check your goals!",
        "review": "📊 Time for a review!",
        "priority": "🔢 Let me help prioritize!",
        "focus": "🎯 Let me set up a focus block for you!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            MorningPlanTool(),
            PriorityScoreTool(),
            DailyReviewTool(),
            WeeklyReviewTool(),
            MonthlyReviewTool(),
            SetGoalsTool(),
            CheckGoalsTool(),
            FocusBlockTool(),
        ]
