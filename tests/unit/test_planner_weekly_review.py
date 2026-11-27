"""weekly_review must collect the daily reviews of the requested week, not the current week."""

from __future__ import annotations

import json

import pytest

from vera.brain.agents import planner
from vera.brain.agents.planner import WeeklyReviewTool


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(planner, "DATA_DIR", tmp_path)
    monkeypatch.setattr(planner, "REVIEWS_DIR", tmp_path / "reviews")
    daily = tmp_path / "reviews" / "daily"
    daily.mkdir(parents=True)
    weekly = tmp_path / "reviews" / "weekly"
    weekly.mkdir(parents=True)
    # Provide a goals.json so execute() doesn't error.
    (tmp_path / "goals.json").write_text("[]", encoding="utf-8")
    return daily


def _write_day(daily_dir, date_str, content=None):
    data = content or {"date": date_str, "summary": "test"}
    (daily_dir / f"{date_str}.json").write_text(json.dumps(data), encoding="utf-8")


async def test_past_week_collects_its_own_days(data_dir):
    """Requesting '2026-W01' should collect Mon 29 Dec 2025 .. Sun 4 Jan 2026,
    not the current week's days."""
    # ISO week 2026-W01 runs Mon 2025-12-29 to Sun 2026-01-04.
    target_days = [
        "2025-12-29", "2025-12-30", "2025-12-31",
        "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04",
    ]
    # Also write a day from a different week to make sure it's excluded.
    for d in target_days:
        _write_day(data_dir, d)
    _write_day(data_dir, "2026-01-12")  # week 3

    result = await WeeklyReviewTool().execute(week="2026-W01")

    assert result["status"] == "success"
    assert result["review"]["week"] == "2026-W01"
    # Must find exactly the 7 target-week days (not 8, not 0).
    assert result["review"]["daily_reviews_found"] == 7
    dates_found = [r["date"] for r in result["review"]["daily_reviews"]]
    assert sorted(dates_found) == sorted(target_days)
