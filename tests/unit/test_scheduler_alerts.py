"""Scheduler-failure alerts count consecutive failures, not lifetime errors.

``alert_scheduler_fail_threshold`` is documented in config.py as
"Consecutive scheduler failures before alert". A loop that fails now and
then but recovers in between must not alert, and an alert must resolve
once the loop succeeds again.
"""

from __future__ import annotations

from vera.monitoring.alerts import AlertManager
from vera.monitoring.metrics import MetricsCollector


def _manager(threshold: int = 3) -> tuple[MetricsCollector, AlertManager]:
    metrics = MetricsCollector()
    return metrics, AlertManager(metrics, scheduler_fail_threshold=threshold)


def _active_names(manager: AlertManager) -> set[str]:
    return {a["name"] for a in manager.get_alerts()}


class TestConsecutiveFailureCount:
    def test_success_resets_the_streak(self):
        metrics = MetricsCollector()
        for ok in (False, False, True, False):
            metrics.record_scheduler_run("digest", success=ok)
        assert metrics.get_scheduler_consecutive_failures("digest") == 1

    def test_unbroken_failures_are_counted(self):
        metrics = MetricsCollector()
        for _ in range(4):
            metrics.record_scheduler_run("digest", success=False)
        assert metrics.get_scheduler_consecutive_failures("digest") == 4

    def test_unknown_loop_is_zero(self):
        assert MetricsCollector().get_scheduler_consecutive_failures("nope") == 0

    def test_metrics_report_keeps_lifetime_errors_and_adds_streak(self):
        metrics = MetricsCollector()
        for ok in (False, False, True, False):
            metrics.record_scheduler_run("digest", success=ok)
        data = metrics.get_metrics()["scheduler"]["digest"]
        assert data["errors"] == 3
        assert data["consecutive_failures"] == 1

    def test_reset_clears_streak(self):
        metrics = MetricsCollector()
        metrics.record_scheduler_run("digest", success=False)
        metrics.reset()
        assert metrics.get_scheduler_consecutive_failures("digest") == 0


class TestSchedulerFailAlert:
    def test_non_consecutive_failures_do_not_alert(self):
        metrics, manager = _manager(threshold=3)
        for ok in (False, True, False, True, False, True):
            metrics.record_scheduler_run("digest", success=ok)
        assert manager.check() == []
        assert "scheduler_fail_digest" not in _active_names(manager)

    def test_consecutive_failures_alert(self):
        metrics, manager = _manager(threshold=3)
        for _ in range(3):
            metrics.record_scheduler_run("digest", success=False)
        fired = manager.check()
        assert [a.name for a in fired] == ["scheduler_fail_digest"]
        assert "3 consecutive failures" in fired[0].message

    def test_alert_resolves_after_recovery(self):
        metrics, manager = _manager(threshold=3)
        for _ in range(3):
            metrics.record_scheduler_run("digest", success=False)
        manager.check()
        metrics.record_scheduler_run("digest", success=True)
        manager.check()
        assert "scheduler_fail_digest" not in _active_names(manager)
        resolved = manager.get_alerts(include_resolved=True)
        assert [a["resolved"] for a in resolved if a["name"] == "scheduler_fail_digest"] == [True]

    def test_alert_fires_again_after_a_new_streak(self):
        metrics, manager = _manager(threshold=2)
        for ok in (False, False):
            metrics.record_scheduler_run("digest", success=ok)
        assert len(manager.check()) == 1
        metrics.record_scheduler_run("digest", success=True)
        manager.check()
        for _ in range(2):
            metrics.record_scheduler_run("digest", success=False)
        assert [a.name for a in manager.check()] == ["scheduler_fail_digest"]
