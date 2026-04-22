"""Semantic memory — persistent key-value store for user facts and preferences."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SemanticMemory:
    """JSON-backed store for user facts, preferences, and knowledge."""

    def __init__(self, store_path: Path | None = None) -> None:
        self._store_path = store_path
        self._facts: dict[str, str] = {}
        if store_path and store_path.exists():
            self.load()

    def remember(self, key: str, value: str) -> None:
        self._facts[key.lower().strip()] = value
        logger.debug("Remembered fact: %s = %s", key, value[:50])
        self._auto_save()

    def recall(self, key: str) -> str | None:
        return self._facts.get(key.lower().strip())

    def search(self, query: str) -> dict[str, str]:
        """Find facts whose key or value contains the query."""
        query_lower = query.lower()
        return {k: v for k, v in self._facts.items() if query_lower in k or query_lower in v.lower()}

    def get_all(self) -> dict[str, str]:
        return dict(self._facts)

    def forget(self, key: str) -> bool:
        key = key.lower().strip()
        if key in self._facts:
            del self._facts[key]
            self._auto_save()
            return True
        return False

    def save(self, path: Path | None = None) -> None:
        path = path or self._store_path
        if not path:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self._facts, f, indent=2)
        logger.debug("Saved %d semantic facts", len(self._facts))

    def load(self, path: Path | None = None) -> None:
        path = path or self._store_path
        if not path or not path.exists():
            return
        with open(path) as f:
            self._facts = json.load(f)
        logger.info("Loaded %d semantic facts from %s", len(self._facts), path)

    def _auto_save(self) -> None:
        if self._store_path:
            self.save()

    @property
    def count(self) -> int:
        return len(self._facts)
