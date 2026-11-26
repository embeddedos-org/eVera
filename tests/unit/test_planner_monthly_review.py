"""monthly_review must only collect the weekly reviews of the month it reviews.

``MonthlyReviewTool`` globbed ``<year>-W*.json``, so the review of one month
picked up every weekly review saved that year.
"""

from __future__ import annotations

import json

import pytest

from vera.brain.agents import planner
from vera.brain.agents.planner import MonthlyReviewTool


@pytest.fixture
def reviews_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(planner, "DATA_DIR", tmp_path)
    monkeypatch.setattr(planner, "REVIEWS_DIR", tmp_path / "reviews")
    weekly = tmp_path / "reviews" / "weekly"
    weekly.mkdir(parents=True)
    return weekly


def _write_week(weekly_dir, week_id):
    (weekly_dir / f"{week_id}.json").write_text(json.dumps({"week": week_id}), encoding="utf-8")


def _weeks(result):
    return [r["week"] for r in result["review"]["weekly_reviews"]]


async def test_only_weeks_of_the_month_are_collected(reviews_dir):
    # 2026-11-01 is a Sunday (ISO week 44); 2026-11-30 is a Monday (week 49).
    for week_id in ["2026-W02", "2026-W43", "2026-W44", "2026-W45", "2026-W48", "2026-W49", "2026-W50"]:
        _write_week(reviews_dir, week_id)

    result = await MonthlyReviewTool().execute(month="2026-11")

    assert result["status"] == "success"
    assert _weeks(result) == ["2026-W44", "2026-W45", "2026-W48", "2026-W49"]
    assert result["review"]["weekly_reviews_found"] == 4


async def test_week_spanning_two_months_counts_in_both(reviews_dir):
    # ISO week 44 of 2026 runs from Mon 26 Oct to Sun 1 Nov.
    _write_week(reviews_dir, "2026-W44")

    october = await MonthlyReviewTool().execute(month="2026-10")
    november = await MonthlyReviewTool().execute(month="2026-11")

    assert _weeks(october) == ["2026-W44"]
    assert _weeks(november) == ["2026-W44"]


async def test_january_uses_the_names_weekly_review_writes(reviews_dir):
    # WeeklyReviewTool names a week with "%Y-W%V": on Fri 1 Jan 2027 that is
    # "2027-W53"; the next week is "2027-W01". "2026-W53" is the name for
    # 28-31 Dec 2026. Sun 31 Jan 2027 is in week 4; Mon 1 Feb starts week 5.
    for week_id in ["2026-W53", "2027-W53", "2027-W01", "2027-W04", "2027-W05", "2027-W10"]:
        _write_week(reviews_dir, week_id)

    result = await MonthlyReviewTool().execute(month="2027-01")

    assert _weeks(result) == ["2027-W53", "2027-W01", "2027-W04"]


async def test_month_without_weekly_reviews(reviews_dir):
    _write_week(reviews_dir, "2026-W02")

    result = await MonthlyReviewTool().execute(month="2026-07")

    assert result["status"] == "success"
    assert result["review"]["weekly_reviews_found"] == 0


@pytest.mark.parametrize("month", ["2026-13", "November", "2026-11-05", ""])
async def test_invalid_month_is_an_error(reviews_dir, month):
    result = await MonthlyReviewTool().execute(month=month)

    assert result["status"] == "error"
    assert not (reviews_dir.parent / "monthly" / f"{month}.json").exists()


async def test_last_representable_month(reviews_dir):
    # 31 Dec 9999 is the last date datetime can hold; the month must not
    # step past it.
    _write_week(reviews_dir, "9999-W52")

    result = await MonthlyReviewTool().execute(month="9999-12")

    assert result["status"] == "success"
    assert _weeks(result) == ["9999-W52"]


async def test_one_digit_month_is_saved_as_two_digits(reviews_dir):
    _write_week(reviews_dir, "2026-W02")

    result = await MonthlyReviewTool().execute(month="2026-1")

    assert result["status"] == "success"
    assert result["review"]["month"] == "2026-01"
    assert _weeks(result) == ["2026-W02"]
    monthly = reviews_dir.parent / "monthly"
    assert (monthly / "2026-01.json").exists()
    assert not (monthly / "2026-1.json").exists()
