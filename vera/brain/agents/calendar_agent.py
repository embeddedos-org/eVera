"""Calendar Agent -- events, scheduling, availability, Google Calendar sync."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class CreateEventTool(Tool):
    def __init__(self):
        super().__init__(
            name="create_event",
            description="Create calendar event",
            parameters={
                "title": {"type": "str", "description": "Event title"},
                "date": {"type": "str", "description": "Date YYYY-MM-DD"},
                "time": {"type": "str", "description": "Time HH:MM"},
                "duration_minutes": {"type": "int", "description": "Duration"},
                "location": {"type": "str", "description": "Location"},
                "description": {"type": "str", "description": "Description"},
                "recurrence": {"type": "str", "description": "none|daily|weekly|monthly"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        cd = Path("data/calendar")
        cd.mkdir(parents=True, exist_ok=True)
        event = {
            "title": kw.get("title", ""),
            "date": kw.get("date", ""),
            "time": kw.get("time", ""),
            "duration": kw.get("duration_minutes", 60),
            "location": kw.get("location", ""),
            "description": kw.get("description", ""),
            "recurrence": kw.get("recurrence", "none"),
        }
        fp = cd / f"{kw.get('date', '')}.json"
        events = json.loads(fp.read_text()) if fp.exists() else []
        events.append(event)
        fp.write_text(json.dumps(events, indent=2))
        return {"status": "success", "event": event}


class ViewCalendarTool(Tool):
    def __init__(self):
        super().__init__(
            name="view_calendar",
            description="View calendar events",
            parameters={
                "start_date": {"type": "str", "description": "Start YYYY-MM-DD"},
                "end_date": {"type": "str", "description": "End YYYY-MM-DD"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        cd = Path("data/calendar")
        if not cd.exists():
            return {"status": "success", "events": []}
        start = datetime.strptime(kw.get("start_date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")
        end = datetime.strptime(kw.get("end_date", (start + timedelta(days=7)).strftime("%Y-%m-%d")), "%Y-%m-%d")
        all_events = []
        d = start
        while d <= end:
            fp = cd / f"{d.strftime('%Y-%m-%d')}.json"
            if fp.exists():
                all_events.extend([{**e, "date": d.strftime("%Y-%m-%d")} for e in json.loads(fp.read_text())])
            d += timedelta(days=1)
        return {
            "status": "success",
            "events": sorted(all_events, key=lambda e: f"{e['date']} {e.get('time', '')}"),
            "count": len(all_events),
        }


def _minutes(value: Any) -> int | None:
    """Minutes after midnight for an "HH:MM" (or "HH:MM:SS") time, or None if it is not one."""
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            t = datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
        return t.hour * 60 + t.minute
    return None


def _duration(value: Any) -> int:
    """An event's length in minutes; create_event's 60 when it is missing or unreadable."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 60


class AvailabilityTool(Tool):
    def __init__(self):
        super().__init__(
            name="check_availability",
            description="Check schedule availability",
            parameters={
                "date": {"type": "str", "description": "Date"},
                "start_time": {"type": "str", "description": "Start HH:MM"},
                "end_time": {"type": "str", "description": "End HH:MM"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        window_start = _minutes(kw.get("start_time") or "00:00")
        # No end time means the rest of the day, up to midnight.
        window_end = _minutes(kw["end_time"]) if kw.get("end_time") else 24 * 60
        if kw.get("end_time") and str(kw["end_time"]).strip() == "24:00":
            window_end = 24 * 60
        if window_start is None or window_end is None:
            return {"status": "error", "message": "start_time and end_time must be HH:MM"}
        if window_end == 23 * 60 + 59:
            window_end = 24 * 60  # "23:59" (the old default) means the end of the day
        if window_end < window_start:
            # A window across midnight would need the next day's events too.
            return {"status": "error", "message": "end_time must not be before start_time (one day only)"}
        if window_end == window_start:
            window_end += 1  # "am I free at 10:00?": a one-minute window

        fp = Path("data/calendar") / f"{kw.get('date', '')}.json"
        if not fp.exists():
            return {"status": "success", "available": True}
        events = json.loads(fp.read_text())

        # An event conflicts when it overlaps the window, not only when it
        # starts inside it: a 09:00 meeting of 120 minutes blocks 10:00-10:30.
        conflicts = []
        for e in events:
            start = _minutes(e.get("time", ""))
            if start is None:
                continue
            end = start + max(_duration(e.get("duration")), 1)
            if start < window_end and end > window_start:
                conflicts.append(e)
        return {"status": "success", "available": len(conflicts) == 0, "conflicts": conflicts}


class GoogleCalendarTool(Tool):
    def __init__(self):
        super().__init__(
            name="google_calendar",
            description="Sync with Google Calendar",
            parameters={
                "action": {"type": "str", "description": "list|sync"},
                "days_ahead": {"type": "int", "description": "Days to look ahead"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        return {"status": "success", "message": "Set GOOGLE_CALENDAR_CREDENTIALS in .env for full sync."}


class CalendarAgent(BaseAgent):
    name = "calendar"
    description = "Calendar events, scheduling, availability, Google Calendar sync"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are eVera's Calendar Agent. Create events, view schedules, check availability, sync with Google Calendar."
    )
    offline_responses = {
        "event": "\U0001f4c5 Creating event!",
        "calendar": "\U0001f4c5 Calendar!",
        "schedule": "\U0001f4c5 Schedule!",
        "available": "\u2705 Checking!",
        "meeting": "\U0001f91d Meeting!",
    }

    def _setup_tools(self):
        self._tools = [CreateEventTool(), ViewCalendarTool(), AvailabilityTool(), GoogleCalendarTool()]
