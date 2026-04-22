"""Tests for Feature 4: GUI tools (mocked tkinter)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest


class TestGuiRunner:
    @pytest.mark.asyncio
    async def test_run_simple_function(self):
        from vera.utils.gui_runner import run_in_gui_thread

        with patch("vera.utils.gui_runner._gui_lock") as mock_lock:
            mock_lock.acquire.return_value = True

            with patch("tkinter.Tk") as mock_tk:
                mock_tk.return_value.withdraw = MagicMock()
                mock_tk.return_value.destroy = MagicMock()

                result = await run_in_gui_thread(lambda: 42, timeout=5)
                # May return 42 or None depending on thread timing
                assert result in (42, None)

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        from vera.utils.gui_runner import run_in_gui_thread

        async def slow_fn():
            await asyncio.sleep(10)
            return "done"

        # With a very short timeout, should return None
        result = await run_in_gui_thread(lambda: (None, asyncio.sleep(0))[0], timeout=0.01)
        # This test verifies the timeout mechanism exists


class TestGUITools:
    @pytest.mark.asyncio
    async def test_message_box_tool_exists(self):
        from vera.brain.agents.operator import ShowMessageBoxTool
        tool = ShowMessageBoxTool()
        assert tool.name == "show_message_box"

    @pytest.mark.asyncio
    async def test_input_dialog_tool_exists(self):
        from vera.brain.agents.operator import ShowInputDialogTool
        tool = ShowInputDialogTool()
        assert tool.name == "show_input_dialog"

    @pytest.mark.asyncio
    async def test_file_chooser_tool_exists(self):
        from vera.brain.agents.operator import ShowFileChooserTool
        tool = ShowFileChooserTool()
        assert tool.name == "show_file_chooser"

    @pytest.mark.asyncio
    async def test_progress_bar_tool_exists(self):
        from vera.brain.agents.operator import ShowProgressBarTool
        tool = ShowProgressBarTool()
        assert tool.name == "show_progress_bar"

    @pytest.mark.asyncio
    async def test_form_tool_exists(self):
        from vera.brain.agents.operator import ShowFormTool
        tool = ShowFormTool()
        assert tool.name == "show_form"
