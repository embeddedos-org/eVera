"""Deep health check for eVera production monitoring."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timezone
from typing import Any

_start_time = time.monotonic()


def deep_health_check(brain: Any) -> dict[str, Any]:
    """Run deep health checks against all core subsystems.

    Returns a structured dict with overall status, version, uptime,
    and per-component check results.
    """
    checks: dict[str, dict[str, Any]] = {}
    overall = "healthy"

    # Memory vault check
    try:
        vault = brain.memory_vault
        facts = vault.semantic.get_all()
        stats = vault.get_stats()
        checks["memory_vault"] = {
            "status": "ok",
            "facts": len(facts),
            "events": stats.get("episodic_events", 0),
        }
    except Exception as e:
        checks["memory_vault"] = {"status": "error", "error": str(e)}
        overall = "unhealthy"

    # Scheduler check
    try:
        scheduler = brain.scheduler
        active_loops = len([t for t in scheduler._tasks if not t.done()])
        total_loops = len(scheduler._tasks)
        checks["scheduler"] = {
            "status": "ok" if active_loops > 0 else "degraded",
            "active_loops": active_loops,
            "total_loops": total_loops,
        }
        if active_loops == 0 and total_loops > 0:
            overall = "degraded"
    except Exception as e:
        checks["scheduler"] = {"status": "error", "error": str(e)}
        overall = "unhealthy"

    # Event bus check
    try:
        from vera.events.bus import _agent_status_queue

        checks["event_bus"] = {
            "status": "ok",
            "queue_size": _agent_status_queue.qsize(),
        }
    except Exception as e:
        checks["event_bus"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # Provider check
    try:
        pm = brain.provider_manager
        health = pm._provider_health
        available = sum(1 for v in health.values() if v)
        total = len(health)
        if total == 0:
            status = "ok"  # No health checks run yet
        elif available == total:
            status = "ok"
        elif available > 0:
            status = "degraded"
            if overall == "healthy":
                overall = "degraded"
        else:
            status = "unhealthy"
            overall = "unhealthy"

        checks["providers"] = {
            "status": status,
            "available": available,
            "total": total,
        }
    except Exception as e:
        checks["providers"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    return {
        "status": overall,
        "version": "1.0.0",
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }
