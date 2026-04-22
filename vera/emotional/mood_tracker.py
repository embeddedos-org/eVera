"""Mood history tracker — persists mood entries to JSON for pattern analysis."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MoodEntry:
    """A single mood observation."""
    timestamp: str
    mood: str
    confidence: float
    trigger: str | None
    transcript_snippet: str


class MoodTracker:
    """Tracks and persists user mood over time."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: list[MoodEntry] = []
        self._load()

    def record(
        self,
        mood: str,
        confidence: float,
        trigger: str | None,
        transcript: str,
    ) -> None:
        """Record a new mood observation and auto-save."""
        entry = MoodEntry(
            timestamp=datetime.now().isoformat(),
            mood=mood,
            confidence=confidence,
            trigger=trigger,
            transcript_snippet=transcript[:100],
        )
        self._entries.append(entry)
        self._save()
        logger.debug("Recorded mood: %s (%.2f)", mood, confidence)

    def recent(self, hours: int = 24) -> list[MoodEntry]:
        """Get mood entries within the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            e for e in self._entries
            if datetime.fromisoformat(e.timestamp) >= cutoff
        ]

    def history(self, days: int = 14) -> list[MoodEntry]:
        """Get mood entries within the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        return [
            e for e in self._entries
            if datetime.fromisoformat(e.timestamp) >= cutoff
        ]

    def _load(self) -> None:
        """Load mood history from disk."""
        if not self._path.exists():
            self._entries = []
            return
        try:
            data = json.loads(self._path.read_text())
            self._entries = [MoodEntry(**e) for e in data]
            logger.info("Loaded %d mood entries from %s", len(self._entries), self._path)
        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to load mood history: %s", e)
            self._entries = []

    def _save(self) -> None:
        """Persist mood history to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps([asdict(e) for e in self._entries], indent=2, default=str)
            )
        except OSError as e:
            logger.warning("Failed to save mood history: %s", e)
