"""Tests for the FastAPI REST + WebSocket endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from vera.core import VeraResponse
from vera.providers.models import ModelTier


@pytest.fixture
def mock_brain():
    brain = MagicMock()
    brain.start = AsyncMock()
    brain.stop = AsyncMock()
    brain.process = AsyncMock(
        return_value=VeraResponse(
            response="Hello! How can I help?",
            agent="companion",
            tier=ModelTier.EXECUTOR,
            intent="greeting",
        )
    )
    brain.confirm_action = AsyncMock(
        return_value=VeraResponse(response="Confirmed.", agent="system", tier=ModelTier.REFLEX)
    )
    brain.get_status = MagicMock(return_value={"status": "running"})
    brain.memory_vault = MagicMock()
    brain.memory_vault.semantic.get_all.return_value = {"name": "Test User"}
    brain.memory_vault.remember_fact = MagicMock()
    return brain


@pytest.fixture
def app(mock_brain):
    from vera.app import create_app

    return create_app(mock_brain)


@pytest.mark.asyncio
async def test_health(app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_status(app, mock_brain):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"


@pytest.mark.asyncio
async def test_chat(app, mock_brain):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/chat", json={"transcript": "hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "Hello! How can I help?"
        assert data["agent"] == "companion"
        mock_brain.process.assert_called_once()


@pytest.mark.asyncio
async def test_get_memory_facts(app, mock_brain):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/memory/facts")
        assert resp.status_code == 200
        assert resp.json() == {"name": "Test User"}


@pytest.mark.asyncio
async def test_set_memory_fact(app, mock_brain):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/memory/facts", json={"key": "color", "value": "blue"})
        assert resp.status_code == 200
        assert resp.json() == {"key": "color", "value": "blue"}
        mock_brain.memory_vault.remember_fact.assert_called_once_with("color", "blue")
