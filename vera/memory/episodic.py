"""Episodic memory — FAISS-backed vector store for past events."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EpisodicEvent:
    """A stored episodic memory event."""

    text: str
    timestamp: float = field(default_factory=time.time)
    agent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0  # similarity score (populated on recall)


class EpisodicMemory:
    """Long-term episodic memory using sentence-transformers + FAISS."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", index_path: Path | None = None) -> None:
        self._model_name = model_name
        self._index_path = index_path
        self._embedder = None
        self._index = None
        self._events: list[EpisodicEvent] = []
        self._dimension: int = 384  # default for all-MiniLM-L6-v2

    def _ensure_loaded(self) -> None:
        """Lazy-load the embedding model and FAISS index."""
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._embedder = SentenceTransformer(self._model_name)
                self._dimension = self._embedder.get_sentence_embedding_dimension()
            except ImportError:
                logger.warning("sentence-transformers not installed; episodic memory disabled")
                return

        if self._index is None:
            try:
                import faiss

                self._index = faiss.IndexFlatL2(self._dimension)
            except ImportError:
                logger.warning("faiss-cpu not installed; episodic memory disabled")
                return

            if self._index_path and self._index_path.exists():
                self.load_from_disk(self._index_path)

    def _embed(self, texts: list[str]) -> np.ndarray:
        self._ensure_loaded()
        if self._embedder is None:
            return np.zeros((len(texts), self._dimension), dtype=np.float32)
        return self._embedder.encode(texts, convert_to_numpy=True).astype(np.float32)

    MAX_EVENTS = 10000

    def store(self, text: str, agent: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        self._ensure_loaded()
        event = EpisodicEvent(text=text, agent=agent, metadata=metadata or {})
        self._events.append(event)

        # Prune old events to prevent unbounded growth
        if len(self._events) > self.MAX_EVENTS:
            self._events = self._events[-self.MAX_EVENTS :]
            # Rebuild FAISS index
            if self._index is not None:
                self._rebuild_index()
            return

        if self._index is not None:
            embedding = self._embed([text])
            self._index.add(embedding)
            logger.debug("Stored episodic event: %s (total: %d)", text[:50], len(self._events))

    def _rebuild_index(self) -> None:
        """Rebuild FAISS index from current events."""
        try:
            import faiss

            self._index = faiss.IndexFlatL2(self._dimension)
            if self._events:
                texts = [e.text for e in self._events]
                embeddings = self._embed(texts)
                self._index.add(embeddings)
            logger.info("Rebuilt FAISS index with %d events", len(self._events))
        except Exception as e:
            logger.warning("Failed to rebuild FAISS index: %s", e)

    def recall(self, query: str, k: int = 5) -> list[EpisodicEvent]:
        self._ensure_loaded()
        if self._index is None or self._index.ntotal == 0:
            return []

        query_vec = self._embed([query])
        k = min(k, self._index.ntotal)
        distances, indices = self._index.search(query_vec, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self._events):
                event = self._events[idx]
                event.score = float(1.0 / (1.0 + dist))  # Convert L2 distance to similarity
                results.append(event)
        return results

    def save_to_disk(self, path: Path | None = None) -> None:
        path = path or self._index_path
        if not path:
            return

        path.mkdir(parents=True, exist_ok=True)

        if self._index is not None:
            import faiss

            faiss.write_index(self._index, str(path / "index.faiss"))

        events_data = [asdict(e) for e in self._events]
        with open(path / "events.json", "w") as f:
            json.dump(events_data, f, indent=2)
        logger.info("Saved %d episodic events to %s", len(self._events), path)

    def load_from_disk(self, path: Path | None = None) -> None:
        path = path or self._index_path
        if not path:
            return

        index_file = path / "index.faiss"
        events_file = path / "events.json"

        if index_file.exists():
            import faiss

            self._index = faiss.read_index(str(index_file))

        if events_file.exists():
            with open(events_file) as f:
                events_data = json.load(f)
            self._events = [
                EpisodicEvent(
                    text=e["text"],
                    timestamp=e.get("timestamp", 0),
                    agent=e.get("agent"),
                    metadata=e.get("metadata", {}),
                )
                for e in events_data
            ]
        logger.info("Loaded %d episodic events from %s", len(self._events), path)

    @property
    def count(self) -> int:
        return len(self._events)
