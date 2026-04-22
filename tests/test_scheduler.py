"""Tests for proactive scheduler — reminders, calendar, stock alerts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def scheduler(tmp_path):
    import vera.scheduler as sched_mod

    sched_mod.DATA_DIR = tmp_path
    from vera.scheduler import ProactiveScheduler

    s = ProactiveScheduler()
    return s, tmp_path


class TestScheduler:
    @pytest.mark.asyncio
    async def test_fires_due_reminder(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        # Create a reminder that's already due
        reminders = [
            {
                "id": "1",
                "text": "Test reminder",
                "trigger_at": (datetime.now() - timedelta(minutes=1)).isoformat(),
                "dismissed": False,
            }
        ]
        (data_dir / "reminders.json").write_text(json.dumps(reminders))

        await sched._check_reminders()

        assert len(notifications) == 1
        assert "Test reminder" in notifications[0]["message"]

    @pytest.mark.asyncio
    async def test_skips_dismissed_reminder(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        reminders = [
            {
                "id": "1",
                "text": "Old reminder",
                "trigger_at": (datetime.now() - timedelta(hours=1)).isoformat(),
                "dismissed": True,
            }
        ]
        (data_dir / "reminders.json").write_text(json.dumps(reminders))

        await sched._check_reminders()
        assert len(notifications) == 0

    @pytest.mark.asyncio
    async def test_skips_future_reminder(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        reminders = [
            {
                "id": "1",
                "text": "Future reminder",
                "trigger_at": (datetime.now() + timedelta(hours=1)).isoformat(),
                "dismissed": False,
            }
        ]
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

        reminders = [
            {
                "id": "1",
                "text": "Multi-handler test",
                "trigger_at": (datetime.now() - timedelta(seconds=10)).isoformat(),
                "dismissed": False,
            }
        ]
        (data_dir / "reminders.json").write_text(json.dumps(reminders))

        await sched._check_reminders()
        assert len(n1) == 1
        assert len(n2) == 1


class TestScheduledTasks:
    """Tests for _check_scheduled_tasks() — daily, weekly, interval tasks."""

    @pytest.mark.asyncio
    async def test_daily_task_fires_at_matching_time(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        now = datetime.now()
        tasks = [
            {
                "name": "Daily standup",
                "description": "Join standup call",
                "enabled": True,
                "schedule": {
                    "type": "daily",
                    "time": f"{now.hour:02d}:{now.minute:02d}",
                },
                "last_run": "",
            }
        ]
        (data_dir / "scheduled_tasks.json").write_text(json.dumps(tasks))

        await sched._check_scheduled_tasks()
        assert len(notifications) == 1
        assert "Daily standup" in notifications[0]["message"]

    @pytest.mark.asyncio
    async def test_daily_task_already_run_today(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        now = datetime.now()
        tasks = [
            {
                "name": "Already done",
                "enabled": True,
                "schedule": {
                    "type": "daily",
                    "time": f"{now.hour:02d}:{now.minute:02d}",
                },
                "last_run": now.strftime("%Y-%m-%d"),
            }
        ]
        (data_dir / "scheduled_tasks.json").write_text(json.dumps(tasks))

        await sched._check_scheduled_tasks()
        assert len(notifications) == 0

    @pytest.mark.asyncio
    async def test_weekly_task_correct_day_and_time(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        now = datetime.now()
        today_name = now.strftime("%A").lower()
        tasks = [
            {
                "name": "Weekly review",
                "enabled": True,
                "schedule": {
                    "type": "weekly",
                    "day": today_name,
                    "time": f"{now.hour:02d}:{now.minute:02d}",
                },
                "last_run": "",
            }
        ]
        (data_dir / "scheduled_tasks.json").write_text(json.dumps(tasks))

        await sched._check_scheduled_tasks()
        assert len(notifications) == 1
        assert "Weekly review" in notifications[0]["message"]

    @pytest.mark.asyncio
    async def test_interval_task_past_interval(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        tasks = [
            {
                "name": "Interval check",
                "enabled": True,
                "schedule": {
                    "type": "interval",
                    "minutes": 5,
                },
                "last_run_ts": 0,  # Last run at epoch → definitely past interval
            }
        ]
        (data_dir / "scheduled_tasks.json").write_text(json.dumps(tasks))

        await sched._check_scheduled_tasks()
        assert len(notifications) == 1
        assert "Interval check" in notifications[0]["message"]

    @pytest.mark.asyncio
    async def test_disabled_task_not_fired(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        now = datetime.now()
        tasks = [
            {
                "name": "Disabled task",
                "enabled": False,
                "schedule": {
                    "type": "daily",
                    "time": f"{now.hour:02d}:{now.minute:02d}",
                },
                "last_run": "",
            }
        ]
        (data_dir / "scheduled_tasks.json").write_text(json.dumps(tasks))

        await sched._check_scheduled_tasks()
        assert len(notifications) == 0

    @pytest.mark.asyncio
    async def test_no_tasks_file(self, scheduler):
        sched, _ = scheduler
        await sched._check_scheduled_tasks()  # Should not crash


class TestScheduledPosts:
    """Tests for _check_scheduled_posts() — content publisher loop."""

    @pytest.mark.asyncio
    async def test_due_post_becomes_ready_to_publish(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        past_time = (datetime.now() - timedelta(minutes=5)).isoformat()
        posts = [
            {
                "platform": "twitter",
                "content": "Hello Twitter!",
                "schedule_at": past_time,
                "status": "scheduled",
            }
        ]
        (data_dir / "scheduled_posts.json").write_text(json.dumps(posts))

        await sched._check_scheduled_posts()

        assert len(notifications) == 1
        assert "twitter" in notifications[0]["message"].lower()

        # Verify status updated on disk
        updated = json.loads((data_dir / "scheduled_posts.json").read_text())
        assert updated[0]["status"] == "ready_to_publish"

    @pytest.mark.asyncio
    async def test_non_scheduled_post_skipped(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        posts = [
            {
                "platform": "twitter",
                "content": "Already published",
                "schedule_at": (datetime.now() - timedelta(hours=1)).isoformat(),
                "status": "published",
            }
        ]
        (data_dir / "scheduled_posts.json").write_text(json.dumps(posts))

        await sched._check_scheduled_posts()
        assert len(notifications) == 0

    @pytest.mark.asyncio
    async def test_no_posts_file(self, scheduler):
        sched, _ = scheduler
        await sched._check_scheduled_posts()  # Should not crash


class TestSpendingAlerts:
    """Tests for _check_spending_alerts() — budget monitoring."""

    @pytest.mark.asyncio
    async def test_budget_exceeded_fires_alert(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        now = datetime.now()
        finance = {
            "budgets": {"food": 100},
            "transactions": [
                {"amount": -60, "category": "food", "date": now.isoformat()},
                {"amount": -50, "category": "food", "date": now.isoformat()},
            ],
        }
        (data_dir / "finance.json").write_text(json.dumps(finance))

        await sched._check_spending_alerts()
        assert len(notifications) == 1
        assert notifications[0]["type"] == "budget_alert"
        assert "🚨" in notifications[0]["message"]

    @pytest.mark.asyncio
    async def test_budget_warning_at_80_percent(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        now = datetime.now()
        finance = {
            "budgets": {"food": 100},
            "transactions": [
                {"amount": -85, "category": "food", "date": now.isoformat()},
            ],
        }
        (data_dir / "finance.json").write_text(json.dumps(finance))

        await sched._check_spending_alerts()
        assert len(notifications) == 1
        assert notifications[0]["type"] == "budget_warning"
        assert "⚠️" in notifications[0]["message"]

    @pytest.mark.asyncio
    async def test_under_budget_no_notification(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        now = datetime.now()
        finance = {
            "budgets": {"food": 100},
            "transactions": [
                {"amount": -30, "category": "food", "date": now.isoformat()},
            ],
        }
        (data_dir / "finance.json").write_text(json.dumps(finance))

        await sched._check_spending_alerts()
        assert len(notifications) == 0

    @pytest.mark.asyncio
    async def test_no_budgets_no_notification(self, scheduler):
        sched, data_dir = scheduler
        notifications = []
        sched.add_notification_handler(lambda n: notifications.append(n))

        finance = {"transactions": []}
        (data_dir / "finance.json").write_text(json.dumps(finance))

        await sched._check_spending_alerts()
        assert len(notifications) == 0

    @pytest.mark.asyncio
    async def test_no_finance_file_no_crash(self, scheduler):
        sched, _ = scheduler
        await sched._check_spending_alerts()  # Should not crash


class TestSchedulerStartStop:
    """Tests for start()/stop() lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self, scheduler):
        sched, _ = scheduler
        assert sched._running is False
        await sched.start()
        assert sched._running is True
        assert len(sched._tasks) == 15
        await sched.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self, scheduler):
        sched, _ = scheduler
        await sched.start()
        assert sched._running is True
        await sched.stop()
        assert sched._running is False

    def test_remove_notification_handler(self, scheduler):
        sched, _ = scheduler

        def handler(n):
            return None

        sched.add_notification_handler(handler)
        assert len(sched._notification_handlers) == 1
        sched.remove_notification_handler(handler)
        assert len(sched._notification_handlers) == 0

    def test_remove_nonexistent_handler(self, scheduler):
        sched, _ = scheduler
        sched.remove_notification_handler(lambda n: None)  # Should not crash
