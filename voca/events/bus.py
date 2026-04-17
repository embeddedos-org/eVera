"""Async event bus for inter-component communication."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

MAX_EVENT_LOG = 100


class EventType(str, Enum):
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    TRANSCRIPT_READY = "transcript_ready"
    RESPONSE_READY = "response_ready"
    TTS_START = "tts_start"
    TTS_DONE = "tts_done"
    TTS_INTERRUPT = "tts_interrupt"
    AGENT_DISPATCH = "agent_dispatch"
    AGENT_DONE = "agent_done"
    MEMORY_UPDATE = "memory_update"
    ERROR = "error"


EventCallback = Callable[[EventType, dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """Lightweight async event bus using asyncio.Queue per subscriber."""

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[EventCallback]] = {}
        self._queue: asyncio.Queue[tuple[EventType, dict[str, Any]]] = asyncio.Queue()
        self._running = False
        self._dispatch_task: asyncio.Task | None = None
        self._event_log: deque[dict[str, Any]] = deque(maxlen=MAX_EVENT_LOG)

    def subscribe(self, event_type: EventType, callback: EventCallback) -> None:
        self._subscribers.setdefault(event_type, []).append(callback)
        logger.debug("Subscribed %s to %s", callback.__name__, event_type.value)

    def unsubscribe(self, event_type: EventType, callback: EventCallback) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                cb for cb in self._subscribers[event_type] if cb is not callback
            ]

    async def publish(self, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        data = data or {}
        logger.debug("Publishing event: %s", event_type.value)
        await self._queue.put((event_type, data))

    def publish_sync(self, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        """Non-async publish — schedules onto the running loop."""
        data = data or {}
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._queue.put_nowait, (event_type, data))
        except RuntimeError:
            self._queue.put_nowait((event_type, data))

    async def start(self) -> None:
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info("EventBus started")

    async def stop(self) -> None:
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        logger.info("EventBus stopped")

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                event_type, data = await asyncio.wait_for(self._queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            self._event_log.append({
                "type": event_type.value,
                "data": data,
                "timestamp": time.time(),
            })

            callbacks = self._subscribers.get(event_type, [])
            for cb in callbacks:
                try:
                    await cb(event_type, data)
                except Exception:
                    logger.exception("Error in event callback %s for %s", cb.__name__, event_type)

    def get_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent events from the log buffer."""
        events = list(self._event_log)
        return events[-limit:]
