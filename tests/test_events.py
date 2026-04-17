"""Tests for the async event bus."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from voca.events.bus import EventBus, EventType


@pytest.mark.asyncio
async def test_publish_subscribe(event_bus: EventBus):
    callback = AsyncMock()
    event_bus.subscribe(EventType.TRANSCRIPT_READY, callback)

    await event_bus.start()
    await event_bus.publish(EventType.TRANSCRIPT_READY, {"text": "hello"})
    await asyncio.sleep(0.3)
    await event_bus.stop()

    callback.assert_called_once_with(EventType.TRANSCRIPT_READY, {"text": "hello"})


@pytest.mark.asyncio
async def test_unsubscribe(event_bus: EventBus):
    callback = AsyncMock()
    event_bus.subscribe(EventType.SPEECH_START, callback)
    event_bus.unsubscribe(EventType.SPEECH_START, callback)

    await event_bus.start()
    await event_bus.publish(EventType.SPEECH_START, {})
    await asyncio.sleep(0.3)
    await event_bus.stop()

    callback.assert_not_called()


@pytest.mark.asyncio
async def test_multiple_subscribers(event_bus: EventBus):
    cb1 = AsyncMock()
    cb2 = AsyncMock()
    event_bus.subscribe(EventType.RESPONSE_READY, cb1)
    event_bus.subscribe(EventType.RESPONSE_READY, cb2)

    await event_bus.start()
    await event_bus.publish(EventType.RESPONSE_READY, {"data": "test"})
    await asyncio.sleep(0.3)
    await event_bus.stop()

    cb1.assert_called_once()
    cb2.assert_called_once()


def test_event_types():
    expected = {
        "SPEECH_START", "SPEECH_END", "TRANSCRIPT_READY", "RESPONSE_READY",
        "TTS_START", "TTS_DONE", "TTS_INTERRUPT", "AGENT_DISPATCH",
        "AGENT_DONE", "MEMORY_UPDATE", "ERROR",
    }
    actual = {e.name for e in EventType}
    assert expected == actual
