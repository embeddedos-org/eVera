"""The HTTP 5xx error rate is measured over a recent window, not since start-up.

``MetricsCollector.get_request_error_rate(window_seconds=300.0)`` is
documented as the "5xx error rate over the recent window", and the
``high_error_rate`` alert reads it. Old requests must age out: a burst of
errors long ago must not keep the alert firing, and a fresh burst must not
be diluted by hours of earlier successes.
"""

from __future__ import annotations

import time

import pytest

from vera.monitoring.alerts import AlertManager
from vera.monitoring.metrics import MetricsCollector


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(time, "monotonic", fake)
    return fake


def _record(metrics: MetricsCollector, status: int, n: int) -> None:
    for _ in range(n):
        metrics.record_request("GET", "/api/status", status, 10.0)


class TestWindowedErrorRate:
    def test_old_errors_age_out_of_the_window(self, clock):
        metrics = MetricsCollector()
        _record(metrics, 500, 5)
        clock.now += 600
        _record(metrics, 200, 5)
        assert metrics.get_request_error_rate(window_seconds=300) == 0.0

    def test_recent_errors_are_not_diluted_by_old_successes(self, clock):
        metrics = MetricsCollector()
        _record(metrics, 200, 95)
        clock.now += 3600
        _record(metrics, 503, 5)
        assert metrics.get_request_error_rate(window_seconds=300) == 1.0

    def test_mixed_requests_inside_the_window(self, clock):
        metrics = MetricsCollector()
        _record(metrics, 200, 3)
        _record(metrics, 500, 1)
        assert metrics.get_request_error_rate() == 0.25

    def test_no_requests_in_window_is_zero(self, clock):
        metrics = MetricsCollector()
        assert metrics.get_request_error_rate() == 0.0
        _record(metrics, 500, 2)
        clock.now += 301
        assert metrics.get_request_error_rate(window_seconds=300) == 0.0

    def test_reset_clears_the_window(self, clock):
        metrics = MetricsCollector()
        _record(metrics, 500, 2)
        metrics.reset()
        assert metrics.get_request_error_rate() == 0.0

    def test_lifetime_counters_in_report_are_unchanged(self, clock):
        metrics = MetricsCollector()
        _record(metrics, 500, 2)
        clock.now += 600
        _record(metrics, 200, 2)
        report = metrics.get_metrics()["requests"]
        assert report["GET /api/status 500"]["errors"] == 2
        assert report["GET /api/status 200"]["count"] == 2


class TestHighErrorRateAlert:
    def test_alert_resolves_once_old_errors_leave_the_window(self, clock):
        metrics = MetricsCollector()
        manager = AlertManager(metrics, error_rate_threshold=0.1)
        _record(metrics, 500, 5)
        assert [a.name for a in manager.check()] == ["high_error_rate"]
        clock.now += 600
        _record(metrics, 200, 5)
        manager.check()
        assert "high_error_rate" not in {a["name"] for a in manager.get_alerts()}

    def test_fresh_burst_fires_after_a_long_healthy_run(self, clock):
        metrics = MetricsCollector()
        manager = AlertManager(metrics, error_rate_threshold=0.1)
        _record(metrics, 200, 200)
        clock.now += 3600
        _record(metrics, 502, 5)
        assert "high_error_rate" in [a.name for a in manager.check()]
