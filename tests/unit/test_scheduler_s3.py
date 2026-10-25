"""Unit tests for the proactive scheduler — S3: settings-gated run wrappers.

Covers vera/scheduler.py (issue #46 coverage drive), slice S3 of the
decomposition in docs/scheduler-coverage-scoping.md: _run_job_scan,
_run_morning_plan, _run_digest, _run_ticket_scan, _run_channel_monitor,
_run_mood_check, _send_daily_briefing, and — as the preservation test
for the daily-review surface — the real _daily_review_reminder_loop
body fired once on its cadence override. Every agent / messaging /
emotional import a worker performs is stubbed in sys.modules
per-worker (the S1 config-stub pattern, extended); no test imports a
real agent tool, the real config settings, or a real provider.

Corrections to the scoping doc, from reading the code at HEAD:

- The doc's "_run_daily_review (ticket scan)" conflates two workers.
  The ticket scan is _run_ticket_scan; there is no _run_daily_review
  method — the daily-review notification is built inline in
  _daily_review_reminder_loop, so that surface is covered by testing
  the loop itself on a patched cadence (scoping position (b) allows
  one loop iteration per family where it is free).
- _run_job_scan's "result cap" is a daily-application cap:
  _today_application_count() >= settings.job_hunter.
  max_daily_applications skips the scan before the tool is built.
- _send_daily_briefing has no settings gate and no imports beyond
  the module's stdlib set — it is a DATA_DIR file-state worker like
  the S2 checkers, and it always notifies, even with no state files.
- _run_channel_monitor compares message timestamps as strings, so
  a ts of "10" sorts as OLDER than a last_ts of "9". Pinned as-is.

Behaviours are pinned as the code implements them, quirks included;
a behaviour that looks wrong is a filed issue, not a fix inside a
coverage slice.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import vera.scheduler as scheduler_module
from vera.scheduler import ProactiveScheduler


# ---------------------------------------------------------------------------
# Shared fixtures and stub helpers
# ---------------------------------------------------------------------------


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


def make_scheduler(record) -> ProactiveScheduler:
    scheduler = ProactiveScheduler()
    scheduler.add_notification_handler(record)
    return scheduler


def install_module(monkeypatch: pytest.MonkeyPatch, name: str, **attrs) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def stub_config(monkeypatch: pytest.MonkeyPatch, **groups) -> SimpleNamespace:
    """Install a fake ``config`` module; groups are SimpleNamespaces."""
    settings = SimpleNamespace(**groups)
    install_module(monkeypatch, "config", settings=settings)
    return settings


def stub_tool_module(
    monkeypatch: pytest.MonkeyPatch, dotted: str, tool_name: str, result=None, exc=None
):
    """Stub ``vera.brain.agents.<x>``-style module with a recording tool.

    Returns a state dict: {"constructed": n, "calls": [kwargs, ...]}.
    """
    state = {"constructed": 0, "calls": []}

    class StubTool:
        def __init__(self) -> None:
            state["constructed"] += 1

        async def execute(self, **kwargs):
            state["calls"].append(kwargs)
            if exc is not None:
                raise exc
            return result

    parts = dotted.split(".")
    for i in range(2, len(parts)):
        install_module(monkeypatch, ".".join(parts[:i]))
    install_module(monkeypatch, dotted, **{tool_name: StubTool})
    return state


def job_hunter_settings(max_daily: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        job_hunter=SimpleNamespace(enabled=True, max_daily_applications=max_daily)
    )


# ---------------------------------------------------------------------------
# _run_job_scan
# ---------------------------------------------------------------------------


class TestRunJobScan:
    def _stub_scanner(self, monkeypatch, result, daily_count: int = 0):
        state = stub_tool_module(
            monkeypatch, "vera.brain.agents.job_hunter", "RunJobScanTool", result=result
        )
        module = sys.modules["vera.brain.agents.job_hunter"]
        module._today_application_count = lambda: daily_count
        return state

    async def test_daily_cap_skips_before_building_the_tool(self, monkeypatch, recorder):
        record, received = recorder
        stub_config(monkeypatch, **job_hunter_settings(max_daily=3).__dict__)
        state = self._stub_scanner(monkeypatch, {"applied": 9}, daily_count=3)
        await make_scheduler(record)._run_job_scan()
        assert state["constructed"] == 0
        assert received == []

    async def test_applied_jobs_notify_excited(self, monkeypatch, recorder):
        record, received = recorder
        stub_config(monkeypatch, **job_hunter_settings().__dict__)
        result = {"applied": 2, "skipped": 1, "failed": 0, "total_found": 3}
        self._stub_scanner(monkeypatch, result)
        await make_scheduler(record)._run_job_scan()
        assert len(received) == 1
        note = received[0]
        assert note["type"] == "job_scan"
        assert note["mood"] == "excited"
        assert "applied to 2" in note["message"]
        assert note["data"] is result

    async def test_failures_without_applications_notify_thinking(self, monkeypatch, recorder):
        record, received = recorder
        stub_config(monkeypatch, **job_hunter_settings().__dict__)
        self._stub_scanner(
            monkeypatch, {"applied": 0, "skipped": 0, "failed": 1, "total_found": 1}
        )
        await make_scheduler(record)._run_job_scan()
        assert len(received) == 1
        assert received[0]["mood"] == "thinking"

    async def test_all_skipped_is_silent(self, monkeypatch, recorder):
        record, received = recorder
        stub_config(monkeypatch, **job_hunter_settings().__dict__)
        self._stub_scanner(
            monkeypatch, {"applied": 0, "skipped": 4, "failed": 0, "total_found": 4}
        )
        await make_scheduler(record)._run_job_scan()
        assert received == []

    async def test_tool_error_propagates_to_the_loop(self, monkeypatch, recorder):
        record, received = recorder
        stub_config(monkeypatch, **job_hunter_settings().__dict__)
        stub_tool_module(
            monkeypatch,
            "vera.brain.agents.job_hunter",
            "RunJobScanTool",
            exc=RuntimeError("scanner down"),
        )
        sys.modules["vera.brain.agents.job_hunter"]._today_application_count = lambda: 0
        with pytest.raises(RuntimeError, match="scanner down"):
            await make_scheduler(record)._run_job_scan()
        assert received == []


# ---------------------------------------------------------------------------
# _run_morning_plan / _run_digest
# ---------------------------------------------------------------------------


class TestRunMorningPlan:
    async def test_success_notifies_with_capped_lists(self, monkeypatch, recorder):
        record, received = recorder
        plan = {
            "events": [{"time": "09:00", "title": f"E{i}"} for i in range(7)],
            "pending_todos": [{"text": f"T{i}"} for i in range(6)],
            "active_goals": [{"title": f"G{i}"} for i in range(4)],
        }
        state = stub_tool_module(
            monkeypatch,
            "vera.brain.agents.planner",
            "MorningPlanTool",
            result={"status": "success", "plan": plan},
        )
        await make_scheduler(record)._run_morning_plan()
        assert state["calls"] == [{"date": "today"}]
        assert len(received) == 1
        note = received[0]
        assert note["type"] == "morning_plan"
        message = note["message"]
        # Counts report the full lists; the bullets are capped 5/5/3.
        assert "7 event(s)" in message
        assert "6 pending task(s)" in message
        assert "4 active goal(s)" in message
        assert message.count("•") == 5 + 5 + 3

    async def test_non_success_status_is_silent(self, monkeypatch, recorder):
        record, received = recorder
        stub_tool_module(
            monkeypatch,
            "vera.brain.agents.planner",
            "MorningPlanTool",
            result={"status": "error"},
        )
        await make_scheduler(record)._run_morning_plan()
        assert received == []


class TestRunDigest:
    async def test_success_notifies_with_counts(self, monkeypatch, recorder):
        record, received = recorder
        result = {"status": "success", "digest": {"items": [1, 2, 3], "sources_count": 2}}
        state = stub_tool_module(
            monkeypatch, "vera.brain.agents.digest", "GenerateDigestTool", result=result
        )
        await make_scheduler(record)._run_digest()
        assert state["calls"] == [{"date": "today"}]
        assert len(received) == 1
        note = received[0]
        assert note["type"] == "daily_digest"
        assert "3 items from 2 sources" in note["message"]

    async def test_non_success_status_is_silent(self, monkeypatch, recorder):
        record, received = recorder
        stub_tool_module(
            monkeypatch,
            "vera.brain.agents.digest",
            "GenerateDigestTool",
            result={"status": "error"},
        )
        await make_scheduler(record)._run_digest()
        assert received == []


# ---------------------------------------------------------------------------
# _run_ticket_scan (the scoping doc's "_run_daily_review" is this worker
# plus the daily-review loop tested separately below)
# ---------------------------------------------------------------------------


class TestRunTicketScan:
    def _stub_tickets(self, monkeypatch, result):
        return stub_tool_module(
            monkeypatch, "vera.brain.agents.jira_agent", "GetMyTicketsTool", result=result
        )

    async def test_new_tickets_notify_each_and_write_back(
        self, monkeypatch, recorder, data_dir
    ):
        record, received = recorder
        tickets = [
            {"key": "ABC-1", "summary": "First", "priority": "High", "type": "Bug"},
            {"key": "ABC-2", "summary": "Second", "priority": "Low", "type": "Task"},
        ]
        self._stub_tickets(monkeypatch, {"status": "success", "tickets": tickets})
        await make_scheduler(record)._run_ticket_scan()
        assert [n["type"] for n in received] == ["new_ticket", "new_ticket"]
        assert "ABC-1" in received[0]["message"]
        state = json.loads((data_dir / "jira_last_scan.json").read_text())
        assert sorted(state["known_tickets"]) == ["ABC-1", "ABC-2"]
        assert "last_scan" in state

    async def test_known_tickets_are_silent_but_state_still_writes(
        self, monkeypatch, recorder, data_dir
    ):
        record, received = recorder
        (data_dir / "jira_last_scan.json").write_text(
            json.dumps({"known_tickets": ["ABC-1"], "last_scan": "earlier"})
        )
        self._stub_tickets(
            monkeypatch,
            {"status": "success", "tickets": [{"key": "ABC-1", "summary": "Old"}]},
        )
        await make_scheduler(record)._run_ticket_scan()
        assert received == []
        state = json.loads((data_dir / "jira_last_scan.json").read_text())
        assert state["known_tickets"] == ["ABC-1"]

    async def test_non_success_status_returns_without_write_back(
        self, monkeypatch, recorder, data_dir
    ):
        record, received = recorder
        self._stub_tickets(monkeypatch, {"status": "error"})
        await make_scheduler(record)._run_ticket_scan()
        assert received == []
        assert not (data_dir / "jira_last_scan.json").exists()

    async def test_malformed_last_scan_counts_everything_as_new(
        self, monkeypatch, recorder, data_dir
    ):
        record, received = recorder
        (data_dir / "jira_last_scan.json").write_text("{not json")
        self._stub_tickets(
            monkeypatch,
            {"status": "success", "tickets": [{"key": "ABC-9", "summary": "Fresh"}]},
        )
        await make_scheduler(record)._run_ticket_scan()
        assert len(received) == 1
        assert received[0]["data"]["key"] == "ABC-9"


# ---------------------------------------------------------------------------
# _run_channel_monitor
# ---------------------------------------------------------------------------


class TestRunChannelMonitor:
    def _setup(self, monkeypatch, *, token="xoxb-test", channels=("C1",), mention_alert=True):
        settings = SimpleNamespace(
            channel_monitor=SimpleNamespace(
                enabled=True, channels=list(channels), mention_alert=mention_alert
            )
        )
        stub_config(monkeypatch, channel_monitor=settings.channel_monitor)
        return settings

    def _stub_messaging(self, monkeypatch, *, token, histories):
        async def fetch_channel_history(channel_id, oldest="0", limit=50):
            return histories.get(channel_id, [])

        install_module(
            monkeypatch, "vera.messaging", SLACK_BOT_TOKEN=token,
            fetch_channel_history=fetch_channel_history,
        )

    async def test_missing_token_returns_before_any_state(self, monkeypatch, recorder, data_dir):
        record, received = recorder
        self._setup(monkeypatch)
        self._stub_messaging(monkeypatch, token="", histories={})
        await make_scheduler(record)._run_channel_monitor()
        assert received == []
        assert not (data_dir / "channel_monitor.json").exists()

    async def test_no_channels_returns_before_any_state(self, monkeypatch, recorder, data_dir):
        record, received = recorder
        self._setup(monkeypatch, channels=())
        self._stub_messaging(monkeypatch, token="xoxb-test", histories={})
        await make_scheduler(record)._run_channel_monitor()
        assert received == []
        assert not (data_dir / "channel_monitor.json").exists()

    async def test_mention_notifies_and_state_advances(self, monkeypatch, recorder, data_dir):
        record, received = recorder
        self._setup(monkeypatch)
        messages = [
            {"ts": "100.1", "text": "hello"},
            {"ts": "100.2", "text": "ping <@U1>"},
        ]
        self._stub_messaging(monkeypatch, token="xoxb-test", histories={"C1": messages})
        await make_scheduler(record)._run_channel_monitor()
        assert len(received) == 1
        note = received[0]
        assert note["type"] == "mention_alert"
        assert note["data"] == {"channel": "C1", "mentions": 1, "total_new": 2}
        state = json.loads((data_dir / "channel_monitor.json").read_text())
        assert state == {"C1": "100.2"}

    async def test_activity_without_mention_notifies_neutral(
        self, monkeypatch, recorder, data_dir
    ):
        record, received = recorder
        self._setup(monkeypatch)
        self._stub_messaging(
            monkeypatch, token="xoxb-test",
            histories={"C1": [{"ts": "5", "text": "just chatter"}]},
        )
        await make_scheduler(record)._run_channel_monitor()
        assert len(received) == 1
        assert received[0]["type"] == "channel_activity"
        assert received[0]["mood"] == "neutral"

    async def test_timestamps_compare_as_strings_quirk(self, monkeypatch, recorder, data_dir):
        """last_ts "9" vs message ts "10": string comparison sorts
        "10" before "9", so the newer message is treated as seen."""
        record, received = recorder
        self._setup(monkeypatch)
        (data_dir / "channel_monitor.json").write_text(json.dumps({"C1": "9"}))
        self._stub_messaging(
            monkeypatch, token="xoxb-test",
            histories={"C1": [{"ts": "10", "text": "numerically newer"}]},
        )
        await make_scheduler(record)._run_channel_monitor()
        assert received == []
        state = json.loads((data_dir / "channel_monitor.json").read_text())
        assert state == {"C1": "9"}  # unchanged, but the file was rewritten


# ---------------------------------------------------------------------------
# _run_mood_check
# ---------------------------------------------------------------------------


class TestRunMoodCheck:
    def _settings(self, threshold: int = 3, lookback: int = 7) -> SimpleNamespace:
        return SimpleNamespace(
            emotional=SimpleNamespace(
                negative_mood_threshold=threshold, pattern_lookback_days=lookback
            )
        )

    def _stub_emotional(self, monkeypatch, *, recent, history=None, patterns=None):
        state = {"tracker_built": 0, "patterns_called": 0}

        class StubTracker:
            def __init__(self, path) -> None:
                state["tracker_built"] += 1

            def recent(self, hours: int):
                return recent

            def history(self, days: int):
                return history if history is not None else recent

        def detect_patterns(hist, lookback_days: int):
            state["patterns_called"] += 1
            return patterns if patterns is not None else []

        install_module(monkeypatch, "vera.emotional")
        install_module(monkeypatch, "vera.emotional.mood_tracker", MoodTracker=StubTracker)
        install_module(
            monkeypatch, "vera.emotional.pattern_detector", detect_patterns=detect_patterns
        )
        install_module(
            monkeypatch, "vera.emotional.sentiment", NEGATIVE_MOODS={"sad", "angry", "anxious"}
        )
        return state

    async def test_cooldown_short_circuits_before_the_tracker(self, monkeypatch, recorder):
        record, received = recorder
        state = self._stub_emotional(monkeypatch, recent=[])
        scheduler = make_scheduler(record)
        await scheduler._run_mood_check(
            self._settings(), datetime.now(), timedelta(hours=4)
        )
        assert state["tracker_built"] == 0
        assert received == []

    async def test_no_recent_entries_is_silent(self, monkeypatch, recorder):
        record, received = recorder
        self._stub_emotional(monkeypatch, recent=[])
        await make_scheduler(record)._run_mood_check(self._settings(), None, timedelta(hours=4))
        assert received == []

    async def test_negative_streak_notifies_checkin(self, monkeypatch, recorder):
        record, received = recorder
        recent = [SimpleNamespace(mood=m) for m in ("ok", "sad", "angry", "sad")]
        state = self._stub_emotional(monkeypatch, recent=recent)
        await make_scheduler(record)._run_mood_check(
            self._settings(threshold=3), None, timedelta(hours=4)
        )
        assert len(received) == 1
        note = received[0]
        assert note["type"] == "mood_checkin"
        assert note["data"] == {"streak": 3, "current_mood": "sad"}
        assert state["patterns_called"] == 0  # streak path returns first

    async def test_day_of_week_pattern_notifies_preemptive(self, monkeypatch, recorder):
        record, received = recorder
        today_name = datetime.now().strftime("%A")
        pattern = SimpleNamespace(pattern_type="day_of_week", data={"day": today_name})
        self._stub_emotional(
            monkeypatch,
            recent=[SimpleNamespace(mood="ok")],
            patterns=[pattern],
        )
        await make_scheduler(record)._run_mood_check(
            self._settings(threshold=3), None, timedelta(hours=4)
        )
        assert len(received) == 1
        assert received[0]["type"] == "mood_preemptive"
        assert received[0]["data"]["day"] == today_name

    async def test_below_threshold_without_pattern_is_silent(self, monkeypatch, recorder):
        record, received = recorder
        self._stub_emotional(
            monkeypatch,
            recent=[SimpleNamespace(mood="sad"), SimpleNamespace(mood="ok")],
            patterns=[],
        )
        await make_scheduler(record)._run_mood_check(
            self._settings(threshold=3), None, timedelta(hours=4)
        )
        assert received == []


# ---------------------------------------------------------------------------
# _send_daily_briefing (file-state worker; always notifies)
# ---------------------------------------------------------------------------


class TestSendDailyBriefing:
    async def test_no_state_files_still_notifies(self, recorder, data_dir):
        record, received = recorder
        await make_scheduler(record)._send_daily_briefing()
        assert len(received) == 1
        note = received[0]
        assert note["type"] == "daily_briefing"
        assert note["data"]["date"] == datetime.now().strftime("%Y-%m-%d")
        assert "Good morning" in note["message"]

    async def test_populated_files_are_summarised(self, recorder, data_dir):
        record, received = recorder
        today = datetime.now().strftime("%Y-%m-%d")
        (data_dir / "calendar.json").write_text(
            json.dumps(
                [
                    {"date": today, "time": "10:00", "title": "Standup"},
                    {"date": "1999-01-01", "time": "10:00", "title": "Ancient"},
                ]
            )
        )
        (data_dir / "todos.json").write_text(
            json.dumps([{"text": "Pending one", "done": False}, {"text": "Done", "done": True}])
        )
        (data_dir / "reminders.json").write_text(
            json.dumps([{"text": "Active", "dismissed": False}, {"text": "Old", "dismissed": True}])
        )
        await make_scheduler(record)._send_daily_briefing()
        message = received[0]["message"]
        assert "1 event(s) today" in message
        assert "Standup" in message
        assert "Ancient" not in message
        assert "1 todo(s) pending" in message
        assert "1 active reminder(s)" in message

    async def test_calendar_without_todays_events_says_free_day(self, recorder, data_dir):
        record, received = recorder
        (data_dir / "calendar.json").write_text(
            json.dumps([{"date": "1999-01-01", "time": "10:00", "title": "Ancient"}])
        )
        await make_scheduler(record)._send_daily_briefing()
        assert "No events today" in received[0]["message"]

    async def test_malformed_calendar_is_skipped_not_fatal(self, recorder, data_dir):
        record, received = recorder
        (data_dir / "calendar.json").write_text("{not json")
        await make_scheduler(record)._send_daily_briefing()
        assert len(received) == 1
        assert "event(s) today" not in received[0]["message"]


# ---------------------------------------------------------------------------
# Loop gates + the daily-review loop preservation test
# ---------------------------------------------------------------------------


class TestLoopGates:
    """The loops' settings gates return before any worker runs."""

    async def test_job_scan_loop_returns_when_disabled(self, monkeypatch):
        stub_config(monkeypatch, job_hunter=SimpleNamespace(enabled=False))
        await ProactiveScheduler()._job_scan_loop()

    async def test_morning_plan_loop_returns_when_disabled(self, monkeypatch):
        stub_config(monkeypatch, planner=SimpleNamespace(enabled=False))
        await ProactiveScheduler()._morning_plan_loop()

    async def test_digest_loop_returns_when_disabled(self, monkeypatch):
        stub_config(
            monkeypatch, digest=SimpleNamespace(enabled=True, auto_digest=False)
        )
        await ProactiveScheduler()._digest_loop()

    async def test_daily_review_loop_returns_when_disabled(self, monkeypatch):
        stub_config(monkeypatch, planner=SimpleNamespace(enabled=False))
        await ProactiveScheduler()._daily_review_reminder_loop()

    async def test_channel_monitor_loop_returns_when_disabled(self, monkeypatch):
        stub_config(monkeypatch, channel_monitor=SimpleNamespace(enabled=False))
        await ProactiveScheduler()._channel_monitor_loop()

    async def test_ticket_scan_loop_returns_when_disabled(self, monkeypatch):
        stub_config(monkeypatch, jira=SimpleNamespace(enabled=False))
        await ProactiveScheduler()._ticket_scan_loop()

    async def test_mood_check_loop_returns_when_empathy_disabled(self, monkeypatch):
        stub_config(
            monkeypatch,
            emotional=SimpleNamespace(enabled=True, proactive_empathy_enabled=False),
        )
        await ProactiveScheduler()._mood_check_loop()


class TestDailyReviewLoopCadence:
    """Preservation test for start()'s cadence override: with planner
    enabled, start() must schedule _daily_review_reminder_loop, and
    the real loop body must fire exactly one daily_review_reminder
    at the configured time (the loop is the worker for this surface —
    there is no _run_daily_review method)."""

    async def test_start_schedules_the_real_loop_and_it_fires_once(
        self, monkeypatch, recorder
    ):
        record, received = recorder
        fixed_now = datetime(2026, 10, 25, 21, 30)

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now

        monkeypatch.setattr(scheduler_module, "datetime", FixedDateTime)
        settings = SimpleNamespace(
            job_hunter=SimpleNamespace(enabled=False),
            planner=SimpleNamespace(enabled=True, daily_review_time="21:30", morning_plan_time="06:00"),
            wellness=SimpleNamespace(enabled=False),
            digest=SimpleNamespace(enabled=False),
            emotional=SimpleNamespace(enabled=False),
            jira=SimpleNamespace(enabled=False),
            channel_monitor=SimpleNamespace(enabled=False),
        )
        stub_config(monkeypatch, **settings.__dict__)

        scheduler = make_scheduler(record)

        # Replace every loop except the daily-review one with an inert
        # stub (the S1 pattern), so only the real loop body runs.
        async def inert_loop() -> None:
            await asyncio.sleep(3600)

        for name in [
            "_reminder_loop", "_calendar_loop", "_stock_alert_loop",
            "_daily_briefing_loop", "_scheduled_tasks_loop",
            "_content_publisher_loop", "_spending_alert_loop",
            "_morning_plan_loop",
        ]:
            monkeypatch.setattr(scheduler, name, inert_loop)

        real_sleep = asyncio.sleep
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)
            if seconds == 120:
                # The loop fired; stop it before its next pass.
                scheduler._running = False
            await real_sleep(0)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        try:
            await scheduler.start()
            await real_sleep(0.05)
        finally:
            await scheduler.stop()
            monkeypatch.setattr(asyncio, "sleep", real_sleep)

        review_notes = [n for n in received if n["type"] == "daily_review_reminder"]
        assert len(review_notes) == 1
        assert review_notes[0]["data"] == {"date": "2026-10-25"}
        assert 120 in sleeps  # the post-fire cooldown sleep was reached
