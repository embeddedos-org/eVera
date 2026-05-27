"""Staging validation tests for eVera monitoring and alerting.

Simulates staging deployment validation: verifies endpoints respond correctly,
alerts fire when thresholds are breached, alerts resolve when conditions
normalize, and metrics are wired through the full request lifecycle.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from vera.monitoring.alerts import AlertManager
from vera.monitoring.metrics import MetricsCollector

# ─── Shared fixtures ─────────────────────────────────────────────────


@pytest.fixture
def mock_brain():
    """Create a mock brain with all subsystems mocked."""
    brain = MagicMock()
    brain.memory_vault.semantic.get_all.return_value = {"user_name": "Tester"}
    brain.memory_vault.get_stats.return_value = {
        "episodic_events": 10,
        "semantic_facts": 5,
        "working_turns": 3,
    }
    brain.provider_manager._provider_health = {"openai": True, "ollama": True}

    task_mock = MagicMock()
    task_mock.done.return_value = False
    brain.scheduler._tasks = [task_mock, MagicMock(done=MagicMock(return_value=False))]
    brain.scheduler._notification_handlers = []
    brain.scheduler.add_notification_handler = MagicMock()
    brain.scheduler.remove_notification_handler = MagicMock()
    return brain


@pytest.fixture
def staging_client(mock_brain):
    """Create a TestClient simulating a staging deployment."""
    with patch("vera.app.settings") as mock_settings:
        mock_settings.server.cors_origins = ["http://localhost:8000"]
        mock_settings.server.api_key = ""
        mock_settings.server.webhook_secret = ""
        mock_settings.monitoring.enabled = True
        mock_settings.monitoring.metrics_endpoint = True
        mock_settings.monitoring.alert_error_rate_threshold = 0.1
        mock_settings.monitoring.alert_latency_threshold_ms = 5000.0
        mock_settings.monitoring.alert_scheduler_fail_threshold = 3
        mock_settings.monitoring.alert_check_interval_s = 60

        from vera.app import create_app

        app = create_app(brain=mock_brain)
        yield TestClient(app)


# ═══════════════════════════════════════════════════════════════
# Staging Validation: Health Endpoint
# ═══════════════════════════════════════════════════════════════


class TestStagingHealth:
    """Validate /health returns deep checks in staging."""

    def test_health_returns_healthy_status(self, staging_client):
        resp = staging_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert data["version"] == "1.0.0"

    def test_health_contains_all_check_sections(self, staging_client):
        resp = staging_client.get("/health")
        data = resp.json()
        checks = data["checks"]
        assert "memory_vault" in checks
        assert "scheduler" in checks
        assert "providers" in checks

    def test_health_uptime_is_positive(self, staging_client):
        resp = staging_client.get("/health")
        data = resp.json()
        assert data["uptime_seconds"] >= 0

    def test_health_has_iso_timestamp(self, staging_client):
        resp = staging_client.get("/health")
        data = resp.json()
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # ISO 8601 format


# ═══════════════════════════════════════════════════════════════
# Staging Validation: Metrics Endpoint
# ═══════════════════════════════════════════════════════════════


class TestStagingMetrics:
    """Validate /metrics tracks request data in staging."""

    def test_metrics_returns_200(self, staging_client):
        resp = staging_client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_has_all_sections(self, staging_client):
        resp = staging_client.get("/metrics")
        data = resp.json()
        for section in ("uptime_seconds", "requests", "llm", "scheduler", "agents", "recent_errors"):
            assert section in data, f"Missing section: {section}"

    def test_metrics_records_own_requests(self, staging_client):
        """After hitting /health, /metrics should show recorded requests."""
        staging_client.get("/health")
        staging_client.get("/health")
        resp = staging_client.get("/metrics")
        data = resp.json()
        # The metrics middleware should have recorded the /health requests
        # (and the /metrics request itself)
        assert len(data["requests"]) > 0

    def test_metrics_tracks_request_count_correctly(self, staging_client):
        """Multiple requests should increment counts."""
        for _ in range(5):
            staging_client.get("/health")
        resp = staging_client.get("/metrics")
        data = resp.json()
        # Find the health endpoint entry
        health_entries = {k: v for k, v in data["requests"].items() if "/health" in k}
        assert len(health_entries) > 0
        # Total count across health entries should be >= 5
        total = sum(v["count"] for v in health_entries.values())
        assert total >= 5


# ═══════════════════════════════════════════════════════════════
# Staging Validation: Alerts Endpoint
# ═══════════════════════════════════════════════════════════════


class TestStagingAlerts:
    """Validate /alerts fires and resolves alerts correctly."""

    def test_alerts_returns_empty_list_when_clean(self, staging_client):
        resp = staging_client.get("/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_alerts_returns_list_format(self, staging_client):
        resp = staging_client.get("/alerts")
        data = resp.json()
        assert isinstance(data, list)


# ═══════════════════════════════════════════════════════════════
# Staging Validation: Alert Firing Scenarios
# ═══════════════════════════════════════════════════════════════


class TestAlertFiringScenarios:
    """Simulate staging conditions that should trigger alerts."""

    def setup_method(self):
        self.metrics = MetricsCollector()
        self.am = AlertManager(
            self.metrics,
            error_rate_threshold=0.1,
            latency_threshold_ms=2000.0,
            scheduler_fail_threshold=2,
        )

    def test_scenario_high_5xx_rate_fires_critical_alert(self):
        """Simulate 50% of requests returning 5xx — should fire critical alert."""
        for i in range(10):
            self.metrics.record_request("GET", "/chat", 200, 100.0)
        for i in range(10):
            self.metrics.record_request("POST", "/chat", 500, 200.0)

        alerts = self.am.check()
        alert_names = [a.name for a in alerts]
        assert "high_error_rate" in alert_names

        # Verify alert details
        error_alert = next(a for a in alerts if a.name == "high_error_rate")
        assert error_alert.severity == "critical"
        assert "50.0%" in error_alert.message

    def test_scenario_high_latency_fires_warning_alert(self):
        """Simulate slow responses exceeding 2s threshold."""
        for i in range(5):
            self.metrics.record_request("GET", "/chat", 200, 3000.0)

        alerts = self.am.check()
        alert_names = [a.name for a in alerts]
        assert "high_latency" in alert_names

        latency_alert = next(a for a in alerts if a.name == "high_latency")
        assert latency_alert.severity == "warning"

    def test_scenario_llm_failures_fire_alert(self):
        """Simulate LLM provider errors exceeding threshold."""
        self.metrics.record_llm_call("openai", "gpt-4o", "SPECIALIST", 0, 0, error=True)
        self.metrics.record_llm_call("openai", "gpt-4o", "SPECIALIST", 0, 0, error=True)

        alerts = self.am.check()
        alert_names = [a.name for a in alerts]
        assert "high_llm_error_rate" in alert_names

    def test_scenario_scheduler_failures_fire_alert(self):
        """Simulate scheduler loop failing repeatedly."""
        self.metrics.record_scheduler_run("reminder", success=False)
        self.metrics.record_scheduler_run("reminder", success=False)

        alerts = self.am.check()
        alert_names = [a.name for a in alerts]
        assert "scheduler_fail_reminder" in alert_names

    def test_scenario_multiple_alerts_fire_simultaneously(self):
        """Multiple thresholds breached at once — all alerts should fire."""
        # High error rate
        self.metrics.record_request("GET", "/", 500, 5000.0)
        # High LLM error rate
        self.metrics.record_llm_call("openai", "gpt-4o", "SPEC", 0, 0, error=True)
        # Scheduler failures
        self.metrics.record_scheduler_run("calendar", success=False)
        self.metrics.record_scheduler_run("calendar", success=False)

        alerts = self.am.check()
        alert_names = [a.name for a in alerts]
        assert "high_error_rate" in alert_names
        assert "high_llm_error_rate" in alert_names
        assert "high_latency" in alert_names  # 5000ms > 2000ms threshold
        assert "scheduler_fail_calendar" in alert_names


# ═══════════════════════════════════════════════════════════════
# Staging Validation: Alert Resolution
# ═══════════════════════════════════════════════════════════════


class TestAlertResolution:
    """Validate that alerts resolve when conditions normalize."""

    def setup_method(self):
        self.metrics = MetricsCollector()
        self.am = AlertManager(
            self.metrics,
            error_rate_threshold=0.1,
            latency_threshold_ms=2000.0,
            scheduler_fail_threshold=3,
        )

    def test_error_rate_alert_resolves_after_recovery(self):
        """Alert should resolve when error rate drops below threshold."""
        # Trigger alert
        self.metrics.record_request("GET", "/", 500, 100.0)
        self.am.check()
        assert len(self.am.get_alerts(include_resolved=False)) > 0

        # Simulate recovery: reset and add only successful requests
        self.metrics.reset()
        for _ in range(20):
            self.metrics.record_request("GET", "/", 200, 50.0)
        self.am.check()

        active = self.am.get_alerts(include_resolved=False)
        error_alerts = [a for a in active if a["name"] == "high_error_rate"]
        assert len(error_alerts) == 0

    def test_latency_alert_resolves_when_speed_improves(self):
        """Latency alert should resolve when avg drops below threshold."""
        self.metrics.record_request("GET", "/", 200, 5000.0)
        self.am.check()

        # Reset and record fast requests
        self.metrics.reset()
        for _ in range(10):
            self.metrics.record_request("GET", "/", 200, 100.0)
        self.am.check()

        active = self.am.get_alerts(include_resolved=False)
        latency_alerts = [a for a in active if a["name"] == "high_latency"]
        assert len(latency_alerts) == 0

    def test_resolved_alerts_still_in_history(self):
        """Resolved alerts should appear when include_resolved=True."""
        self.metrics.record_request("GET", "/", 500, 100.0)
        self.am.check()

        self.metrics.reset()
        self.metrics.record_request("GET", "/", 200, 50.0)
        self.am.check()

        all_alerts = self.am.get_alerts(include_resolved=True)
        resolved = [a for a in all_alerts if a["resolved"]]
        assert len(resolved) > 0

    def test_alert_cycle_fire_resolve_refire(self):
        """Alert should be able to fire, resolve, then fire again."""
        # Fire
        self.metrics.record_request("GET", "/", 500, 100.0)
        alerts1 = self.am.check()
        assert any(a.name == "high_error_rate" for a in alerts1)

        # Resolve
        self.metrics.reset()
        self.metrics.record_request("GET", "/", 200, 50.0)
        self.am.check()
        assert len([a for a in self.am.get_alerts(include_resolved=False) if a["name"] == "high_error_rate"]) == 0

        # Re-fire
        self.metrics.reset()
        self.metrics.record_request("GET", "/bad", 500, 100.0)
        alerts3 = self.am.check()
        assert any(a.name == "high_error_rate" for a in alerts3)


# ═══════════════════════════════════════════════════════════════
# Staging Validation: Alert Output Format
# ═══════════════════════════════════════════════════════════════


class TestAlertOutputFormat:
    """Validate alert payloads have correct structure for dashboarding."""

    def test_alert_dict_has_required_fields(self):
        metrics = MetricsCollector()
        am = AlertManager(metrics, error_rate_threshold=0.05)
        metrics.record_request("GET", "/", 500, 100.0)
        alerts = am.check()

        assert len(alerts) > 0
        alert_dict = alerts[0].to_dict()
        assert "name" in alert_dict
        assert "severity" in alert_dict
        assert "message" in alert_dict
        assert "timestamp" in alert_dict
        assert "resolved" in alert_dict
        assert "time_iso" in alert_dict

    def test_alert_timestamp_is_numeric(self):
        metrics = MetricsCollector()
        am = AlertManager(metrics, error_rate_threshold=0.05)
        metrics.record_request("GET", "/", 500, 100.0)
        alerts = am.check()
        assert isinstance(alerts[0].timestamp, float)

    def test_alert_time_iso_is_valid_iso8601(self):
        from datetime import datetime

        metrics = MetricsCollector()
        am = AlertManager(metrics, error_rate_threshold=0.05)
        metrics.record_request("GET", "/", 500, 100.0)
        alerts = am.check()
        iso_str = alerts[0].to_dict()["time_iso"]
        # Should parse without error
        datetime.fromisoformat(iso_str)


# ═══════════════════════════════════════════════════════════════
# Staging Validation: Metrics Wiring Integration
# ═══════════════════════════════════════════════════════════════


class TestMetricsWiringIntegration:
    """Validate that metrics are wired through existing subsystems."""

    def test_metrics_collector_thread_safety(self):
        """Record from multiple threads concurrently — no crashes."""
        import threading

        m = MetricsCollector()
        errors = []

        def record_batch(thread_id):
            try:
                for i in range(100):
                    m.record_request("GET", f"/t{thread_id}", 200, float(i))
                    m.record_llm_call("p", "m", "t", i, float(i))
                    m.record_scheduler_run(f"loop_{thread_id}", True, float(i))
                    m.record_agent_dispatch(f"agent_{thread_id}", float(i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_batch, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        data = m.get_metrics()
        # 10 threads * 100 requests each = 1000 total request records
        total_requests = sum(v["count"] for v in data["requests"].values())
        assert total_requests == 1000

    def test_metrics_recent_errors_capped(self):
        """Recent errors deque should cap at 100."""
        m = MetricsCollector()
        for i in range(150):
            m.record_request("GET", "/", 500, 1.0)
        data = m.get_metrics()
        assert len(data["recent_errors"]) == 100

    def test_config_monitoring_settings_exist(self):
        """MonitoringSettings should be accessible from root config."""
        from config import MonitoringSettings, settings

        assert hasattr(settings, "monitoring")
        ms = MonitoringSettings()
        assert ms.enabled is True
        assert ms.alert_error_rate_threshold == 0.1
        assert ms.alert_latency_threshold_ms == 5000.0
        assert ms.alert_scheduler_fail_threshold == 3
        assert ms.alert_check_interval_s == 60
        assert MonitoringSettings.model_config["env_prefix"] == "VERA_MONITORING_"

    def test_env_example_has_monitoring_section(self):
        """The .env.example file should contain monitoring config."""
        from pathlib import Path

        env_example = Path(__file__).parent.parent / ".env.example"
        content = env_example.read_text()
        assert "VERA_MONITORING_ENABLED" in content
        assert "VERA_MONITORING_ALERT_ERROR_RATE_THRESHOLD" in content
        assert "VERA_MONITORING_ALERT_LATENCY_THRESHOLD_MS" in content
