"""Thread-safe in-memory metrics collector for eVera.

Tracks request latency, LLM calls, scheduler runs, and agent dispatches
with no external dependencies.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Counter:
    """Accumulator for count + total (for averages)."""

    count: int = 0
    total: float = 0.0
    errors: int = 0

    def record(self, value: float = 0.0, error: bool = False) -> None:
        self.count += 1
        self.total += value
        if error:
            self.errors += 1

    @property
    def avg(self) -> float:
        return self.total / self.count if self.count else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "total": round(self.total, 2),
            "avg": round(self.avg, 2),
            "errors": self.errors,
        }


@dataclass
class _ErrorEntry:
    timestamp: float
    message: str


class MetricsCollector:
    """Singleton-style, thread-safe metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time = time.monotonic()
        self._requests: dict[tuple[str, str, int], _Counter] = defaultdict(_Counter)
        self._llm: dict[tuple[str, str, str], _Counter] = defaultdict(_Counter)
        self._llm_tokens: dict[tuple[str, str, str], int] = defaultdict(int)
        self._scheduler: dict[str, _Counter] = defaultdict(_Counter)
        self._scheduler_last_run: dict[str, float] = {}
        self._agents: dict[str, _Counter] = defaultdict(_Counter)
        self._recent_errors: deque[_ErrorEntry] = deque(maxlen=100)

    # --- Recording methods ---

    def record_request(self, method: str, path: str, status_code: int, latency_ms: float) -> None:
        with self._lock:
            key = (method, path, status_code)
            self._requests[key].record(latency_ms, error=(status_code >= 500))
            if status_code >= 500:
                self._recent_errors.append(_ErrorEntry(time.time(), f"HTTP {status_code} {method} {path}"))

    def record_llm_call(
        self,
        provider: str,
        model: str,
        tier: str,
        tokens: int,
        latency_ms: float,
        error: bool = False,
    ) -> None:
        with self._lock:
            key = (provider, model, tier)
            self._llm[key].record(latency_ms, error=error)
            self._llm_tokens[key] += tokens
            if error:
                self._recent_errors.append(_ErrorEntry(time.time(), f"LLM error: {provider}/{model}"))

    def record_scheduler_run(self, loop_name: str, success: bool = True, duration_ms: float = 0.0) -> None:
        with self._lock:
            self._scheduler[loop_name].record(duration_ms, error=not success)
            self._scheduler_last_run[loop_name] = time.time()
            if not success:
                self._recent_errors.append(_ErrorEntry(time.time(), f"Scheduler failure: {loop_name}"))

    def record_agent_dispatch(self, agent_name: str, latency_ms: float, error: bool = False) -> None:
        with self._lock:
            self._agents[agent_name].record(latency_ms, error=error)
            if error:
                self._recent_errors.append(_ErrorEntry(time.time(), f"Agent error: {agent_name}"))

    # --- Query methods ---

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "uptime_seconds": round(time.monotonic() - self._start_time, 1),
                "requests": {f"{m} {p} {s}": c.to_dict() for (m, p, s), c in self._requests.items()},
                "llm": {
                    f"{prov}/{model} ({tier})": {
                        **c.to_dict(),
                        "tokens": self._llm_tokens[(prov, model, tier)],
                    }
                    for (prov, model, tier), c in self._llm.items()
                },
                "scheduler": {
                    name: {
                        **c.to_dict(),
                        "last_run": self._scheduler_last_run.get(name),
                    }
                    for name, c in self._scheduler.items()
                },
                "agents": {name: c.to_dict() for name, c in self._agents.items()},
                "recent_errors": [{"timestamp": e.timestamp, "message": e.message} for e in self._recent_errors],
            }

    def get_request_error_rate(self, window_seconds: float = 300.0) -> float:
        """Calculate 5xx error rate over the recent window."""
        with self._lock:
            total = sum(c.count for c in self._requests.values())
            errors = sum(c.errors for c in self._requests.values())
            return errors / total if total else 0.0

    def get_llm_error_rate(self) -> float:
        with self._lock:
            total = sum(c.count for c in self._llm.values())
            errors = sum(c.errors for c in self._llm.values())
            return errors / total if total else 0.0

    def get_avg_request_latency(self) -> float:
        with self._lock:
            total_count = sum(c.count for c in self._requests.values())
            total_latency = sum(c.total for c in self._requests.values())
            return total_latency / total_count if total_count else 0.0

    def get_scheduler_consecutive_failures(self, loop_name: str) -> int:
        """Return the error count for a scheduler loop."""
        with self._lock:
            counter = self._scheduler.get(loop_name)
            return counter.errors if counter else 0

    def reset(self) -> None:
        """Reset all metrics. Used for testing."""
        with self._lock:
            self._start_time = time.monotonic()
            self._requests.clear()
            self._llm.clear()
            self._llm_tokens.clear()
            self._scheduler.clear()
            self._scheduler_last_run.clear()
            self._agents.clear()
            self._recent_errors.clear()
