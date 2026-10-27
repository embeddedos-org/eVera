"""Unit tests for the proactive scheduler — S5: the loop layer.

Covers vera/scheduler.py (issue #46 coverage drive), slice S5 of the
decomposition in docs/scheduler-coverage-scoping.md: the fifteen
*_loop wrappers. S1 covered __init__ / handlers / _notify /
_run_with_metrics / start() / stop(); S2–S4 covered every worker the
loops call. What remained uncovered was the loop bodies themselves
(the while / gate / sleep lines, 78.46% isolation baseline).

Discipline (from the scoping doc): test workers, not loops — one
iteration per loop, obtained only by stubbing asyncio.sleep so the
first sleep flips _running to False and returns immediately. No
loop is refactored to make it testable, and no test ever really
sleeps. Time-gated loops get a fixed clock by replacing the module's
datetime class with a subclass whose now() returns a pinned value.

Behaviour pinned as the code implements it:

- Every loop swallows a worker exception (try/except + warning log)
  and still reaches its sleep; nothing propagates out of a loop.
  The briefing loop's anti-duplicate sleep(120) sits OUTSIDE its
  try block, so a failed briefing still sleeps 120 then 60.
- Sleep delays are the literal values in each body: reminder uses
  the instance _check_interval (30), calendar 300, stock 600,
  scheduled-tasks / content-publisher / break-reminder 60,
  spending 3600; the settings loops use their configured interval
  (job scan / ticket scan / channel monitor / mood check) and the
  time-of-day loops sleep 60 between checks, plus 120 after firing.
- The time gates are exact: stock fires only for 9 <= hour <= 16,
  the briefing only at hour 8 with minute < 2, and the planner /
  digest loops only when now matches the configured HH:MM exactly
  (hour AND minute).
- _daily_review_reminder_loop has no separate worker: it calls
  _notify directly with a daily_review_reminder payload.
- _mood_check_loop passes (settings, None, timedelta(hours=4)) to
  _run_mood_check on every iteration.
- A loop entered with _running False returns immediately: no
  worker call, no sleep.
"""

from __future__ import annotations

import asyncio
import sys
import types
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import vera.scheduler as scheduler_module
from vera.scheduler import ProactiveScheduler


# ---------------------------------------------------------------------------
# Settings / config stub (the S1/S3 sys.modules pattern)
# ---------------------------------------------------------------------------


def make_settings(**overrides) -> SimpleNamespace:
    settings = SimpleNamespace(
        job_hunter=SimpleNamespace(enabled=True, scan_interval_minutes=15),
        planner=SimpleNamespace(
            enabled=True, morning_plan_time="10:00", daily_review_time="10:00"
        ),
        wellness=SimpleNamespace(enabled=True, break_reminder_interval_min=45),
        digest=SimpleNamespace(enabled=True, auto_digest=True, digest_time="10:00"),
        emotional=SimpleNamespace(
            enabled=True, proactive_empathy_enabled=True, mood_check_interval_min=30
        ),
        jira=SimpleNamespace(enabled=True, scan_interval_minutes=20),
        channel_monitor=SimpleNamespace(enabled=True, poll_interval_min=5),
    )
    for section, values in overrides.items():
        for key, value in values.items():
            setattr(getattr(settings, section), key, value)
    return settings


@pytest.fixture
def config_stub(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    settings = make_settings()
    module = types.ModuleType("config")
    module.settings = settings  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "config", module)
    return settings


# ---------------------------------------------------------------------------
# Sleep harness: record delays, flip _running off on the first sleep
# ---------------------------------------------------------------------------


class SleepRecorder:
    def __init__(self, scheduler: ProactiveScheduler) -> None:
        self.scheduler = scheduler
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)
        self.scheduler._running = False


@pytest.fixture
def sleep_recorder(monkeypatch: pytest.MonkeyPatch):
    def install(scheduler: ProactiveScheduler) -> SleepRecorder:
        recorder = SleepRecorder(scheduler)
        monkeypatch.setattr(asyncio, "sleep", recorder)
        return recorder

    return install


def running_scheduler() -> ProactiveScheduler:
    scheduler = ProactiveScheduler()
    scheduler._running = True
    return scheduler


def stub_metrics(scheduler: ProactiveScheduler) -> list[tuple[str, object]]:
    """Replace _run_with_metrics: record (name, worker) and run the worker."""
    calls: list[tuple[str, object]] = []

    async def fake_metrics(name, coro):
        calls.append((name, coro))
        await coro()

    scheduler._run_with_metrics = fake_metrics  # type: ignore[method-assign]
    return calls


def fixed_clock(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: D102 - test double
            return moment

    monkeypatch.setattr(scheduler_module, "datetime", FixedDateTime)


# ---------------------------------------------------------------------------
# Simple loops (no settings gate)
# ---------------------------------------------------------------------------


class TestSimpleLoops:
    async def test_reminder_loop_one_iteration(self, sleep_recorder):
        scheduler = running_scheduler()
        metrics = stub_metrics(scheduler)
        worker = AsyncMock()
        scheduler._check_reminders = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._reminder_loop()

        assert worker.await_count == 1
        assert [name for name, _ in metrics] == ["reminder"]
        assert sleeps.delays == [scheduler._check_interval]

    async def test_calendar_loop_one_iteration(self, sleep_recorder):
        scheduler = running_scheduler()
        metrics = stub_metrics(scheduler)
        worker = AsyncMock()
        scheduler._check_upcoming_events = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._calendar_loop()

        assert worker.await_count == 1
        assert [name for name, _ in metrics] == ["calendar"]
        assert sleeps.delays == [300]

    async def test_scheduled_tasks_loop_one_iteration(self, sleep_recorder):
        scheduler = running_scheduler()
        metrics = stub_metrics(scheduler)
        worker = AsyncMock()
        scheduler._check_scheduled_tasks = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._scheduled_tasks_loop()

        assert worker.await_count == 1
        assert [name for name, _ in metrics] == ["scheduled_tasks"]
        assert sleeps.delays == [60]

    async def test_content_publisher_loop_one_iteration(self, sleep_recorder):
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._check_scheduled_posts = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._content_publisher_loop()

        assert worker.await_count == 1
        assert sleeps.delays == [60]

    async def test_spending_alert_loop_one_iteration(self, sleep_recorder):
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._check_spending_alerts = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._spending_alert_loop()

        assert worker.await_count == 1
        assert sleeps.delays == [3600]

    async def test_worker_exception_is_swallowed_and_sleep_still_happens(
        self, sleep_recorder
    ):
        scheduler = running_scheduler()
        stub_metrics(scheduler)
        scheduler._check_reminders = AsyncMock(
            side_effect=RuntimeError("worker exploded")
        )
        sleeps = sleep_recorder(scheduler)

        await scheduler._reminder_loop()  # must not raise

        assert sleeps.delays == [scheduler._check_interval]


# Every loop wraps its worker in the same try/except + warning shape:
# a raising worker is swallowed and the loop still reaches its sleep.
# (loop, worker attribute, needs config stub, fixed clock, delays after raise)
RAISE_CASES = [
    ("_reminder_loop", "_check_reminders", False, None, [30]),
    ("_calendar_loop", "_check_upcoming_events", False, None, [300]),
    ("_stock_alert_loop", "_check_stock_alerts", False, datetime(2026, 1, 5, 10, 0), [600]),
    ("_daily_briefing_loop", "_send_daily_briefing", False, datetime(2026, 1, 5, 8, 0), [120, 60]),
    ("_scheduled_tasks_loop", "_check_scheduled_tasks", False, None, [60]),
    ("_content_publisher_loop", "_check_scheduled_posts", False, None, [60]),
    ("_spending_alert_loop", "_check_spending_alerts", False, None, [3600]),
    ("_job_scan_loop", "_run_job_scan", True, None, [900]),
    ("_morning_plan_loop", "_run_morning_plan", True, datetime(2026, 1, 5, 10, 0), [60]),
    ("_break_reminder_loop", "_check_break_needed", True, None, [60]),
    ("_digest_loop", "_run_digest", True, datetime(2026, 1, 5, 10, 0), [60]),
    ("_daily_review_reminder_loop", "_notify", True, datetime(2026, 1, 5, 10, 0), [60]),
    ("_mood_check_loop", "_run_mood_check", True, None, [1800]),
    ("_ticket_scan_loop", "_run_ticket_scan", True, None, [1200]),
    ("_channel_monitor_loop", "_run_channel_monitor", True, None, [300]),
]


class TestWorkerRaises:
    @pytest.mark.parametrize(
        "loop_name,worker_attr,needs_config,moment,expected_delays", RAISE_CASES
    )
    async def test_raising_worker_is_swallowed_by_every_loop(
        self,
        config_stub,
        sleep_recorder,
        monkeypatch,
        loop_name,
        worker_attr,
        needs_config,
        moment,
        expected_delays,
    ):
        if moment is not None:
            fixed_clock(monkeypatch, moment)
        scheduler = running_scheduler()
        stub_metrics(scheduler)
        setattr(
            scheduler,
            worker_attr,
            AsyncMock(side_effect=RuntimeError("worker exploded")),
        )
        sleeps = sleep_recorder(scheduler)

        await getattr(scheduler, loop_name)()  # must not raise

        assert sleeps.delays == expected_delays


class TestStockAlertLoop:
    async def test_fires_during_market_hours(self, sleep_recorder, monkeypatch):
        fixed_clock(monkeypatch, datetime(2026, 1, 5, 10, 0))
        scheduler = running_scheduler()
        metrics = stub_metrics(scheduler)
        worker = AsyncMock()
        scheduler._check_stock_alerts = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._stock_alert_loop()

        assert worker.await_count == 1
        assert [name for name, _ in metrics] == ["stock_alert"]
        assert sleeps.delays == [600]

    async def test_skips_outside_market_hours(self, sleep_recorder, monkeypatch):
        fixed_clock(monkeypatch, datetime(2026, 1, 5, 20, 0))
        scheduler = running_scheduler()
        stub_metrics(scheduler)
        worker = AsyncMock()
        scheduler._check_stock_alerts = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._stock_alert_loop()

        assert worker.await_count == 0
        assert sleeps.delays == [600]


class TestDailyBriefingLoop:
    async def test_fires_at_eight_am(self, sleep_recorder, monkeypatch):
        fixed_clock(monkeypatch, datetime(2026, 1, 5, 8, 0))
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._send_daily_briefing = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._daily_briefing_loop()

        assert worker.await_count == 1
        # 120s anti-duplicate sleep inside the gate, then the 60s tick.
        assert sleeps.delays == [120, 60]

    async def test_skips_outside_the_briefing_minute(self, sleep_recorder, monkeypatch):
        fixed_clock(monkeypatch, datetime(2026, 1, 5, 9, 0))
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._send_daily_briefing = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._daily_briefing_loop()

        assert worker.await_count == 0
        assert sleeps.delays == [60]


# ---------------------------------------------------------------------------
# Settings-gated loops (config stub installed, everything enabled)
# ---------------------------------------------------------------------------


class TestSettingsLoops:
    async def test_job_scan_loop_one_iteration(self, config_stub, sleep_recorder):
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._run_job_scan = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._job_scan_loop()

        assert worker.await_count == 1
        assert sleeps.delays == [15 * 60]

    async def test_break_reminder_loop_passes_the_configured_interval(
        self, config_stub, sleep_recorder
    ):
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._check_break_needed = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._break_reminder_loop()

        assert worker.await_args_list[0].args == (45,)
        assert worker.await_count == 1
        assert sleeps.delays == [60]

    async def test_mood_check_loop_passes_settings_and_cooldown(
        self, config_stub, sleep_recorder
    ):
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._run_mood_check = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._mood_check_loop()

        assert worker.await_count == 1
        args = worker.await_args_list[0].args
        assert args[0] is config_stub
        assert args[1] is None
        assert args[2] == timedelta(hours=4)
        assert sleeps.delays == [30 * 60]

    async def test_ticket_scan_loop_one_iteration(self, config_stub, sleep_recorder):
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._run_ticket_scan = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._ticket_scan_loop()

        assert worker.await_count == 1
        assert sleeps.delays == [20 * 60]

    async def test_channel_monitor_loop_one_iteration(
        self, config_stub, sleep_recorder
    ):
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._run_channel_monitor = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._channel_monitor_loop()

        assert worker.await_count == 1
        assert sleeps.delays == [5 * 60]


class TestTimeOfDayLoops:
    async def test_morning_plan_fires_at_the_configured_time(
        self, config_stub, sleep_recorder, monkeypatch
    ):
        fixed_clock(monkeypatch, datetime(2026, 1, 5, 10, 0))
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._run_morning_plan = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._morning_plan_loop()

        assert worker.await_count == 1
        assert sleeps.delays == [120, 60]

    async def test_morning_plan_skips_at_other_times(
        self, config_stub, sleep_recorder, monkeypatch
    ):
        fixed_clock(monkeypatch, datetime(2026, 1, 5, 11, 0))
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._run_morning_plan = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._morning_plan_loop()

        assert worker.await_count == 0
        assert sleeps.delays == [60]

    async def test_digest_fires_at_the_configured_time(
        self, config_stub, sleep_recorder, monkeypatch
    ):
        fixed_clock(monkeypatch, datetime(2026, 1, 5, 10, 0))
        scheduler = running_scheduler()
        worker = AsyncMock()
        scheduler._run_digest = worker
        sleeps = sleep_recorder(scheduler)

        await scheduler._digest_loop()

        assert worker.await_count == 1
        assert sleeps.delays == [120, 60]

    async def test_daily_review_notifies_directly_at_the_configured_time(
        self, config_stub, sleep_recorder, monkeypatch
    ):
        fixed_clock(monkeypatch, datetime(2026, 1, 5, 10, 0))
        scheduler = running_scheduler()
        notify = AsyncMock()
        scheduler._notify = notify
        sleeps = sleep_recorder(scheduler)

        await scheduler._daily_review_reminder_loop()

        assert notify.await_count == 1
        payload = notify.await_args_list[0].args[0]
        assert payload["type"] == "daily_review_reminder"
        assert payload["data"] == {"date": "2026-01-05"}
        assert sleeps.delays == [120, 60]


# ---------------------------------------------------------------------------
# Already-stopped: every loop returns before any worker call or sleep
# ---------------------------------------------------------------------------

ALL_LOOPS = [
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


class TestAlreadyStopped:
    @pytest.mark.parametrize("loop_name", ALL_LOOPS)
    async def test_loop_entered_stopped_does_nothing(
        self, config_stub, sleep_recorder, loop_name
    ):
        scheduler = ProactiveScheduler()  # _running is False
        metrics = stub_metrics(scheduler)
        sleeps = sleep_recorder(scheduler)

        await getattr(scheduler, loop_name)()

        assert metrics == []
        assert sleeps.delays == []
