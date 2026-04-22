"""Tests for Feature 3: ElevatedScriptTool (admin operations)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_admin():
    from config import settings
    original = settings.safety.admin_enabled
    yield
    settings.safety.admin_enabled = original


class TestElevatedScriptTool:
    @pytest.mark.asyncio
    async def test_disabled_by_default(self):
        from config import settings
        settings.safety.admin_enabled = False
        from vera.brain.agents.operator import ElevatedScriptTool
        tool = ElevatedScriptTool()
        result = await tool.execute(command="whoami")
        assert result["status"] == "denied"
        assert "disabled" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_hard_block(self):
        from config import settings
        settings.safety.admin_enabled = True
        from vera.brain.agents.operator import ElevatedScriptTool
        tool = ElevatedScriptTool()
        result = await tool.execute(command="rm -rf /")
        assert result["status"] == "denied"
        assert "hard-block" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_whitelist_rejection(self):
        from config import settings
        settings.safety.admin_enabled = True
        settings.safety.admin_allowed_commands = ["apt install *"]
        from vera.brain.agents.operator import ElevatedScriptTool
        tool = ElevatedScriptTool()
        result = await tool.execute(command="systemctl restart nginx")
        assert result["status"] == "denied"
        assert "not in allowed" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_whitelist_match(self):
        from config import settings
        settings.safety.admin_enabled = True
        settings.safety.admin_allowed_commands = ["whoami"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            settings.safety.admin_audit_log = f.name

        from vera.brain.agents.operator import ElevatedScriptTool
        tool = ElevatedScriptTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "root"
            mock_run.return_value.stderr = ""
            result = await tool.execute(command="whoami")
            assert result["status"] == "success"

        # Check audit log was written
        audit = Path(f.name).read_text()
        assert "whoami" in audit

    @pytest.mark.asyncio
    async def test_empty_command(self):
        from config import settings
        settings.safety.admin_enabled = True
        from vera.brain.agents.operator import ElevatedScriptTool
        tool = ElevatedScriptTool()
        result = await tool.execute(command="")
        assert result["status"] == "error"
