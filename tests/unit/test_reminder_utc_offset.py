"""Reminders given as an ISO time with a UTC offset.

``create_reminder`` accepts an ISO datetime. One with an offset
("...Z" or "+05:30") was stored timezone-aware, and comparing it with
the naive ``datetime.now()`` raised TypeError: first in the tool itself,
then on every scheduler pass, so no reminder fired at all.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from vera import scheduler as scheduler_module
from vera.brain.agents import life_manager
from vera.brain.agents.life_manager import CreateReminderTool
from vera.scheduler import ProactiveScheduler


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(life_manager, "DATA_DIR", tmp_path)
    monkeypatch.setattr(scheduler_module, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def scheduler():
    received: list[dict] = []
    sched = ProactiveScheduler()

    async def record(notification: dict) -> None:
        received.append(notification)

    sched.add_notification_handler(record)
    return sched, received


def _local_naive(aware: datetime) -> datetime:
    return aware.astimezone().replace(tzinfo=None)


@pytest.mark.parametrize("suffix", ["Z", "+00:00", "+05:30", "-08:00"])
async def test_create_reminder_accepts_an_offset(data_dir, suffix):
    when = datetime(2030, 1, 2, 9, 30)
    result = await CreateReminderTool().execute(text="call", when=when.isoformat() + suffix)

    assert result["status"] == "success"
    stored = datetime.fromisoformat(result["reminder"]["trigger_at"])
    assert stored.tzinfo is None
    assert stored == _local_naive(datetime.fromisoformat(when.isoformat() + suffix))


async def test_offset_reminder_fires(data_dir, scheduler):
    sched, received = scheduler
    due = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    await CreateReminderTool().execute(text="stretch", when=due)

    await sched._check_reminders()

    assert [n["data"]["text"] for n in received] == ["stretch"]


async def test_one_stored_offset_reminder_does_not_block_the_others(data_dir, scheduler):
    sched, received = scheduler
    reminders = [
        {"text": "aware", "trigger_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
        {"text": "naive", "trigger_at": (datetime.now() - timedelta(minutes=1)).isoformat()},
        {"text": "later", "trigger_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
    ]
    (data_dir / "reminders.json").write_text(json.dumps(reminders))

    await sched._check_reminders()

    assert sorted(n["data"]["text"] for n in received) == ["aware", "naive"]
    on_disk = json.loads((data_dir / "reminders.json").read_text())
    assert [r.get("dismissed", False) for r in on_disk] == [True, True, False]
