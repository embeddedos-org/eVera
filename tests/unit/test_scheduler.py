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
