"""Tests for Feature 1: VisionMonitor."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_event_bus():
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


class TestVisionMonitor:
    def test_init_disabled(self, mock_event_bus):
        with patch("config.settings") as mock_settings:
            mock_settings.vision.monitor_enabled = False
            from vera.brain.agents.vision import VisionMonitor

            vm = VisionMonitor(event_bus=mock_event_bus)
            assert vm._task is None

    @pytest.mark.asyncio
    async def test_start_when_disabled(self, mock_event_bus):
        with patch("config.settings") as mock_settings:
            mock_settings.vision.monitor_enabled = False
            from vera.brain.agents.vision import VisionMonitor

            vm = VisionMonitor(event_bus=mock_event_bus)
            await vm.start()
            assert vm._task is None

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, mock_event_bus):
        with patch("config.settings") as mock_settings:
            mock_settings.vision.monitor_enabled = True
            mock_settings.vision.monitor_interval_s = 1
            mock_settings.vision.monitor_model = "test-model"
            mock_settings.vision.monitor_prompt = "test"
            from vera.brain.agents.vision import VisionMonitor

            vm = VisionMonitor(event_bus=mock_event_bus)

            with patch.object(vm, "_loop", new_callable=AsyncMock):
                await vm.start()
                assert vm._task is not None
                await vm.stop()
                assert vm._task is None

    def test_hash_debounce_attribute(self, mock_event_bus):
        with patch("config.settings") as mock_settings:
            mock_settings.vision.monitor_enabled = False
            from vera.brain.agents.vision import VisionMonitor

            vm = VisionMonitor(event_bus=mock_event_bus)
            assert vm._last_hash is None
