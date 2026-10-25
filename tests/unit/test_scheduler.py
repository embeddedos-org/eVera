"""Unit tests for the proactive scheduler — S1: lifecycle + dispatch core.

Covers vera/scheduler.py (issue #46 coverage drive), slice S1 of the
decomposition in docs/scheduler-coverage-scoping.md: __init__
defaults, notification-handler registration/removal, _notify
dispatch, _run_with_metrics, and start()/stop() task spawning under
a stubbed config module. The *_loop bodies and the _check_*/_run_*
workers are S2–S4 and are deliberately not exercised here: every
loop method is replaced with an inert stub before start() runs, so
no real loop body ever runs against real state.

Behaviours pinned as the code implements them today:

- remove_notification_handler does NOT raise for an absent handler:
  it catches the ValueError from list.remove and logs at debug.
- start() always spawns the seven unconditional loops; settings
  only gate the eight conditional ones (planner gates two of them).
- _notify stamps a timestamp onto the notification dict it is
  given (mutating it) and isolates a raising handler: the handlers
  after it still fire.
"""

from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace

import pytest

from vera.scheduler import ProactiveScheduler

LOOP_METHODS = [
    "_reminder_loop",
    "_calendar_loop",
    "_stock_alert_loop",
    "_daily_briefing_loop",
    "_scheduled_tasks_loop",
    "_content_publisher_loop",
    "_spending_alert_loop",
    "_job_scan_loop",
    "_morning_plan_loop",
    "_break_reminder_loop",
    "_digest_loop",
    "_daily_review_reminder_loop",
    "_mood_check_loop",
    "_ticket_scan_loop",
    "_channel_monitor_loop",
]

SETTING_GROUPS = [
    "job_hunter",
    "planner",
    "wellness",
    "digest",
    "emotional",
    "jira",
    "channel_monitor",
]


def make_scheduler(monkeypatch: pytest.MonkeyPatch) -> ProactiveScheduler:
    """A scheduler whose loop methods are inert (sleep until cancelled)."""
    scheduler = ProactiveScheduler()

    async def inert_loop() -> None:
        await asyncio.sleep(3600)

    for name in LOOP_METHODS:
        monkeypatch.setattr(scheduler, name, inert_loop)
    return scheduler


def stub_settings(monkeypatch: pytest.MonkeyPatch, **enabled: bool) -> None:
    """Install a fake ``config`` module with the named groups enabled."""
    settings = SimpleNamespace(
        **{group: SimpleNamespace(enabled=enabled.get(group, False)) for group in SETTING_GROUPS}
    )
    config_module = types.ModuleType("config")
    config_module.settings = settings  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "config", config_module)


def stub_metrics(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """Replace vera.monitoring.metrics with a recorder; return its calls."""
    calls: list[tuple] = []

    def record_scheduler_run(loop_name: str, success: bool, duration_ms: float) -> None:
        calls.append((loop_name, success, duration_ms))

    metrics_module = types.ModuleType("vera.monitoring.metrics")
    metrics_module.record_scheduler_run = record_scheduler_run  # type: ignore[attr-defined]
    monitoring_module = types.ModuleType("vera.monitoring")
    monitoring_module.metrics = metrics_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "vera.monitoring", monitoring_module)
    monkeypatch.setitem(sys.modules, "vera.monitoring.metrics", metrics_module)
    return calls


class TestInit:
    def test_defaults(self):
        scheduler = ProactiveScheduler()
        assert scheduler._running is False
        assert scheduler._tasks == []
        assert scheduler._notification_handlers == []
        assert scheduler._check_interval == 30


class TestNotificationHandlers:
    def test_add_appends_in_order(self):
        scheduler = ProactiveScheduler()

        async def first(_: dict) -> None: ...

        async def second(_: dict) -> None: ...

        scheduler.add_notification_handler(first)
        scheduler.add_notification_handler(second)
        assert scheduler._notification_handlers == [first, second]

    def test_remove_registered_handler(self):
        scheduler = ProactiveScheduler()

        async def handler(_: dict) -> None: ...

        scheduler.add_notification_handler(handler)
        scheduler.remove_notification_handler(handler)
        assert scheduler._notification_handlers == []

    def test_remove_absent_handler_does_not_raise(self):
        # Pinned as-is: the implementation catches list.remove's
        # ValueError and logs at debug instead of propagating it.
        scheduler = ProactiveScheduler()

        async def handler(_: dict) -> None: ...

        scheduler.remove_notification_handler(handler)
        assert scheduler._notification_handlers == []


class TestNotify:
    async def test_all_handlers_receive_the_notification(self):
        scheduler = ProactiveScheduler()
        received: list[dict] = []

        async def handler(notification: dict) -> None:
            received.append(notification)

        scheduler.add_notification_handler(handler)
        scheduler.add_notification_handler(handler)
        notification = {"type": "reminder", "text": "stand up"}
        await scheduler._notify(notification)
        assert received == [notification, notification]

    async def test_notify_stamps_a_timestamp_onto_the_dict(self):
        scheduler = ProactiveScheduler()
        notification = {"type": "reminder"}
        await scheduler._notify(notification)
        assert "timestamp" in notification

    async def test_raising_handler_does_not_block_the_others(self):
        scheduler = ProactiveScheduler()
        received: list[str] = []

        async def bad(_: dict) -> None:
            raise RuntimeError("handler exploded")

        async def good(_: dict) -> None:
            received.append("fired")

        scheduler.add_notification_handler(bad)
        scheduler.add_notification_handler(good)
        await scheduler._notify({"type": "reminder"})
        assert received == ["fired"]

    async def test_no_handlers_is_a_no_op(self):
        scheduler = ProactiveScheduler()
        notification = {"type": "reminder"}
        await scheduler._notify(notification)
        assert "timestamp" in notification


class TestRunWithMetrics:
    async def test_success_records_success(self, monkeypatch: pytest.MonkeyPatch):
        calls = stub_metrics(monkeypatch)
        scheduler = ProactiveScheduler()
        ran = False

        async def work() -> None:
            nonlocal ran
            ran = True

        await scheduler._run_with_metrics("reminder", work)
        assert ran is True
        assert len(calls) == 1
        loop_name, success, duration_ms = calls[0]
        assert loop_name == "reminder"
        assert success is True
        assert duration_ms >= 0

    async def test_failure_records_failure_and_reraises(self, monkeypatch: pytest.MonkeyPatch):
        calls = stub_metrics(monkeypatch)
        scheduler = ProactiveScheduler()

        async def work() -> None:
            raise RuntimeError("worker exploded")

        with pytest.raises(RuntimeError, match="worker exploded"):
            await scheduler._run_with_metrics("stock", work)
        assert len(calls) == 1
        loop_name, success, _ = calls[0]
        assert loop_name == "stock"
        assert success is False


class TestStartStop:
    async def test_all_disabled_spawns_only_the_seven_base_loops(self, monkeypatch: pytest.MonkeyPatch):
        stub_settings(monkeypatch)
        scheduler = make_scheduler(monkeypatch)
        await scheduler.start()
        try:
            assert scheduler._running is True
            assert len(scheduler._tasks) == 7
        finally:
            await scheduler.stop()
        assert scheduler._running is False

    async def test_planner_enabled_adds_two_loops(self, monkeypatch: pytest.MonkeyPatch):
        # planner gates both _morning_plan_loop and
        # _daily_review_reminder_loop in start().
        stub_settings(monkeypatch, planner=True)
        scheduler = make_scheduler(monkeypatch)
        await scheduler.start()
        try:
            assert len(scheduler._tasks) == 9
        finally:
            await scheduler.stop()

    async def test_single_flag_adds_one_loop(self, monkeypatch: pytest.MonkeyPatch):
        stub_settings(monkeypatch, job_hunter=True)
        scheduler = make_scheduler(monkeypatch)
        await scheduler.start()
        try:
            assert len(scheduler._tasks) == 8
        finally:
            await scheduler.stop()

    async def test_all_enabled_spawns_fifteen_loops(self, monkeypatch: pytest.MonkeyPatch):
        stub_settings(monkeypatch, **dict.fromkeys(SETTING_GROUPS, True))
        scheduler = make_scheduler(monkeypatch)
        await scheduler.start()
        try:
            assert len(scheduler._tasks) == 15
        finally:
            await scheduler.stop()

    async def test_stop_cancels_all_tasks(self, monkeypatch: pytest.MonkeyPatch):
        stub_settings(monkeypatch)
        scheduler = make_scheduler(monkeypatch)
        await scheduler.start()
        tasks = list(scheduler._tasks)
        await scheduler.stop()
        assert scheduler._running is False
        assert all(task.cancelled() or task.done() for task in tasks)

    async def test_stop_without_start_is_clean(self, monkeypatch: pytest.MonkeyPatch):
        scheduler = make_scheduler(monkeypatch)
        await scheduler.stop()
        assert scheduler._running is False


# ---------------------------------------------------------------------------
# S2: file-state checkers (docs/scheduler-coverage-scoping.md)
#
# The six _check_* workers below own no imports beyond the module's
# stdlib set: all state is JSON files under DATA_DIR, patched per
# test to a tmp dir, and a recording handler captures _notify
# output. Write-back is asserted wherever a checker mutates the
# file it read — those mutations are the behaviour being pinned.
# ---------------------------------------------------------------------------

import json
from datetime import datetime, timedelta
from pathlib import Path

import vera.scheduler as scheduler_module


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(scheduler_module, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def recorder():
    """Return (handler, received) — an async handler and its inbox."""
    received: list[dict] = []

    async def record(notification: dict) -> None:
        received.append(notification)

    return record, received


def make_checking_scheduler(record) -> ProactiveScheduler:
    scheduler = ProactiveScheduler()
    scheduler.add_notification_handler(record)
    return scheduler


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload))


def read_json(path: Path):
    return json.loads(path.read_text())


def iso(dt: datetime) -> str:
    return dt.isoformat()


class TestCheckReminders:
    async def test_missing_file_is_silent(self, data_dir, recorder):
        record, received = recorder
        scheduler = make_checking_scheduler(record)
        await scheduler._check_reminders()
        assert received == []

    async def test_malformed_json_is_silent(self, data_dir, recorder):
        record, received = recorder
        (data_dir / "reminders.json").write_text("{not json")
        scheduler = make_checking_scheduler(record)
        await scheduler._check_reminders()
        assert received == []

    async def test_due_reminder_fires_and_is_dismissed_on_disk(self, data_dir, recorder):
        record, received = recorder
        path = data_dir / "reminders.json"
        due = {"text": "stretch", "trigger_at": iso(datetime.now() - timedelta(minutes=5))}
        future = {"text": "later", "trigger_at": iso(datetime.now() + timedelta(hours=1))}
        dismissed = {
            "text": "old",
            "trigger_at": iso(datetime.now() - timedelta(days=1)),
            "dismissed": True,
        }
        write_json(path, [due, future, dismissed])

        scheduler = make_checking_scheduler(record)
        await scheduler._check_reminders()

        assert len(received) == 1
        assert received[0]["type"] == "reminder"
        assert "stretch" in received[0]["message"]
        # Write-back: only the fired reminder is marked dismissed.
        on_disk = read_json(path)
        assert on_disk[0]["dismissed"] is True
        assert "dismissed" not in on_disk[1]
        assert on_disk[2]["dismissed"] is True

    async def test_nothing_due_leaves_file_untouched(self, data_dir, recorder):
        record, received = recorder
        path = data_dir / "reminders.json"
        original = json.dumps(
            [{"text": "later", "trigger_at": iso(datetime.now() + timedelta(hours=2))}]
        )
        path.write_text(original)
        scheduler = make_checking_scheduler(record)
        await scheduler._check_reminders()
        assert received == []
        assert path.read_text() == original


class TestCheckUpcomingEvents:
    async def test_missing_and_malformed_are_silent(self, data_dir, recorder):
        record, received = recorder
        scheduler = make_checking_scheduler(record)
        await scheduler._check_upcoming_events()
        (data_dir / "calendar.json").write_text("][")
        await scheduler._check_upcoming_events()
        assert received == []

    async def test_event_within_15_minutes_fires_and_marks_notified(self, data_dir, recorder):
        record, received = recorder
        path = data_dir / "calendar.json"
        now = datetime.now()
        soon = {
            "title": "standup",
            "date": now.strftime("%Y-%m-%d"),
            "time": (now + timedelta(minutes=10)).strftime("%H:%M"),
        }
        far = {
            "title": "later today",
            "date": now.strftime("%Y-%m-%d"),
            "time": (now + timedelta(hours=3)).strftime("%H:%M"),
        }
        past = {
            "title": "already started",
            "date": now.strftime("%Y-%m-%d"),
            "time": (now - timedelta(minutes=30)).strftime("%H:%M"),
        }
        other_day = {
            "title": "tomorrow",
            "date": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
            "time": (now + timedelta(minutes=5)).strftime("%H:%M"),
        }
        no_time = {"title": "all day", "date": now.strftime("%Y-%m-%d")}
        already = dict(soon, title="pinged", notified=True)
        bad_time = {"title": "broken", "date": now.strftime("%Y-%m-%d"), "time": "25:99"}
        write_json(path, [soon, far, past, other_day, no_time, already, bad_time])

        scheduler = make_checking_scheduler(record)
        await scheduler._check_upcoming_events()

        assert len(received) == 1
        assert received[0]["type"] == "calendar"
        assert "standup" in received[0]["message"]
        on_disk = read_json(path)
        assert on_disk[0]["notified"] is True
        assert "notified" not in on_disk[1]
        assert on_disk[5]["notified"] is True

    async def test_file_is_rewritten_even_when_nothing_fires(self, data_dir, recorder):
        # Pin: unlike the other checkers, _check_upcoming_events
        # writes the file back unconditionally at the end.
        record, received = recorder
        path = data_dir / "calendar.json"
        events = [{"title": "far", "date": "2999-01-01", "time": "09:00"}]
        path.write_text(json.dumps(events))
        scheduler = make_checking_scheduler(record)
        await scheduler._check_upcoming_events()
        assert received == []
        assert read_json(path) == events


class TestCheckScheduledTasks:
    async def test_missing_and_malformed_are_silent(self, data_dir, recorder):
        record, received = recorder
        scheduler = make_checking_scheduler(record)
        await scheduler._check_scheduled_tasks()
        (data_dir / "scheduled_tasks.json").write_text("nope")
        await scheduler._check_scheduled_tasks()
        assert received == []

    async def test_interval_task_due_fires_and_writes_back(self, data_dir, recorder):
        record, received = recorder
        path = data_dir / "scheduled_tasks.json"
        due = {
            "name": "sync",
            "description": "sync things",
            "enabled": True,
            "schedule": {"type": "interval", "minutes": 30},
            "last_run_ts": (datetime.now() - timedelta(hours=2)).timestamp(),
            "run_count": 4,
        }
        not_due = {
            "name": "fresh",
            "schedule": {"type": "interval", "minutes": 30},
            "last_run_ts": datetime.now().timestamp(),
        }
        disabled = {
            "name": "off",
            "enabled": False,
            "schedule": {"type": "interval", "minutes": 1},
            "last_run_ts": 0,
        }
        unknown = {"name": "mystery", "schedule": {"type": "cron"}, "last_run_ts": 0}
        write_json(path, [due, not_due, disabled, unknown])

        scheduler = make_checking_scheduler(record)
        await scheduler._check_scheduled_tasks()

        assert len(received) == 1
        assert received[0]["type"] == "scheduled_task"
        assert "sync" in received[0]["message"]
        on_disk = read_json(path)
        assert on_disk[0]["run_count"] == 5
        assert on_disk[0]["last_run"] == datetime.now().strftime("%Y-%m-%d")
        assert on_disk[0]["last_run_ts"] > due["last_run_ts"]
        assert "run_count" not in on_disk[1]

    async def test_daily_task_at_current_time_fires_once_per_day(self, data_dir, recorder):
        record, received = recorder
        path = data_dir / "scheduled_tasks.json"
        now = datetime.now()
        task = {
            "name": "report",
            "schedule": {"type": "daily", "time": now.strftime("%H:%M")},
        }
        write_json(path, [task])
        scheduler = make_checking_scheduler(record)
        await scheduler._check_scheduled_tasks()
        assert len(received) == 1
        # Second pass in the same minute: last_run is today, silent.
        await scheduler._check_scheduled_tasks()
        assert len(received) == 1

    async def test_weekly_task_on_matching_day_fires(self, data_dir, recorder):
        record, received = recorder
        path = data_dir / "scheduled_tasks.json"
        now = datetime.now()
        task = {
            "name": "weekly report",
            "schedule": {
                "type": "weekly",
                "day": now.strftime("%A"),
                "time": now.strftime("%H:%M"),
            },
        }
        other_day = {
            "name": "not today",
            "schedule": {
                "type": "weekly",
                "day": (now + timedelta(days=1)).strftime("%A"),
                "time": now.strftime("%H:%M"),
            },
        }
        write_json(path, [task, other_day])
        scheduler = make_checking_scheduler(record)
        await scheduler._check_scheduled_tasks()
        assert len(received) == 1
        assert "weekly report" in received[0]["message"]


class TestCheckScheduledPosts:
    async def test_missing_and_malformed_are_silent(self, data_dir, recorder):
        record, received = recorder
        scheduler = make_checking_scheduler(record)
        await scheduler._check_scheduled_posts()
        (data_dir / "scheduled_posts.json").write_text("{")
        await scheduler._check_scheduled_posts()
        assert received == []

    async def test_due_post_fires_and_moves_to_ready_to_publish(self, data_dir, recorder):
        record, received = recorder
        path = data_dir / "scheduled_posts.json"
        due = {
            "platform": "mastodon",
            "content": "hello world",
            "status": "scheduled",
            "schedule_at": iso(datetime.now() - timedelta(minutes=1)),
        }
        future = dict(due, content="later", schedule_at=iso(datetime.now() + timedelta(hours=1)))
        published = dict(due, content="done", status="published")
        broken = {"status": "scheduled"}  # no schedule_at: skipped
        bad_date = dict(due, content="bad", schedule_at="not-a-date")
        write_json(path, [due, future, published, broken, bad_date])

        scheduler = make_checking_scheduler(record)
        await scheduler._check_scheduled_posts()

        assert len(received) == 1
        assert received[0]["type"] == "content_publish"
        assert "mastodon" in received[0]["message"]
        on_disk = read_json(path)
        assert on_disk[0]["status"] == "ready_to_publish"
        assert "notified_at" in on_disk[0]
        assert on_disk[1]["status"] == "scheduled"


class TestCheckSpendingAlerts:
    def finance(self, budgets, transactions):
        return {"budgets": budgets, "transactions": transactions}

    def txn(self, amount, category="Food", when=None):
        when = when or datetime.now()
        return {"amount": amount, "category": category, "date": when.strftime("%Y-%m-%d")}

    async def test_missing_malformed_and_budgetless_are_silent(self, data_dir, recorder):
        record, received = recorder
        scheduler = make_checking_scheduler(record)
        await scheduler._check_spending_alerts()
        write_json(data_dir / "finance.json", self.finance({}, [self.txn(-500)]))
        await scheduler._check_spending_alerts()
        (data_dir / "finance.json").write_text("###")
        await scheduler._check_spending_alerts()
        assert received == []

    async def test_warning_band_and_exceeded_band(self, data_dir, recorder):
        record, received = recorder
        budgets = {"Food": 100, "Travel": 100, "Books": 100}
        transactions = [
            self.txn(-85, "Food"),  # 85% -> warning
            self.txn(-120, "Travel"),  # 120% -> exceeded
            self.txn(-10, "Books"),  # 10% -> silent
            self.txn(500, "Food"),  # income: ignored
            self.txn(-999, "Food", when=datetime.now().replace(day=1) - timedelta(days=1)),
        ]
        write_json(data_dir / "finance.json", self.finance(budgets, transactions))
        scheduler = make_checking_scheduler(record)
        await scheduler._check_spending_alerts()

        by_type = {n["data"]["category"]: n["type"] for n in received}
        assert by_type == {"Food": "budget_warning", "Travel": "budget_alert"}

    async def test_zero_budget_never_alerts(self, data_dir, recorder):
        record, received = recorder
        write_json(
            data_dir / "finance.json",
            self.finance({"Food": 0}, [self.txn(-50, "Food")]),
        )
        scheduler = make_checking_scheduler(record)
        await scheduler._check_spending_alerts()
        assert received == []

    async def test_uncategorised_spending_counts_as_other(self, data_dir, recorder):
        record, received = recorder
        txn = {"amount": -95, "date": datetime.now().strftime("%Y-%m-%d")}
        write_json(data_dir / "finance.json", self.finance({"Other": 100}, [txn]))
        scheduler = make_checking_scheduler(record)
        await scheduler._check_spending_alerts()
        assert len(received) == 1
        assert received[0]["data"]["category"] == "Other"


class TestCheckBreakNeeded:
    async def test_missing_and_malformed_are_silent(self, data_dir, recorder):
        record, received = recorder
        scheduler = make_checking_scheduler(record)
        await scheduler._check_break_needed(60)
        (data_dir / "wellness.json").write_text("x")
        await scheduler._check_break_needed(60)
        assert received == []

    async def test_no_active_session_is_silent(self, data_dir, recorder):
        record, received = recorder
        ended = {"start": iso(datetime.now() - timedelta(hours=5)), "end": iso(datetime.now())}
        write_json(data_dir / "wellness.json", {"sessions": [ended], "breaks": []})
        scheduler = make_checking_scheduler(record)
        await scheduler._check_break_needed(30)
        assert received == []

    async def test_long_active_session_fires(self, data_dir, recorder):
        record, received = recorder
        active = {"start": iso(datetime.now() - timedelta(minutes=95))}
        write_json(data_dir / "wellness.json", {"sessions": [active], "breaks": []})
        scheduler = make_checking_scheduler(record)
        await scheduler._check_break_needed(60)
        assert len(received) == 1
        assert received[0]["type"] == "break_reminder"
        assert received[0]["data"]["minutes_worked"] >= 95

    async def test_short_session_and_recent_break_are_silent(self, data_dir, recorder):
        record, received = recorder
        scheduler = make_checking_scheduler(record)
        active = {"start": iso(datetime.now() - timedelta(minutes=20))}
        write_json(data_dir / "wellness.json", {"sessions": [active], "breaks": []})
        await scheduler._check_break_needed(60)
        # A recent break resets the clock even for an old session.
        old_session = {"start": iso(datetime.now() - timedelta(hours=4))}
        recent_break = {"start": iso(datetime.now() - timedelta(minutes=10))}
        write_json(
            data_dir / "wellness.json",
            {"sessions": [old_session], "breaks": [recent_break]},
        )
        await scheduler._check_break_needed(60)
        assert received == []

    async def test_malformed_break_start_falls_back_to_session_start(self, data_dir, recorder):
        record, received = recorder
        active = {"start": iso(datetime.now() - timedelta(minutes=90))}
        write_json(
            data_dir / "wellness.json",
            {"sessions": [active], "breaks": [{"start": "not-a-time"}]},
        )
        scheduler = make_checking_scheduler(record)
        await scheduler._check_break_needed(60)
        assert len(received) == 1
