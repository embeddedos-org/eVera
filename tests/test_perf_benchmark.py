"""Performance benchmark tests for eVera API.

Measures response latency and throughput for all key endpoints.
Tests run against the in-process TestClient (no network overhead),
which gives a realistic baseline for per-request processing cost.
"""

from __future__ import annotations

import statistics
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from vera.app import create_app


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def perf_client():
    """Single app instance shared across all performance tests."""
    app = create_app()
    with TestClient(app) as client:
        yield client


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _measure(client, method: str, path: str, **kwargs) -> tuple[float, int]:
    """Return (latency_ms, status_code) for a single request."""
    t0 = time.perf_counter()
    res = getattr(client, method)(path, **kwargs)
    latency_ms = (time.perf_counter() - t0) * 1000
    return latency_ms, res.status_code


def _benchmark(client, method: str, path: str, n: int = 50, **kwargs) -> dict:
    """Run n requests and return latency statistics (ms)."""
    latencies = []
    for _ in range(n):
        lat, status = _measure(client, method, path, **kwargs)
        latencies.append(lat)
    return {
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
        "mean_ms": round(statistics.mean(latencies), 2),
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(sorted(latencies)[int(n * 0.95)], 2),
        "p99_ms": round(sorted(latencies)[int(n * 0.99)], 2),
        "count": n,
    }


# --------------------------------------------------------------------------- #
# Latency budgets (ms) — in-process TestClient, no I/O
# --------------------------------------------------------------------------- #

# These are conservative in-process budgets (no network, no real LLM).
BUDGET_HEALTH_P95_MS = 50
BUDGET_STATUS_P95_MS = 100
BUDGET_INFO_P95_MS = 50
BUDGET_I18N_P95_MS = 50
BUDGET_LOCATION_UPDATE_P95_MS = 200
BUDGET_LOCATION_CURRENT_P95_MS = 50


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_health_latency(perf_client):
    """GET /health should respond in under 50ms (p95)."""
    stats = _benchmark(perf_client, "get", "/health", n=50)
    print(f"\n/health latency: {stats}")
    assert stats["p95_ms"] < BUDGET_HEALTH_P95_MS, (
        f"/health p95 latency {stats['p95_ms']}ms exceeds budget {BUDGET_HEALTH_P95_MS}ms"
    )


def test_status_latency(perf_client):
    """GET /status should respond in under 100ms (p95)."""
    stats = _benchmark(perf_client, "get", "/status", n=50)
    print(f"\n/status latency: {stats}")
    assert stats["p95_ms"] < BUDGET_STATUS_P95_MS, (
        f"/status p95 latency {stats['p95_ms']}ms exceeds budget {BUDGET_STATUS_P95_MS}ms"
    )


def test_info_latency(perf_client):
    """GET /info should respond in under 50ms (p95)."""
    stats = _benchmark(perf_client, "get", "/info", n=50)
    print(f"\n/info latency: {stats}")
    assert stats["p95_ms"] < BUDGET_INFO_P95_MS, (
        f"/info p95 latency {stats['p95_ms']}ms exceeds budget {BUDGET_INFO_P95_MS}ms"
    )


def test_i18n_latency(perf_client):
    """GET /i18n/strings/en should respond in under 50ms (p95)."""
    stats = _benchmark(perf_client, "get", "/i18n/strings/en", n=50)
    print(f"\n/i18n/strings/en latency: {stats}")
    assert stats["p95_ms"] < BUDGET_I18N_P95_MS, (
        f"/i18n/strings/en p95 latency {stats['p95_ms']}ms exceeds budget {BUDGET_I18N_P95_MS}ms"
    )


def test_location_update_latency(perf_client):
    """POST /location/update should respond in under 200ms (p95)."""
    payload = {"latitude": 37.7749, "longitude": -122.4194, "accuracy": 10.0}
    stats = _benchmark(perf_client, "post", "/location/update", n=50, json=payload)
    print(f"\n/location/update latency: {stats}")
    assert stats["p95_ms"] < BUDGET_LOCATION_UPDATE_P95_MS, (
        f"/location/update p95 latency {stats['p95_ms']}ms exceeds budget {BUDGET_LOCATION_UPDATE_P95_MS}ms"
    )


def test_location_current_latency(perf_client):
    """GET /location/current should respond in under 50ms (p95)."""
    # Pre-populate location
    perf_client.post("/location/update", json={"latitude": 37.7749, "longitude": -122.4194})
    stats = _benchmark(perf_client, "get", "/location/current", n=50)
    print(f"\n/location/current latency: {stats}")
    assert stats["p95_ms"] < BUDGET_LOCATION_CURRENT_P95_MS, (
        f"/location/current p95 latency {stats['p95_ms']}ms exceeds budget {BUDGET_LOCATION_CURRENT_P95_MS}ms"
    )


def test_concurrent_health_requests(perf_client):
    """Simulate 100 sequential health requests — all must succeed."""
    failures = 0
    for _ in range(100):
        _, status = _measure(perf_client, "get", "/health")
        if status != 200:
            failures += 1
    assert failures == 0, f"{failures}/100 health requests failed"


def test_concurrent_i18n_requests(perf_client):
    """Simulate 100 sequential i18n requests across all languages — all must succeed."""
    langs = ["en", "es", "fr", "de", "hi", "zh", "ar", "pt", "ja", "ko"]
    failures = 0
    for i in range(100):
        lang = langs[i % len(langs)]
        _, status = _measure(perf_client, "get", f"/i18n/strings/{lang}")
        if status != 200:
            failures += 1
    assert failures == 0, f"{failures}/100 i18n requests failed"


def test_location_update_throughput(perf_client):
    """100 GPS location updates must all succeed (200 OK)."""
    failures = 0
    for i in range(100):
        payload = {
            "latitude": 37.7749 + i * 0.001,
            "longitude": -122.4194 + i * 0.001,
            "accuracy": 10.0,
        }
        _, status = _measure(perf_client, "post", "/location/update", json=payload)
        if status != 200:
            failures += 1
    assert failures == 0, f"{failures}/100 location updates failed"
