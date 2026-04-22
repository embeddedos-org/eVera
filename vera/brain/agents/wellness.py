"""Wellness Agent — focus sessions, break management, and burnout prevention."""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

BREAK_ACTIVITIES = [
    "Go for a short walk — fresh air does wonders! 🚶",
    "Try a 5-minute meditation or deep breathing exercise 🧘",
    "Listen to a song you enjoy 🎵",
    "Make yourself a cup of coffee or tea ☕",
    "Do a quick stretch session 💪",
    "Look out the window and rest your eyes 👀",
    "Doodle or sketch something for fun 🎨",
    "Chat with a friend or colleague 💬",
]


def _ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _load_wellness() -> dict:
    path = _ensure_data_dir() / "wellness.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "work_hours": {"start": "09:00", "end": "18:00", "max_hours": 8},
        "sessions": [],
        "breaks": [],
        "energy_logs": [],
        "daily_stats": {},
    }


def _save_wellness(data: dict) -> None:
    path = _ensure_data_dir() / "wellness.json"
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _update_daily_stats(data: dict) -> None:
    """Recalculate today's stats from session and break logs."""
    today = _today_key()
    today_sessions = [s for s in data.get("sessions", []) if s.get("start", "").startswith(today)]
    today_breaks = [b for b in data.get("breaks", []) if b.get("start", "").startswith(today)]
    today_energy = [e for e in data.get("energy_logs", []) if e.get("timestamp", "").startswith(today)]

    focus_min = sum(s.get("duration_min", 0) for s in today_sessions if s.get("end"))
    break_min = sum(b.get("duration_min", 0) for b in today_breaks)
    energy_levels = [e.get("level", 3) for e in today_energy]
    avg_energy = sum(energy_levels) / len(energy_levels) if energy_levels else 0

    data.setdefault("daily_stats", {})[today] = {
        "focus_min": focus_min,
        "break_min": break_min,
        "sessions": len(today_sessions),
        "breaks": len(today_breaks),
        "avg_energy": round(avg_energy, 1),
    }


# --- Tool implementations ---


class StartFocusTool(Tool):
    """Start a pomodoro/focus timer."""

    def __init__(self) -> None:
        super().__init__(
            name="start_focus",
            description="Start a pomodoro/focus timer session. Tracks session start time and duration",
            parameters={
                "duration_min": {"type": "int", "description": "Focus duration in minutes. Default: 25"},
                "label": {"type": "str", "description": "Optional label for what you're working on"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from config import settings
        duration = kwargs.get("duration_min", settings.wellness.focus_duration_min)
        label = kwargs.get("label", "")

        try:
            duration = int(duration)
        except (TypeError, ValueError):
            duration = 25

        data = _load_wellness()

        active = [s for s in data.get("sessions", []) if not s.get("end")]
        if active:
            return {"status": "error", "message": "A focus session is already active. Take a break first!"}

        session = {
            "type": "focus",
            "start": datetime.now().isoformat(),
            "end": None,
            "duration_min": duration,
            "label": label,
        }

        data.setdefault("sessions", []).append(session)
        _save_wellness(data)

        return {
            "status": "success",
            "session": session,
            "message": f"🎯 Focus session started! {duration} minutes of deep work. You got this!",
        }


class TakeBreakTool(Tool):
    """Suggest a break activity and log the break."""

    def __init__(self) -> None:
        super().__init__(
            name="take_break",
            description="End current focus session, suggest a break activity, and log the break",
            parameters={
                "duration_min": {"type": "int", "description": "Break duration in minutes. Default: 5"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from config import settings
        duration = kwargs.get("duration_min", settings.wellness.break_duration_min)

        try:
            duration = int(duration)
        except (TypeError, ValueError):
            duration = 5

        data = _load_wellness()
        now = datetime.now()

        # End any active focus session
        for session in data.get("sessions", []):
            if not session.get("end"):
                session["end"] = now.isoformat()
                start = datetime.fromisoformat(session["start"])
                session["duration_min"] = round((now - start).total_seconds() / 60, 1)

        activity = random.choice(BREAK_ACTIVITIES)

        break_entry = {
            "start": now.isoformat(),
            "duration_min": duration,
            "activity": activity,
        }

        data.setdefault("breaks", []).append(break_entry)
        _update_daily_stats(data)
        _save_wellness(data)

        return {
            "status": "success",
            "break": break_entry,
            "suggestion": activity,
            "message": f"☕ Break time! Take {duration} minutes.\n\n{activity}",
        }


class ScreenTimeTool(Tool):
    """Report screen time stats for today."""

    def __init__(self) -> None:
        super().__init__(
            name="screen_time",
            description="Report screen time stats: today's active focus hours, session count, longest streak",
            parameters={},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from config import settings
        data = _load_wellness()
        today = _today_key()

        today_sessions = [
            s for s in data.get("sessions", [])
            if s.get("start", "").startswith(today) and s.get("end")
        ]

        total_min = sum(s.get("duration_min", 0) for s in today_sessions)
        longest = max((s.get("duration_min", 0) for s in today_sessions), default=0)
        max_hours = data.get("work_hours", {}).get("max_hours", settings.wellness.max_work_hours)

        warning = ""
        if total_min / 60 >= max_hours:
            warning = f"⚠️ You've exceeded your {max_hours}h daily work limit! Consider wrapping up."

        return {
            "status": "success",
            "today": today,
            "total_focus_min": round(total_min, 1),
            "total_focus_hours": round(total_min / 60, 1),
            "session_count": len(today_sessions),
            "longest_session_min": round(longest, 1),
            "max_hours": max_hours,
            "warning": warning,
        }


class EnergyCheckTool(Tool):
    """Self-assessment: user rates energy 1-5, system detects burnout patterns."""

    def __init__(self) -> None:
        super().__init__(
            name="energy_check",
            description="Log energy level (1-5) and detect burnout patterns from consecutive low ratings",
            parameters={
                "level": {"type": "int", "description": "Energy level 1-5 (1=exhausted, 5=energized)"},
                "note": {"type": "str", "description": "Optional note about how you're feeling"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from config import settings
        level = kwargs.get("level", 3)
        note = kwargs.get("note", "")

        try:
            level = max(1, min(5, int(level)))
        except (TypeError, ValueError):
            level = 3

        data = _load_wellness()

        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "note": note,
        }

        data.setdefault("energy_logs", []).append(entry)
        _update_daily_stats(data)
        _save_wellness(data)

        # Check for burnout pattern
        threshold = settings.wellness.burnout_threshold
        recent = data["energy_logs"][-threshold:]
        consecutive_low = all(e.get("level", 3) <= 2 for e in recent) if len(recent) >= threshold else False

        burnout_warning = ""
        if consecutive_low:
            burnout_warning = (
                f"🚨 Burnout alert! You've reported {threshold} consecutive low energy levels. "
                "Please take a meaningful break, go outside, or call it a day. Your wellbeing matters!"
            )

        emoji_map = {1: "😴", 2: "😔", 3: "😐", 4: "😊", 5: "🔥"}
        emoji = emoji_map.get(level, "😐")

        return {
            "status": "success",
            "entry": entry,
            "emoji": emoji,
            "burnout_warning": burnout_warning,
            "message": f"{emoji} Energy level logged: {level}/5" + (f"\n{burnout_warning}" if burnout_warning else ""),
        }


class SetWorkHoursTool(Tool):
    """Define work boundaries: start/end time, max hours."""

    def __init__(self) -> None:
        super().__init__(
            name="set_work_hours",
            description="Define work boundaries (start time, end time, max hours). System warns when exceeded",
            parameters={
                "start": {"type": "str", "description": "Work start time (HH:MM). Default: 09:00"},
                "end": {"type": "str", "description": "Work end time (HH:MM). Default: 18:00"},
                "max_hours": {"type": "int", "description": "Maximum work hours per day. Default: 8"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        start = kwargs.get("start", "09:00")
        end = kwargs.get("end", "18:00")
        max_hours = kwargs.get("max_hours", 8)

        try:
            max_hours = int(max_hours)
        except (TypeError, ValueError):
            max_hours = 8

        data = _load_wellness()
        data["work_hours"] = {
            "start": start,
            "end": end,
            "max_hours": max_hours,
        }
        _save_wellness(data)

        return {
            "status": "success",
            "work_hours": data["work_hours"],
            "message": f"⏰ Work hours set: {start} to {end}, max {max_hours}h/day",
        }


class DistractionReportTool(Tool):
    """Analyze context-switching patterns from session logs."""

    def __init__(self) -> None:
        super().__init__(
            name="distraction_report",
            description="Analyze context-switching patterns: how often you switch between focus sessions and breaks",
            parameters={
                "date": {"type": "str", "description": "Date to analyze (YYYY-MM-DD or 'today'). Default: today"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        date_str = kwargs.get("date", "today").strip()
        if date_str == "today":
            date_str = _today_key()

        data = _load_wellness()

        today_sessions = [s for s in data.get("sessions", []) if s.get("start", "").startswith(date_str)]
        today_breaks = [b for b in data.get("breaks", []) if b.get("start", "").startswith(date_str)]

        completed_sessions = [s for s in today_sessions if s.get("end")]
        short_sessions = [s for s in completed_sessions if s.get("duration_min", 0) < 15]

        return {
            "status": "success",
            "date": date_str,
            "total_sessions": len(today_sessions),
            "completed_sessions": len(completed_sessions),
            "breaks_taken": len(today_breaks),
            "short_sessions_under_15min": len(short_sessions),
            "context_switches": len(today_sessions) + len(today_breaks),
            "note": "High context-switch count or many short sessions may indicate distraction issues",
        }


class WellnessSummaryTool(Tool):
    """Generate daily/weekly wellness report."""

    def __init__(self) -> None:
        super().__init__(
            name="wellness_summary",
            description="Generate a wellness report: focus sessions, breaks taken, energy trend, and recommendations",
            parameters={
                "period": {"type": "str", "description": "Period: 'today', 'week', or specific date (YYYY-MM-DD). Default: today"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        period = kwargs.get("period", "today").strip()

        data = _load_wellness()

        if period == "today":
            date_str = _today_key()
            stats = data.get("daily_stats", {}).get(date_str, {})
            sessions = [s for s in data.get("sessions", []) if s.get("start", "").startswith(date_str)]
            breaks = [b for b in data.get("breaks", []) if b.get("start", "").startswith(date_str)]
            energy = [e for e in data.get("energy_logs", []) if e.get("timestamp", "").startswith(date_str)]

            return {
                "status": "success",
                "period": "today",
                "date": date_str,
                "focus_sessions": len(sessions),
                "total_focus_min": stats.get("focus_min", 0),
                "breaks_taken": len(breaks),
                "total_break_min": stats.get("break_min", 0),
                "energy_readings": len(energy),
                "avg_energy": stats.get("avg_energy", 0),
                "energy_trend": [{"time": e["timestamp"], "level": e["level"]} for e in energy],
            }

        elif period == "week":
            now = datetime.now()
            week_stats = {}
            for i in range(7):
                day = (now - __import__("datetime").timedelta(days=now.weekday() - i))
                day_key = day.strftime("%Y-%m-%d")
                day_stats = data.get("daily_stats", {}).get(day_key, {})
                if day_stats:
                    week_stats[day_key] = day_stats

            total_focus = sum(s.get("focus_min", 0) for s in week_stats.values())
            total_breaks = sum(s.get("break_min", 0) for s in week_stats.values())
            total_sessions = sum(s.get("sessions", 0) for s in week_stats.values())
            avg_energies = [s.get("avg_energy", 0) for s in week_stats.values() if s.get("avg_energy")]
            week_avg_energy = sum(avg_energies) / len(avg_energies) if avg_energies else 0

            return {
                "status": "success",
                "period": "week",
                "days_tracked": len(week_stats),
                "total_focus_min": total_focus,
                "total_focus_hours": round(total_focus / 60, 1),
                "total_break_min": total_breaks,
                "total_sessions": total_sessions,
                "avg_energy": round(week_avg_energy, 1),
                "daily_breakdown": week_stats,
            }

        else:
            stats = data.get("daily_stats", {}).get(period, {})
            return {
                "status": "success",
                "period": period,
                "stats": stats if stats else {"message": f"No data found for {period}"},
            }


class WellnessAgent(BaseAgent):
    """Wellness coach focused on sustainable productivity, break management, and burnout prevention."""

    name = "wellness"
    description = "Wellness coach for focus sessions, breaks, screen time, energy tracking, and burnout prevention"
    tier = ModelTier.EXECUTOR
    system_prompt = (
        "You are a wellness coach focused on sustainable productivity and work-life balance. "
        "You help the user:\n"
        "- Start and manage pomodoro/focus sessions\n"
        "- Take meaningful breaks with activity suggestions\n"
        "- Track screen time and work hours\n"
        "- Monitor energy levels and detect burnout patterns\n"
        "- Generate wellness reports with actionable recommendations\n\n"
        "Be encouraging and health-conscious. Celebrate focus wins but also advocate "
        "for rest. If the user seems overworked, gently suggest breaks or stopping for the day."
    )

    offline_responses = {
        "focus": "🎯 Let me start a focus session for you!",
        "break": "☕ Time for a break! You deserve it!",
        "pomodoro": "🍅 Starting a pomodoro session!",
        "energy": "⚡ Let's check your energy levels!",
        "wellness": "🌿 Let me generate your wellness report!",
        "screen_time": "📱 Let me check your screen time!",
        "rest": "😴 Rest is important! Let me help.",
        "burnout": "🚨 Let's check in on your wellbeing!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            StartFocusTool(),
            TakeBreakTool(),
            ScreenTimeTool(),
            EnergyCheckTool(),
            SetWorkHoursTool(),
            DistractionReportTool(),
            WellnessSummaryTool(),
        ]
