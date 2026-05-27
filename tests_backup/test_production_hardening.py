"""Production hardening test suite.

Tests new features: GPS location, i18n support, server info, CORS origins,
and rate limiting.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from config import settings
from vera.app import create_app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    app = create_app()
    return TestClient(app)


def test_server_info_endpoint(client):
    """Test the /info endpoint returns correct server metadata."""
    res = client.get("/info")
    assert res.status_code == 200
    data = res.json()
    assert "version" in data
    assert "eVera API" in data["name"]


def test_i18n_languages_endpoint(client):
    """Test /i18n/languages endpoint returns supported languages."""
    res = client.get("/i18n/languages")
    assert res.status_code == 200
    data = res.json()
    assert "en" in data
    assert "es" in data
    assert "ar" in data


def test_i18n_strings_endpoint(client):
    """Test /i18n/strings/{lang} returns translated strings."""
    # English
    res = client.get("/i18n/strings/en")
    assert res.status_code == 200
    data = res.json()
    assert "strings" in data
    assert "greeting" in data["strings"]

    # Spanish
    res = client.get("/i18n/strings/es")
    assert res.status_code == 200
    data = res.json()
    assert data["strings"]["greeting"] != "Hey there! I'm Vera, your AI buddy."


def test_gps_location_lifecycle(client):
    """Test updating and retrieving GPS location."""
    # 1. Update location
    loc_data = {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "accuracy": 10.0,
        "altitude": 15.0,
        "session_id": "test_session",
    }
    res = client.post("/location/update", json=loc_data)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # 2. Get current location (should match what we just set)
    res = client.get("/location/current")
    assert res.status_code == 200
    data = res.json()
    assert data["latitude"] == 37.7749
    assert data["longitude"] == -122.4194


def test_cors_headers(client):
    """Test that CORS headers are correctly configured."""
    res = client.options(
        "/info",
        headers={
            "Origin": "https://evera.embeddedos.org",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "https://evera.embeddedos.org"
