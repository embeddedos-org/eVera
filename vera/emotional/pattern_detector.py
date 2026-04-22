"""Mood pattern detection — analyzes mood history for recurring patterns."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from vera.emotional.mood_tracker import MoodEntry
from vera.emotional.sentiment import NEGATIVE_MOODS

logger = logging.getLogger(__name__)


@dataclass
class MoodPattern:
    """A detected pattern in mood history."""

    pattern_type: str
    description: str
    confidence: float
    data: dict = field(default_factory=dict)


def detect_patterns(
    entries: list[MoodEntry],
    lookback_days: int = 14,
) -> list[MoodPattern]:
    """Analyze mood entries for recurring patterns.

    @param entries: List of MoodEntry objects to analyze.
    @param lookback_days: How many days of history to consider.
    @return List of detected MoodPattern objects.
    """
    if not entries:
        return []

    cutoff = datetime.now() - timedelta(days=lookback_days)
    recent = [e for e in entries if datetime.fromisoformat(e.timestamp) >= cutoff]

    if len(recent) < 3:
        return []

    patterns: list[MoodPattern] = []

    dow_pattern = _detect_day_of_week_pattern(recent)
    if dow_pattern:
        patterns.append(dow_pattern)

    tod_pattern = _detect_time_of_day_pattern(recent)
    if tod_pattern:
        patterns.append(tod_pattern)

    trend_pattern = _detect_trend(recent)
    if trend_pattern:
        patterns.append(trend_pattern)

    trigger_patterns = _detect_recurring_triggers(recent)
    patterns.extend(trigger_patterns)

    streak_pattern = _detect_negative_streak(recent)
    if streak_pattern:
        patterns.append(streak_pattern)

    return patterns


def _detect_day_of_week_pattern(entries: list[MoodEntry]) -> MoodPattern | None:
    """Flag days with >60% negative moods."""
    day_entries: dict[str, list[str]] = {}
    for e in entries:
        day = datetime.fromisoformat(e.timestamp).strftime("%A")
        day_entries.setdefault(day, []).append(e.mood)

    worst_day = None
    worst_ratio = 0.0

    for day, moods in day_entries.items():
        if len(moods) < 2:
            continue
        neg_count = sum(1 for m in moods if m in NEGATIVE_MOODS)
        ratio = neg_count / len(moods)
        if ratio > 0.6 and ratio > worst_ratio:
            worst_day = day
            worst_ratio = ratio

    if worst_day:
        return MoodPattern(
            pattern_type="day_of_week",
            description=f"{worst_day}s tend to be tough — {worst_ratio:.0%} negative mood ratio",
            confidence=min(0.9, worst_ratio),
            data={"day": worst_day, "negative_ratio": round(worst_ratio, 2)},
        )
    return None


def _detect_time_of_day_pattern(entries: list[MoodEntry]) -> MoodPattern | None:
    """Bucket into morning/afternoon/evening/night, flag high negative ratios."""
    buckets: dict[str, list[str]] = {"morning": [], "afternoon": [], "evening": [], "night": []}

    for e in entries:
        hour = datetime.fromisoformat(e.timestamp).hour
        if 6 <= hour < 12:
            bucket = "morning"
        elif 12 <= hour < 17:
            bucket = "afternoon"
        elif 17 <= hour < 21:
            bucket = "evening"
        else:
            bucket = "night"
        buckets[bucket].append(e.mood)

    worst_bucket = None
    worst_ratio = 0.0

    for bucket, moods in buckets.items():
        if len(moods) < 2:
            continue
        neg_count = sum(1 for m in moods if m in NEGATIVE_MOODS)
        ratio = neg_count / len(moods)
        if ratio > 0.6 and ratio > worst_ratio:
            worst_bucket = bucket
            worst_ratio = ratio

    if worst_bucket:
        return MoodPattern(
            pattern_type="time_of_day",
            description=f"{worst_bucket.capitalize()}s are often rough — {worst_ratio:.0%} negative mood ratio",
            confidence=min(0.9, worst_ratio),
            data={"period": worst_bucket, "negative_ratio": round(worst_ratio, 2)},
        )
    return None


def _detect_trend(entries: list[MoodEntry]) -> MoodPattern | None:
    """Compare last 3 days vs prior period sentiment."""
    now = datetime.now()
    three_days_ago = now - timedelta(days=3)

    recent = [e for e in entries if datetime.fromisoformat(e.timestamp) >= three_days_ago]
    older = [e for e in entries if datetime.fromisoformat(e.timestamp) < three_days_ago]

    if len(recent) < 2 or len(older) < 2:
        return None

    def _neg_ratio(ents: list[MoodEntry]) -> float:
        neg = sum(1 for e in ents if e.mood in NEGATIVE_MOODS)
        return neg / len(ents)

    recent_ratio = _neg_ratio(recent)
    older_ratio = _neg_ratio(older)
    diff = recent_ratio - older_ratio

    if abs(diff) < 0.15:
        direction = "stable"
    elif diff > 0:
        direction = "declining"
    else:
        direction = "improving"

    if direction == "stable":
        return None

    return MoodPattern(
        pattern_type="trend",
        description=f"Mood trend is {direction} (recent: {recent_ratio:.0%} vs prior: {older_ratio:.0%} negative)",
        confidence=min(0.8, abs(diff) + 0.3),
        data={
            "direction": direction,
            "recent_negative_ratio": round(recent_ratio, 2),
            "prior_negative_ratio": round(older_ratio, 2),
        },
    )


def _detect_recurring_triggers(entries: list[MoodEntry]) -> list[MoodPattern]:
    """Surface trigger phrases appearing 3+ times."""
    triggers = [e.trigger for e in entries if e.trigger]
    if not triggers:
        return []

    counts = Counter(t.lower().strip() for t in triggers)
    patterns = []

    for trigger, count in counts.most_common(5):
        if count >= 3:
            patterns.append(
                MoodPattern(
                    pattern_type="recurring_trigger",
                    description=f'"{trigger}" has come up {count} times',
                    confidence=min(0.85, 0.5 + count * 0.1),
                    data={"trigger": trigger, "count": count},
                )
            )

    return patterns


def _detect_negative_streak(entries: list[MoodEntry]) -> MoodPattern | None:
    """Count current unbroken streak of negative moods (most recent first)."""
    if not entries:
        return None

    sorted_entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)
    streak = 0

    for e in sorted_entries:
        if e.mood in NEGATIVE_MOODS:
            streak += 1
        else:
            break

    if streak >= 2:
        return MoodPattern(
            pattern_type="negative_streak",
            description=f"Current streak of {streak} consecutive negative moods",
            confidence=min(0.9, 0.4 + streak * 0.15),
            data={"streak_length": streak},
        )
    return None
