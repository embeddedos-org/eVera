"""check_availability must report a conflict with any event that overlaps the window.

``AvailabilityTool`` used to compare only each event's start time with the
window, as strings. An event that started before the window and was still
running in it (a 09:00 meeting of 120 minutes against 10:00-10:30) was not a
conflict, so the slot was reported free; and "9:00" sorted after "10:00".
"""

from __future__ import annotations

import json

import pytest

from vera.brain.agents.calendar_agent import AvailabilityTool, CreateEventTool

DAY = "2026-11-24"


@pytest.fixture
def calendar_dir(tmp_path, monkeypatch):
    # The calendar tools read and write data/calendar relative to the cwd.
    monkeypatch.chdir(tmp_path)
    return tmp_path / "data" / "calendar"


async def _add(time: str, minutes: int, title: str = "Meeting") -> None:
    result = await CreateEventTool().execute(title=title, date=DAY, time=time, duration_minutes=minutes)
    assert result["status"] == "success"


async def _check(start: str, end: str) -> dict:
    return await AvailabilityTool().execute(date=DAY, start_time=start, end_time=end)


async def test_event_running_into_the_window_is_a_conflict(calendar_dir):
    await _add("09:00", 120, "Design review")
    result = await _check("10:00", "10:30")
    assert result["status"] == "success"
    assert result["available"] is False
    assert [e["title"] for e in result["conflicts"]] == ["Design review"]


async def test_event_ending_when_the_window_starts_is_not_a_conflict(calendar_dir):
    await _add("09:00", 60, "Standup")
    await _add("10:30", 30, "1:1")
    result = await _check("10:00", "10:30")
    assert result["available"] is True
    assert result["conflicts"] == []


async def test_event_inside_the_window_is_a_conflict(calendar_dir):
    await _add("14:15", 15, "Call")
    result = await _check("14:00", "15:00")
    assert result["available"] is False
    assert [e["title"] for e in result["conflicts"]] == ["Call"]


async def test_single_digit_hours_compare_as_times(calendar_dir):
    await _add("9:30", 30, "Early call")
    result = await _check("10:00", "11:00")
    assert result["available"] is True

    result = await _check("9:00", "10:00")
    assert result["available"] is False
    assert [e["title"] for e in result["conflicts"]] == ["Early call"]

    await _add("15:00:00", 30, "Seconds given")
    assert (await _check("15:15", "16:00"))["available"] is False


async def test_event_without_a_duration_uses_the_60_minute_default(calendar_dir):
    calendar_dir.mkdir(parents=True)
    (calendar_dir / f"{DAY}.json").write_text(json.dumps([{"title": "Lunch", "time": "12:00"}]))
    assert (await _check("12:30", "13:00"))["available"] is False
    assert (await _check("13:00", "14:00"))["available"] is True


async def test_whole_day_default_window_includes_late_events(calendar_dir):
    await _add("23:59", 1, "Backup job")
    result = await AvailabilityTool().execute(date=DAY)
    assert result["available"] is False
    result = await _check("23:00", "23:59")
    assert result["available"] is False


async def test_free_day_and_bad_times(calendar_dir):
    assert (await _check("09:00", "17:00"))["available"] is True
    await _add("09:00", 30)
    result = await _check("nine", "17:00")
    assert result["status"] == "error"


async def test_point_window_still_finds_a_meeting_at_that_time(calendar_dir):
    await _add("10:00", 30, "Sync")
    result = await _check("10:00", "10:00")
    assert result["available"] is False
    assert [e["title"] for e in result["conflicts"]] == ["Sync"]
    assert (await _check("10:30", "10:30"))["available"] is True


async def test_window_across_midnight_is_an_error(calendar_dir):
    await _add("23:00", 60, "Late deploy")
    result = await _check("22:00", "01:00")
    assert result["status"] == "error"


async def test_end_time_24_00_means_end_of_day(calendar_dir):
    await _add("23:30", 15, "Nightly")
    result = await _check("23:00", "24:00")
    assert result["status"] == "success"
    assert result["available"] is False
