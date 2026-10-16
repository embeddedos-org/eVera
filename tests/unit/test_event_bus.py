"""Unit tests for the async EventBus (issue #46 coverage drive).

Covers vera/events/bus.py — the inter-component event backbone,
previously exercised only by an archived tests_backup module that
CI does not run. Pins the dispatch contract: subscribers receive
only their event types, a raising callback never stops dispatch
to the others, unsubscribe is identity-based, the event log is
bounded and ordered, and publish_sync works from non-async code.
"""

from __future__ import annotations

import asyncio

import pytest

from vera.events.bus import MAX_EVENT_LOG, EventBus, EventType, emit_pipeline_event


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


async def _collect(bus: EventBus, received: list, event_type: EventType) -> None:
    async def _cb(et, data):
        received.append((et, data))

    bus.subscribe(event_type, _cb)


class TestSubscribePublish:
    async def test_subscriber_receives_published_event(self, bus):
        received = []
        await _collect(bus, received, EventType.SPEECH_START)
        await bus.start()
        try:
            await bus.publish(EventType.SPEECH_START, {"text": "hi"})
            await asyncio.sleep(0.25)
        finally:
            await bus.stop()
        assert received == [(EventType.SPEECH_START, {"text": "hi"})]

    async def test_subscriber_only_gets_its_event_type(self, bus):
        received = []
        await _collect(bus, received, EventType.SPEECH_START)
        await bus.start()
        try:
            await bus.publish(EventType.TTS_DONE, {})
            await bus.publish(EventType.SPEECH_START, {})
            await asyncio.sleep(0.25)
        finally:
            await bus.stop()
        assert [et for et, _ in received] == [EventType.SPEECH_START]

    async def test_publish_defaults_data_to_empty_dict(self, bus):
        received = []
        await _collect(bus, received, EventType.ERROR)
        await bus.start()
        try:
            await bus.publish(EventType.ERROR)
            await asyncio.sleep(0.25)
        finally:
            await bus.stop()
        assert received == [(EventType.ERROR, {})]

    async def test_raising_callback_does_not_stop_dispatch(self, bus):
        received = []

        async def _bad(et, data):
            raise RuntimeError("boom")

        async def _good(et, data):
            received.append(data)

        bus.subscribe(EventType.AGENT_DONE, _bad)
        bus.subscribe(EventType.AGENT_DONE, _good)
        await bus.start()
        try:
            await bus.publish(EventType.AGENT_DONE, {"n": 1})
            await bus.publish(EventType.AGENT_DONE, {"n": 2})
            await asyncio.sleep(0.3)
        finally:
            await bus.stop()
        assert received == [{"n": 1}, {"n": 2}]


class TestUnsubscribe:
    async def test_unsubscribe_stops_delivery(self, bus):
        received = []

        async def _cb(et, data):
            received.append(data)

        bus.subscribe(EventType.MEMORY_UPDATE, _cb)
        bus.unsubscribe(EventType.MEMORY_UPDATE, _cb)
        await bus.start()
        try:
            await bus.publish(EventType.MEMORY_UPDATE, {"x": 1})
            await asyncio.sleep(0.25)
        finally:
            await bus.stop()
        assert received == []

    def test_unsubscribe_unknown_event_type_is_a_noop(self, bus):
        async def _cb(et, data):
            pass

        bus.unsubscribe(EventType.WAKE_WORD_DETECTED, _cb)  # never subscribed


class TestEventLog:
    async def test_log_records_events_in_order(self, bus):
        await bus.start()
        try:
            for i in range(3):
                await bus.publish(EventType.SESSION_STARTED, {"i": i})
            await asyncio.sleep(0.3)
        finally:
            await bus.stop()
        events = bus.get_recent_events()
        assert [e["data"]["i"] for e in events] == [0, 1, 2]
        assert all(e["type"] == "session_started" for e in events)
        assert all("timestamp" in e for e in events)

    async def test_get_recent_events_limit_returns_the_tail(self, bus):
        await bus.start()
        try:
            for i in range(5):
                await bus.publish(EventType.SESSION_ENDED, {"i": i})
            await asyncio.sleep(0.3)
        finally:
            await bus.stop()
        tail = bus.get_recent_events(limit=2)
        assert [e["data"]["i"] for e in tail] == [3, 4]

    async def test_log_is_bounded(self, bus):
        await bus.start()
        try:
            for i in range(MAX_EVENT_LOG + 5):
                await bus.publish(EventType.TTS_START, {"i": i})
            await asyncio.sleep(0.5)
        finally:
            await bus.stop()
        events = bus.get_recent_events(limit=MAX_EVENT_LOG + 10)
        assert len(events) == MAX_EVENT_LOG
        assert events[-1]["data"]["i"] == MAX_EVENT_LOG + 4


class TestPublishSyncAndPipeline:
    async def test_publish_sync_from_async_context(self, bus):
        received = []
        await _collect(bus, received, EventType.TTS_INTERRUPT)
        await bus.start()
        try:
            bus.publish_sync(EventType.TTS_INTERRUPT, {"why": "barge-in"})
            await asyncio.sleep(0.25)
        finally:
            await bus.stop()
        assert received == [(EventType.TTS_INTERRUPT, {"why": "barge-in"})]

    def test_publish_sync_without_a_running_loop_queues(self, bus):
        bus.publish_sync(EventType.SPEECH_END, {"final": True})
        assert bus._queue.qsize() == 1

    async def test_emit_pipeline_event_reaches_the_status_queue(self):
        import vera.events.bus as bus_module

        while not bus_module._agent_status_queue.empty():
            bus_module._agent_status_queue.get_nowait()
        await emit_pipeline_event("planner", "done", tokens=42)
        event = bus_module._agent_status_queue.get_nowait()
        assert event == {"type": "pipeline", "node": "planner", "status": "done", "tokens": 42}
