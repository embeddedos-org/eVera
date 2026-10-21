"""Unit tests for the production deep health check (issue #46 coverage drive).

Covers vera/monitoring/health.py — deep_health_check(), previously at
0% coverage with no dedicated unit test file. The function duck-types
its ``brain`` argument, so the tests drive it with small local stubs
(no real brain, no I/O, no optional-dependency chain) and pin its
actual semantics, including three asymmetries in how component
failures combine into the overall status:

- a zero-task scheduler reports its check as "degraded" but does NOT
  downgrade the overall status (the downgrade is guarded by
  total > 0);
- a provider-manager exception downgrades the overall status only to
  "degraded", unlike vault/scheduler exceptions ("unhealthy");
- the event-bus and provider exception paths assign overall =
  "degraded" unconditionally, so either one firing after a vault
  failure overwrites "unhealthy" back to "degraded". Pinned as-is;
  changing it is a behaviour fix, not a coverage change.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime
from types import SimpleNamespace

import pytest

from vera.monitoring.health import deep_health_check


class _Task:
    def __init__(self, is_done: bool) -> None:
        self._done = is_done

    def done(self) -> bool:
        return self._done


class _Semantic:
    def __init__(self, facts: list, raises: bool = False) -> None:
        self._facts = facts
        self._raises = raises

    def get_all(self) -> list:
        if self._raises:
            raise RuntimeError("vault read failed")
        return self._facts


class _Vault:
    def __init__(self, facts=(), events: int = 0, raises: bool = False) -> None:
        self.semantic = _Semantic(list(facts), raises=raises)
        self._events = events

    def get_stats(self) -> dict:
        return {"episodic_events": self._events}


class _StatsRaisingVault:
    semantic = _Semantic(["fact"])

    def get_stats(self) -> dict:
        raise RuntimeError("stats failed")


class _Scheduler:
    def __init__(self, tasks: list) -> None:
        self._tasks = tasks


class _RaisingScheduler:
    @property
    def _tasks(self) -> list:
        raise RuntimeError("scheduler read failed")


class _ProviderManager:
    def __init__(self, health: dict) -> None:
        self._provider_health = health


class _RaisingProviderManager:
    @property
    def _provider_health(self) -> dict:
        raise RuntimeError("provider read failed")


def _brain(vault=None, scheduler=None, provider_manager=None) -> SimpleNamespace:
    return SimpleNamespace(
        memory_vault=_Vault(facts=["f1", "f2"], events=7) if vault is None else vault,
        scheduler=_Scheduler([_Task(False), _Task(False)]) if scheduler is None else scheduler,
        provider_manager=_ProviderManager({"a": True, "b": True})
        if provider_manager is None
        else provider_manager,
    )


@pytest.fixture
def broken_event_bus(monkeypatch):
    """Make `from vera.events.bus import _agent_status_queue` raise."""
    broken = types.ModuleType("vera.events.bus")
    monkeypatch.setitem(sys.modules, "vera.events.bus", broken)


class TestAllHealthy:
    def test_overall_shape_and_values(self):
        result = deep_health_check(_brain())
        assert result["status"] == "healthy"
        assert result["version"] == "1.0.0"
        assert result["uptime_seconds"] >= 0
        assert set(result["checks"]) == {"memory_vault", "scheduler", "event_bus", "providers"}

    def test_timestamp_is_iso8601(self):
        result = deep_health_check(_brain())
        parsed = datetime.fromisoformat(result["timestamp"])
        assert parsed.tzinfo is not None

    def test_component_fields(self):
        result = deep_health_check(_brain())
        checks = result["checks"]
        assert checks["memory_vault"] == {"status": "ok", "facts": 2, "events": 7}
        assert checks["scheduler"] == {"status": "ok", "active_loops": 2, "total_loops": 2}
        assert checks["event_bus"]["status"] == "ok"
        assert checks["event_bus"]["queue_size"] >= 0
        assert checks["providers"] == {"status": "ok", "available": 2, "total": 2}


class TestMemoryVault:
    def test_semantic_failure_is_error_and_unhealthy(self):
        result = deep_health_check(_brain(vault=_Vault(raises=True)))
        assert result["checks"]["memory_vault"]["status"] == "error"
        assert "vault read failed" in result["checks"]["memory_vault"]["error"]
        assert result["status"] == "unhealthy"

    def test_stats_failure_is_error_and_unhealthy(self):
        result = deep_health_check(_brain(vault=_StatsRaisingVault()))
        assert result["checks"]["memory_vault"]["status"] == "error"
        assert result["status"] == "unhealthy"

    def test_missing_vault_attribute_is_error(self):
        brain = _brain()
        del brain.memory_vault
        result = deep_health_check(brain)
        assert result["checks"]["memory_vault"]["status"] == "error"
        assert result["status"] == "unhealthy"

    def test_other_checks_still_run_after_vault_failure(self):
        result = deep_health_check(_brain(vault=_Vault(raises=True)))
        assert result["checks"]["scheduler"]["status"] == "ok"
        assert result["checks"]["providers"]["status"] == "ok"
        assert result["checks"]["event_bus"]["status"] == "ok"


class TestScheduler:
    def test_all_tasks_done_degrades_check_and_overall(self):
        brain = _brain(scheduler=_Scheduler([_Task(True), _Task(True)]))
        result = deep_health_check(brain)
        assert result["checks"]["scheduler"] == {
            "status": "degraded",
            "active_loops": 0,
            "total_loops": 2,
        }
        assert result["status"] == "degraded"

    def test_mixed_tasks_are_ok(self):
        brain = _brain(scheduler=_Scheduler([_Task(True), _Task(False)]))
        result = deep_health_check(brain)
        assert result["checks"]["scheduler"]["status"] == "ok"
        assert result["checks"]["scheduler"]["active_loops"] == 1
        assert result["status"] == "healthy"

    def test_zero_tasks_degrades_check_but_not_overall(self):
        # Pinned quirk: the check itself reports "degraded" for an empty
        # task list, but the overall downgrade is guarded by total > 0.
        brain = _brain(scheduler=_Scheduler([]))
        result = deep_health_check(brain)
        assert result["checks"]["scheduler"]["status"] == "degraded"
        assert result["status"] == "healthy"

    def test_scheduler_failure_is_error_and_unhealthy(self):
        result = deep_health_check(_brain(scheduler=_RaisingScheduler()))
        assert result["checks"]["scheduler"]["status"] == "error"
        assert result["status"] == "unhealthy"


class TestEventBus:
    def test_event_bus_failure_degrades_overall(self, broken_event_bus):
        result = deep_health_check(_brain())
        assert result["checks"]["event_bus"]["status"] == "error"
        assert result["status"] == "degraded"

    def test_event_bus_failure_overwrites_unhealthy(self, broken_event_bus):
        # Pinned quirk: the event-bus except path assigns "degraded"
        # unconditionally, overwriting a vault failure's "unhealthy".
        result = deep_health_check(_brain(vault=_Vault(raises=True)))
        assert result["checks"]["memory_vault"]["status"] == "error"
        assert result["checks"]["event_bus"]["status"] == "error"
        assert result["status"] == "degraded"


class TestProviders:
    def test_empty_health_dict_is_ok(self):
        result = deep_health_check(_brain(provider_manager=_ProviderManager({})))
        assert result["checks"]["providers"] == {"status": "ok", "available": 0, "total": 0}
        assert result["status"] == "healthy"

    def test_mixed_providers_degrade(self):
        pm = _ProviderManager({"a": True, "b": False})
        result = deep_health_check(_brain(provider_manager=pm))
        assert result["checks"]["providers"] == {"status": "degraded", "available": 1, "total": 2}
        assert result["status"] == "degraded"

    def test_mixed_providers_do_not_upgrade_unhealthy(self):
        pm = _ProviderManager({"a": True, "b": False})
        result = deep_health_check(_brain(vault=_Vault(raises=True), provider_manager=pm))
        assert result["checks"]["providers"]["status"] == "degraded"
        assert result["status"] == "unhealthy"

    def test_all_providers_down_is_unhealthy(self):
        pm = _ProviderManager({"a": False, "b": False})
        result = deep_health_check(_brain(provider_manager=pm))
        assert result["checks"]["providers"]["status"] == "unhealthy"
        assert result["status"] == "unhealthy"

    def test_provider_failure_is_error_but_only_degrades_overall(self):
        # Pinned asymmetry: unlike vault/scheduler exceptions, a provider
        # exception sets the check to "error" but the overall status only
        # to "degraded".
        result = deep_health_check(_brain(provider_manager=_RaisingProviderManager()))
        assert result["checks"]["providers"]["status"] == "error"
        assert result["status"] == "degraded"

    def test_provider_failure_overwrites_unhealthy(self):
        # Pinned quirk: the provider except path also assigns "degraded"
        # unconditionally, overwriting a vault failure's "unhealthy".
        result = deep_health_check(
            _brain(vault=_Vault(raises=True), provider_manager=_RaisingProviderManager())
        )
        assert result["checks"]["memory_vault"]["status"] == "error"
        assert result["checks"]["providers"]["status"] == "error"
        assert result["status"] == "degraded"
