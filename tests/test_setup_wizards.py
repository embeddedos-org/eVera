"""Tests for Features 7 & 8: Smart Home and Trading setup wizards."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSmartHomeSetupTool:
    @pytest.mark.asyncio
    async def test_check_no_config(self):
        from vera.brain.agents.home_controller import SmartHomeSetupTool

        tool = SmartHomeSetupTool()
        with patch("vera.utils.env_writer.read_env_value", return_value=None):
            result = await tool.execute(step="check")
            assert result["status"] == "needs_setup"

    @pytest.mark.asyncio
    async def test_check_with_valid_config(self):
        from vera.brain.agents.home_controller import SmartHomeSetupTool

        tool = SmartHomeSetupTool()

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch(
            "vera.utils.env_writer.read_env_value",
            side_effect=lambda k, **kw: {
                "VERA_HA_URL": "http://ha.local:8123",
                "VERA_HA_TOKEN": "test_token",
            }.get(k),
        ):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
                mock_client.return_value.__aexit__ = AsyncMock()
                result = await tool.execute(step="check")
                assert result.get("connected") is True or result["status"] in ("success", "partial")

    @pytest.mark.asyncio
    async def test_url_step_no_value(self):
        from vera.brain.agents.home_controller import SmartHomeSetupTool

        tool = SmartHomeSetupTool()
        result = await tool.execute(step="url", value="")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_token_step_no_url(self):
        from vera.brain.agents.home_controller import SmartHomeSetupTool

        tool = SmartHomeSetupTool()
        with patch("vera.utils.env_writer.read_env_value", return_value=None):
            result = await tool.execute(step="token", value="some_token")
            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_unknown_step(self):
        from vera.brain.agents.home_controller import SmartHomeSetupTool

        tool = SmartHomeSetupTool()
        result = await tool.execute(step="invalid")
        assert result["status"] == "error"


class TestTradingSetupTool:
    @pytest.mark.asyncio
    async def test_choose_step(self):
        from vera.brain.agents.brokers import TradingSetupTool

        tool = TradingSetupTool()
        with patch("vera.utils.env_writer.read_env_value", return_value=None):
            result = await tool.execute(step="choose")
            assert result["status"] == "choose"
            assert "alpaca" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_credentials_no_broker(self):
        from vera.brain.agents.brokers import TradingSetupTool

        tool = TradingSetupTool()
        result = await tool.execute(step="credentials", broker="")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_alpaca_no_keys(self):
        from vera.brain.agents.brokers import TradingSetupTool

        tool = TradingSetupTool()
        result = await tool.execute(step="credentials", broker="alpaca")
        assert result["status"] == "needs_input"

    @pytest.mark.asyncio
    async def test_ibkr_saves_config(self, tmp_path):
        from vera.brain.agents.brokers import TradingSetupTool

        tool = TradingSetupTool()
        env_file = tmp_path / ".env"
        with patch("vera.utils.env_writer.update_env_file") as mock_update:
            result = await tool.execute(
                step="credentials",
                broker="ibkr",
                host="127.0.0.1",
                port=7497,
                client_id=1,
            )
            assert result["status"] == "success"
            assert mock_update.call_count == 3  # host, port, client_id

    @pytest.mark.asyncio
    async def test_unknown_step(self):
        from vera.brain.agents.brokers import TradingSetupTool

        tool = TradingSetupTool()
        result = await tool.execute(step="invalid")
        assert result["status"] == "error"
