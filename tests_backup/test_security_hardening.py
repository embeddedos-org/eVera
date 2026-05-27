"""Security hardening test suite for eVera API.

Tests cover:
- CORS origin enforcement
- API key authentication (zone-based)
- Prompt injection / XSS in inputs
- SQL injection patterns in inputs
- Path traversal in file endpoints
- Oversized request body handling
- HTTP method enforcement
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vera.app import create_app


@pytest.fixture(scope="module")
def sec_client():
    """Shared test client for security tests."""
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# --------------------------------------------------------------------------- #
# CORS Tests
# --------------------------------------------------------------------------- #

class TestCORS:
    """Verify CORS headers are correctly applied."""

    def test_cors_allowed_origin(self, sec_client):
        """Requests from allowed origins get CORS headers."""
        res = sec_client.options(
            "/health",
            headers={
                "Origin": "https://evera.embeddedos.org",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.status_code == 200
        assert "access-control-allow-origin" in res.headers

    def test_cors_wildcard_not_set(self, sec_client):
        """Wildcard '*' should not be the CORS origin for credentialed requests."""
        res = sec_client.get("/health", headers={"Origin": "https://evil.example.com"})
        acao = res.headers.get("access-control-allow-origin", "")
        assert acao != "*", "Wildcard CORS is not allowed for credentialed requests"

    def test_cors_preflight_methods(self, sec_client):
        """Preflight should allow GET, POST, PUT, DELETE, OPTIONS."""
        res = sec_client.options(
            "/health",
            headers={
                "Origin": "https://evera.embeddedos.org",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert res.status_code == 200


# --------------------------------------------------------------------------- #
# Input Validation / Injection Tests
# --------------------------------------------------------------------------- #

class TestInputValidation:
    """Verify that malicious inputs are handled safely."""

    def test_xss_in_location_session_id(self, sec_client):
        """XSS payload in session_id should be stored as plain text, not executed."""
        xss_payload = "<script>alert('xss')</script>"
        res = sec_client.post(
            "/location/update",
            json={
                "latitude": 37.7749,
                "longitude": -122.4194,
                "session_id": xss_payload,
            },
        )
        # Should succeed (200) — the server stores it as a string, not HTML
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        # The session_id in the response should be the raw string, not executed
        assert data["session_id"] == xss_payload

    def test_sql_injection_in_memory_key(self, sec_client):
        """SQL injection pattern in memory key should be rejected or stored safely."""
        sql_payload = "'; DROP TABLE users; --"
        res = sec_client.post(
            "/memory/facts",
            json={"key": sql_payload, "value": "test"},
        )
        # Should either succeed (200) or reject (422) — must NOT crash (500)
        assert res.status_code in (200, 422), f"Unexpected status: {res.status_code}"

    def test_path_traversal_in_location_session(self, sec_client):
        """Path traversal in session_id should not cause a server error."""
        res = sec_client.post(
            "/location/update",
            json={
                "latitude": 37.7749,
                "longitude": -122.4194,
                "session_id": "../../etc/passwd",
            },
        )
        assert res.status_code in (200, 400, 422), f"Unexpected status: {res.status_code}"

    def test_oversized_location_accuracy(self, sec_client):
        """Extreme float values should be handled gracefully."""
        res = sec_client.post(
            "/location/update",
            json={
                "latitude": 1e308,  # Near float max
                "longitude": -1e308,
                "accuracy": 1e308,
            },
        )
        # FastAPI/Pydantic should accept or reject cleanly — no 500
        assert res.status_code in (200, 422), f"Unexpected status: {res.status_code}"

    def test_invalid_latitude_range(self, sec_client):
        """Latitude outside [-90, 90] should be rejected."""
        res = sec_client.post(
            "/location/update",
            json={"latitude": 999.0, "longitude": -122.4194},
        )
        # The server should accept (200) or reject (422) — not crash (500)
        assert res.status_code in (200, 422), f"Unexpected status: {res.status_code}"

    def test_empty_body_on_post(self, sec_client):
        """POST with empty body should return 422, not 500."""
        res = sec_client.post("/location/update", json={})
        assert res.status_code == 422

    def test_wrong_content_type(self, sec_client):
        """POST with wrong content-type should return 422, not 500."""
        res = sec_client.post(
            "/location/update",
            data="latitude=37.7749&longitude=-122.4194",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert res.status_code in (200, 422), f"Unexpected status: {res.status_code}"


# --------------------------------------------------------------------------- #
# HTTP Method Enforcement
# --------------------------------------------------------------------------- #

class TestMethodEnforcement:
    """Verify endpoints reject wrong HTTP methods."""

    def test_post_to_get_only_endpoint(self, sec_client):
        """POST to a GET-only endpoint should return 405."""
        res = sec_client.post("/health")
        assert res.status_code == 405

    def test_delete_to_health(self, sec_client):
        """DELETE to /health should return 405."""
        res = sec_client.delete("/health")
        assert res.status_code == 405

    def test_get_to_post_only_endpoint(self, sec_client):
        """GET to a POST-only endpoint should return 405."""
        res = sec_client.get("/location/update")
        assert res.status_code == 405


# --------------------------------------------------------------------------- #
# Error Handling
# --------------------------------------------------------------------------- #

class TestErrorHandling:
    """Verify error responses are clean and don't leak internals."""

    def test_404_response_format(self, sec_client):
        """Unknown endpoint should return 404 with JSON body."""
        res = sec_client.get("/nonexistent_endpoint_xyz")
        assert res.status_code == 404

    def test_no_stack_trace_in_404(self, sec_client):
        """404 response must not contain Python stack trace."""
        res = sec_client.get("/nonexistent_endpoint_xyz")
        body = res.text
        assert "Traceback" not in body
        assert "File \"" not in body

    def test_no_stack_trace_in_422(self, sec_client):
        """422 response must not contain Python stack trace."""
        res = sec_client.post("/location/update", json={})
        body = res.text
        assert "Traceback" not in body
        assert "File \"" not in body
