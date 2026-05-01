"""Alerting system for eVera production monitoring.

Checks metrics thresholds periodically and pushes alerts via
the existing notification handler infrastructure.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any

from vera.monitoring.metrics import MetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """A single triggered alert."""

    name: str
    severity: str  # "warning" or "critical"
    message: str
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "time_iso": datetime.fromtimestamp(self.timestamp, tz=UTC).isoformat(),
        }


class AlertManager:
    """Evaluates metrics against thresholds and manages active alerts."""

    def __init__(
        self,
        metrics: MetricsCollector,
        error_rate_threshold: float = 0.1,
        latency_threshold_ms: float = 5000.0,
        scheduler_fail_threshold: int = 3,
    ) -> None:
        self._metrics = metrics
        self._error_rate_threshold = error_rate_threshold
        self._latency_threshold_ms = latency_threshold_ms
        self._scheduler_fail_threshold = scheduler_fail_threshold
        self._alerts: list[Alert] = []
        self._active_alert_names: set[str] = set()

    def check(self) -> list[Alert]:
        """Run all alert checks and return any newly fired alerts."""
        new_alerts: list[Alert] = []

        # 1. HTTP error rate
        error_rate = self._metrics.get_request_error_rate()
        alert_name = "high_error_rate"
        if error_rate > self._error_rate_threshold:
            if alert_name not in self._active_alert_names:
                alert = Alert(
                    name=alert_name,
                    severity="critical",
                    message=(f"HTTP 5xx error rate is {error_rate:.1%}, threshold is {self._error_rate_threshold:.1%}"),
                )
                self._alerts.append(alert)
                self._active_alert_names.add(alert_name)
                new_alerts.append(alert)
        else:
            self._resolve(alert_name)

        # 2. LLM error rate
        llm_error_rate = self._metrics.get_llm_error_rate()
        alert_name = "high_llm_error_rate"
        if llm_error_rate > self._error_rate_threshold:
            if alert_name not in self._active_alert_names:
                alert = Alert(
                    name=alert_name,
                    severity="critical",
                    message=(f"LLM error rate is {llm_error_rate:.1%}, threshold is {self._error_rate_threshold:.1%}"),
                )
                self._alerts.append(alert)
                self._active_alert_names.add(alert_name)
                new_alerts.append(alert)
        else:
            self._resolve(alert_name)

        # 3. Average request latency
        avg_latency = self._metrics.get_avg_request_latency()
        alert_name = "high_latency"
        if avg_latency > self._latency_threshold_ms and avg_latency > 0:
            if alert_name not in self._active_alert_names:
                alert = Alert(
                    name=alert_name,
                    severity="warning",
                    message=(
                        f"Average response latency is {avg_latency:.0f}ms, "
                        f"threshold is {self._latency_threshold_ms:.0f}ms"
                    ),
                )
                self._alerts.append(alert)
                self._active_alert_names.add(alert_name)
                new_alerts.append(alert)
        else:
            self._resolve(alert_name)

        # 4. Scheduler failures
        metrics_data = self._metrics.get_metrics()
        for loop_name, data in metrics_data.get("scheduler", {}).items():
            alert_name = f"scheduler_fail_{loop_name}"
            if data.get("errors", 0) >= self._scheduler_fail_threshold:
                if alert_name not in self._active_alert_names:
                    alert = Alert(
                        name=alert_name,
                        severity="warning",
                        message=(
                            f"Scheduler loop '{loop_name}' has "
                            f"{data['errors']} failures "
                            f"(threshold: {self._scheduler_fail_threshold})"
                        ),
                    )
                    self._alerts.append(alert)
                    self._active_alert_names.add(alert_name)
                    new_alerts.append(alert)
            else:
                self._resolve(alert_name)

        return new_alerts

    def _resolve(self, alert_name: str) -> None:
        """Mark an active alert as resolved."""
        if alert_name in self._active_alert_names:
            self._active_alert_names.discard(alert_name)
            for alert in reversed(self._alerts):
                if alert.name == alert_name and not alert.resolved:
                    alert.resolved = True
                    break

    def get_alerts(self, include_resolved: bool = False) -> list[dict[str, Any]]:
        """Return alerts as dicts."""
        alerts = self._alerts if include_resolved else [a for a in self._alerts if not a.resolved]
        return [a.to_dict() for a in alerts[-50:]]  # Last 50

    def reset(self) -> None:
        """Clear all alerts. Used for testing."""
        self._alerts.clear()
        self._active_alert_names.clear()
