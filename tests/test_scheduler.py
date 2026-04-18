"""Tests for proactive scheduler — reminders, calendar, stock alerts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def scheduler(tmp_path):
    import voca.scheduler as sched_mod
    sched_mod.DATA_DIR = tmp_path
    from voca.scheduler import ProactiveScheduler
    s = ProactiveScheduler()
    return s, tmp_path


class TestScheduler:
    @pytest.mark.asyncio
    async def test_fires_due_reminder(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        # Create a reminder that's already due
        reminders = [{
            "id": "1",
            "text": "Test reminder",
            "trigger_at": (datetime.now() - timedelta(minutes=1)).isoformat(),
            "dismissed": False,
        }]
        (data_dir / "reminders.json").write_text(json.dumps(reminders))

        await sched._check_reminders()

        assert len(notifications) == 1
        assert "Test reminder" in notifications[0]["message"]

    @pytest.mark.asyncio
    async def test_skips_dismissed_reminder(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        reminders = [{
            "id": "1",
            "text": "Old reminder",
            "trigger_at": (datetime.now() - timedelta(hours=1)).isoformat(),
            "dismissed": True,
        }]
        (data_dir / "reminders.json").write_text(json.dumps(reminders))

        await sched._check_reminders()
        assert len(notifications) == 0

    @pytest.mark.asyncio
    async def test_skips_future_reminder(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        reminders = [{
            "id": "1",
            "text": "Future reminder",
            "trigger_at": (datetime.now() + timedelta(hours=1)).isoformat(),
            "dismissed": False,
        }]
        (data_dir / "reminders.json").write_text(json.dumps(reminders))

        await sched._check_reminders()
        assert len(notifications) == 0

    @pytest.mark.asyncio
    async def test_no_reminders_file(self, scheduler):
        sched, _ = scheduler
        await sched._check_reminders()  # Should not crash

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, scheduler):
        sched, data_dir = scheduler
        n1, n2 = [], []
        sched.add_notification_handler(lambda n: n1.append(n))
        sched.add_notification_handler(lambda n: n2.append(n))

        reminders = [{
            "id": "1", "text": "Multi-handler test",
            "trigger_at": (datetime.now() - timedelta(seconds=10)).isoformat(),
            "dismissed": False,
        }]
        (data_dir / "reminders.json").write_text(json.dumps(reminders))

        await sched._check_reminders()
        assert len(n1) == 1
        assert len(n2) == 1
