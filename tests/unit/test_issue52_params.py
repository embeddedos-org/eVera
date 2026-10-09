"""
tests/unit/test_issue52_params.py — eVera issue #52: honour-or-remove per parameter.

SPDX-License-Identifier: MIT  Copyright (c) 2026 EmbeddedOS Foundation

Every parameter a tool declares must be honoured or removed from the tool's
declared parameters, and "rest" must route by intent.
"""
import asyncio
from unittest.mock import MagicMock


class TestScreenshotRegionRemoved:
    def test_region_not_declared(self):
        from vera.brain.agents.vision import ScreenCaptureTool

        tool = ScreenCaptureTool()
        assert "region" not in tool.parameters

    def test_schema_has_no_region(self):
        from vera.brain.agents.vision import ScreenCaptureTool

        schema = ScreenCaptureTool().to_openai_schema()
        props = schema["function"]["parameters"]["properties"]
        assert "region" not in props


class TestWeatherUnitsRemoved:
    def test_units_not_declared(self):
        from vera.brain.agents.www_agent import WeatherTool

        tool = WeatherTool()
        assert "units" not in tool.parameters
        assert set(tool.parameters) == {"location", "days"}


class TestSmartTradeActionHonoured:
    def test_invalid_action_rejected_before_estimate(self):
        from vera.brain.agents.brokers import SmartTradeTool

        result = asyncio.run(SmartTradeTool().execute(action="hold", symbol="AAPL", quantity=1))
        assert result["status"] == "error"
        assert "buy" in result["message"] and "sell" in result["message"]

    def test_missing_action_rejected(self):
        from vera.brain.agents.brokers import SmartTradeTool

        result = asyncio.run(SmartTradeTool().execute(symbol="AAPL", quantity=1))
        assert result["status"] == "error"

    def test_action_still_declared(self):
        from vera.brain.agents.brokers import SmartTradeTool

        assert "action" in SmartTradeTool().parameters


class TestOpenAISchemaRequired:
    def test_required_lists_declared_params(self):
        from vera.brain.agents.base import Tool

        tool = Tool(name="t", description="d", parameters={"a": {"type": "str"}, "b": {"type": "int"}})
        params = tool.to_openai_schema()["function"]["parameters"]
        assert sorted(params["required"]) == ["a", "b"]


class TestRestRoutesByIntent:
    def _router(self):
        from vera.brain.router import TierRouter

        return TierRouter(MagicMock())

    def test_bare_rest_is_wellness(self):
        decision = self._router().classify_by_keywords("I need some rest")
        assert decision.agent_name == "wellness"

    def test_rest_api_phrase_is_api(self):
        decision = self._router().classify_by_keywords("please call the rest api")
        assert decision.agent_name == "api"
        assert decision.intent == "rest_api"

    def test_restful_api_is_api(self):
        decision = self._router().classify_by_keywords("show me the restful api docs")
        assert decision.agent_name == "api"
