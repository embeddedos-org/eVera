"""Tests for eVera production monitoring and alerting."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vera.monitoring.alerts import AlertManager
from vera.monitoring.metrics import MetricsCollector

# ─── MetricsCollector tests ───────────────────────────────────────────


class TestMetricsCollector:
    def setup_method(self):
        self.m = MetricsCollector()

    def test_record_request(self):
        self.m.record_request("GET", "/health", 200, 5.0)
        self.m.record_request("GET", "/health", 200, 10.0)
        data = self.m.get_metrics()
        key = "GET /health 200"
        assert key in data["requests"]
        assert data["requests"][key]["count"] == 2
        assert data["requests"][key]["avg"] == 7.5
        assert data["requests"][key]["errors"] == 0

    def test_record_request_error(self):
        self.m.record_request("POST", "/chat", 500, 100.0)
        data = self.m.get_metrics()
        key = "POST /chat 500"
        assert data["requests"][key]["errors"] == 1
        assert len(data["recent_errors"]) == 1

    def test_record_llm_call(self):
        self.m.record_llm_call("openai", "gpt-4o", "SPECIALIST", 500, 1200.0)
        self.m.record_llm_call("openai", "gpt-4o", "SPECIALIST", 300, 800.0, error=True)
        data = self.m.get_metrics()
        key = "openai/gpt-4o (SPECIALIST)"
        assert key in data["llm"]
        assert data["llm"][key]["count"] == 2
        assert data["llm"][key]["tokens"] == 800
        assert data["llm"][key]["errors"] == 1

    def test_record_scheduler_run(self):
        self.m.record_scheduler_run("reminder", success=True, duration_ms=50.0)
        self.m.record_scheduler_run("reminder", success=False, duration_ms=10.0)
        data = self.m.get_metrics()
        assert "reminder" in data["scheduler"]
        assert data["scheduler"]["reminder"]["count"] == 2
        assert data["scheduler"]["reminder"]["errors"] == 1
        assert data["scheduler"]["reminder"]["last_run"] is not None

    def test_record_agent_dispatch(self):
        self.m.record_agent_dispatch("companion", 300.0)
        self.m.record_agent_dispatch("companion", 500.0, error=True)
        data = self.m.get_metrics()
        assert "companion" in data["agents"]
        assert data["agents"]["companion"]["count"] == 2
        assert data["agents"]["companion"]["errors"] == 1

    def test_get_request_error_rate(self):
        self.m.record_request("GET", "/health", 200, 5.0)
        self.m.record_request("GET", "/chat", 500, 100.0)
        rate = self.m.get_request_error_rate()
        assert rate == 0.5  # 1 error out of 2

    def test_get_llm_error_rate(self):
        self.m.record_llm_call("openai", "gpt-4o", "SPECIALIST", 100, 500.0)
        assert self.m.get_llm_error_rate() == 0.0
        self.m.record_llm_call("openai", "gpt-4o", "SPECIALIST", 0, 0, error=True)
        assert self.m.get_llm_error_rate() == 0.5

    def test_get_avg_request_latency(self):
        self.m.record_request("GET", "/a", 200, 100.0)
        self.m.record_request("GET", "/b", 200, 200.0)
        assert self.m.get_avg_request_latency() == 150.0

    def test_uptime(self):
        data = self.m.get_metrics()
        assert data["uptime_seconds"] >= 0

    def test_reset(self):
        self.m.record_request("GET", "/", 200, 5.0)
        self.m.record_llm_call("x", "y", "z", 1, 1.0)
        self.m.reset()
        data = self.m.get_metrics()
        assert data["requests"] == {}
        assert data["llm"] == {}
        assert data["scheduler"] == {}
        assert data["agents"] == {}
        assert data["recent_errors"] == []


# ─── AlertManager tests ──────────────────────────────────────────────


class TestAlertManager:
    def setup_method(self):
        self.metrics = MetricsCollector()
        self.am = AlertManager(
            self.metrics,
            error_rate_threshold=0.1,
            latency_threshold_ms=1000.0,
            scheduler_fail_threshold=2,
        )

    def test_no_alerts_when_clean(self):
        alerts = self.am.check()
        assert alerts == []

    def test_error_rate_alert(self):
        # 1 success, 1 error = 50% error rate > 10% threshold
        self.metrics.record_request("GET", "/", 200, 5.0)
        self.metrics.record_request("GET", "/bad", 500, 5.0)
        alerts = self.am.check()
        names = [a.name for a in alerts]
        assert "high_error_rate" in names

    def test_error_rate_alert_not_duplicate(self):
        self.metrics.record_request("GET", "/bad", 500, 5.0)
        self.am.check()
        # Second check should not create duplicate
        alerts = self.am.check()
        assert len([a for a in alerts if a.name == "high_error_rate"]) == 0

    def test_llm_error_rate_alert(self):
        self.metrics.record_llm_call("openai", "gpt-4o", "SPEC", 0, 0, error=True)
        alerts = self.am.check()
        names = [a.name for a in alerts]
        assert "high_llm_error_rate" in names

    def test_latency_alert(self):
        self.metrics.record_request("GET", "/slow", 200, 2000.0)
        alerts = self.am.check()
        names = [a.name for a in alerts]
        assert "high_latency" in names

    def test_scheduler_failure_alert(self):
        self.metrics.record_scheduler_run("reminder", success=False)
        self.metrics.record_scheduler_run("reminder", success=False)
        alerts = self.am.check()
        names = [a.name for a in alerts]
        assert "scheduler_fail_reminder" in names

    def test_alert_resolves(self):
        self.metrics.record_request("GET", "/bad", 500, 5.0)
        self.am.check()
        # Now add many successes to bring rate below threshold
        self.metrics.reset()
        self.metrics.record_request("GET", "/", 200, 5.0)
        self.am.check()
        active = self.am.get_alerts(include_resolved=False)
        # high_error_rate should be resolved
        error_alerts = [a for a in active if a["name"] == "high_error_rate"]
        assert len(error_alerts) == 0

    def test_get_alerts_with_resolved(self):
        self.metrics.record_request("GET", "/bad", 500, 5.0)
        self.am.check()
        self.metrics.reset()
        self.metrics.record_request("GET", "/", 200, 5.0)
        self.am.check()
        all_alerts = self.am.get_alerts(include_resolved=True)
        assert len(all_alerts) >= 1

    def test_reset(self):
        self.metrics.record_request("GET", "/bad", 500, 5.0)
        self.am.check()
        self.am.reset()
        assert self.am.get_alerts() == []


# ─── Health check tests ──────────────────────────────────────────────


class TestHealthCheck:
    def test_healthy_status(self):
        from vera.monitoring.health import deep_health_check

        brain = MagicMock()
        brain.memory_vault.semantic.get_all.return_value = {"key": "value"}
        brain.memory_vault.get_stats.return_value = {"episodic_events": 5}

        task_mock = MagicMock()
        task_mock.done.return_value = False
        brain.scheduler._tasks = [task_mock]

        brain.provider_manager._provider_health = {"openai": True}

        result = deep_health_check(brain)
        assert result["status"] == "healthy"
        assert result["version"] == "1.0.0"
        assert "uptime_seconds" in result
        assert "timestamp" in result
        assert result["checks"]["memory_vault"]["status"] == "ok"
        assert result["checks"]["scheduler"]["status"] == "ok"
        assert result["checks"]["providers"]["status"] == "ok"

    def test_degraded_when_provider_partial(self):
        from vera.monitoring.health import deep_health_check

        brain = MagicMock()
        brain.memory_vault.semantic.get_all.return_value = {}
        brain.memory_vault.get_stats.return_value = {}

        task_mock = MagicMock()
        task_mock.done.return_value = False
        brain.scheduler._tasks = [task_mock]

        brain.provider_manager._provider_health = {
            "openai": True,
            "ollama": False,
        }

        result = deep_health_check(brain)
        assert result["status"] == "degraded"
        assert result["checks"]["providers"]["status"] == "degraded"

    def test_unhealthy_when_memory_fails(self):
        from vera.monitoring.health import deep_health_check

        brain = MagicMock()
        brain.memory_vault.semantic.get_all.side_effect = Exception("DB error")

        task_mock = MagicMock()
        task_mock.done.return_value = False
        brain.scheduler._tasks = [task_mock]
        brain.provider_manager._provider_health = {}

        result = deep_health_check(brain)
        assert result["status"] == "unhealthy"
        assert result["checks"]["memory_vault"]["status"] == "error"


# ─── Endpoint tests ──────────────────────────────────────────────────


class TestEndpoints:
    @pytest.fixture
    def client(self):
        """Create a test client with mocked brain."""
        from unittest.mock import PropertyMock

        from fastapi.testclient import TestClient

        mock_brain = MagicMock()
        mock_brain.memory_vault.semantic.get_all.return_value = {}
        mock_brain.memory_vault.get_stats.return_value = {}
        mock_brain.provider_manager._provider_health = {}

        task_mock = MagicMock()
        task_mock.done.return_value = False
        mock_brain.scheduler._tasks = [task_mock]
        mock_brain.scheduler._notification_handlers = []
        mock_brain.scheduler.add_notification_handler = MagicMock()
        mock_brain.scheduler.remove_notification_handler = MagicMock()

        # Patch settings to avoid needing .env
        with patch("vera.app.settings") as mock_settings:
            mock_settings.server.cors_origins = ["http://localhost:8000"]
            mock_settings.server.api_key = ""
            mock_settings.server.webhook_secret = ""
            mock_settings.monitoring.alert_error_rate_threshold = 0.1
            mock_settings.monitoring.alert_latency_threshold_ms = 5000.0
            mock_settings.monitoring.alert_scheduler_fail_threshold = 3

            from vera.app import create_app

            app = create_app(brain=mock_brain)
            yield TestClient(app)

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "checks" in data

    def test_metrics_endpoint(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "requests" in data
        assert "llm" in data
        assert "scheduler" in data
        assert "agents" in data

    def test_alerts_endpoint(self, client):
        resp = client.get("/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
