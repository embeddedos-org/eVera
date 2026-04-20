"""Tests for LiveTrading plugin tools — all hit ImportError fallback paths."""

from __future__ import annotations

import pytest


# ── IBKR Tools ──────────────────────────────────────────────────

class TestIBKRConnect:
    @pytest.mark.asyncio
    async def test_import_error_path(self):
        from plugins.live_trading import IBKRConnectTool
        tool = IBKRConnectTool()
        result = await tool.execute()
        assert result["status"] == "error"
        assert "not found" in result["message"] or "not available" in result["message"] or "stocks_plugin" in result["message"]


class TestIBKRTrade:
    @pytest.mark.asyncio
    async def test_missing_params_validation(self):
        from plugins.live_trading import IBKRTradeTool
        tool = IBKRTradeTool()
        # Missing required params → ImportError or validation error
        result = await tool.execute()
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_import_error_path(self):
        from plugins.live_trading import IBKRTradeTool
        tool = IBKRTradeTool()
        result = await tool.execute(action="BUY", symbol="AAPL", quantity=10)
        assert result["status"] == "error"
        assert "not available" in result["message"] or "interactive_brokers" in result["message"]


class TestIBKRPortfolio:
    @pytest.mark.asyncio
    async def test_import_error_path(self):
        from plugins.live_trading import IBKRPortfolioTool
        tool = IBKRPortfolioTool()
        result = await tool.execute()
        assert result["status"] == "error"
        assert "not available" in result["message"] or "interactive_brokers" in result["message"]

    @pytest.mark.asyncio
    async def test_import_error_with_positions_detail(self):
        from plugins.live_trading import IBKRPortfolioTool
        tool = IBKRPortfolioTool()
        result = await tool.execute(detail="positions")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_import_error_with_pnl_detail(self):
        from plugins.live_trading import IBKRPortfolioTool
        tool = IBKRPortfolioTool()
        result = await tool.execute(detail="pnl")
        assert result["status"] == "error"


# ── TradeStation Tools ──────────────────────────────────────────

class TestTradeStationTrade:
    @pytest.mark.asyncio
    async def test_error_path(self):
        from plugins.live_trading import TradeStationTradeTool
        tool = TradeStationTradeTool()
        result = await tool.execute(action="BUY", symbol="MSFT", quantity=5)
        assert result["status"] == "error"
        assert "message" in result


class TestTradeStationAccount:
    @pytest.mark.asyncio
    async def test_import_error_path(self):
        from plugins.live_trading import TradeStationAccountTool
        tool = TradeStationAccountTool()
        result = await tool.execute()
        assert result["status"] == "error"
        assert "not available" in result["message"] or "tradestation" in result["message"]


# ── Schwab Tools ────────────────────────────────────────────────

class TestSchwabTrade:
    @pytest.mark.asyncio
    async def test_error_path(self):
        from plugins.live_trading import SchwabTradeTool
        tool = SchwabTradeTool()
        result = await tool.execute(action="BUY", symbol="GOOG", quantity=3)
        assert result["status"] == "error"
        assert "message" in result


class TestSchwabAccount:
    @pytest.mark.asyncio
    async def test_error_path(self):
        from plugins.live_trading import SchwabAccountTool
        tool = SchwabAccountTool()
        result = await tool.execute()
        assert result["status"] == "error"
        assert "message" in result


# ── AI Trading Tools ───────────────────────────────────────────

class TestAITradingDecision:
    @pytest.mark.asyncio
    async def test_import_error_path(self):
        from plugins.live_trading import AITradingDecisionTool
        tool = AITradingDecisionTool()
        result = await tool.execute(symbol="SPY")
        assert result["status"] == "error"
        assert "not available" in result["message"] or "shared/ml" in result["message"]

    @pytest.mark.asyncio
    async def test_import_error_performance_action(self):
        from plugins.live_trading import AITradingDecisionTool
        tool = AITradingDecisionTool()
        result = await tool.execute(symbol="SPY", action="performance")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_import_error_weights_action(self):
        from plugins.live_trading import AITradingDecisionTool
        tool = AITradingDecisionTool()
        result = await tool.execute(symbol="SPY", action="weights")
        assert result["status"] == "error"


# ── RunStrategy Tool ───────────────────────────────────────────

class TestRunStrategy:
    @pytest.mark.asyncio
    async def test_empty_strategy_returns_available_list(self):
        from plugins.live_trading import RunStrategyTool
        tool = RunStrategyTool()
        result = await tool.execute(strategy="")
        assert result["status"] == "info"
        assert "available_strategies" in result
        assert len(result["available_strategies"]) == 6
        assert "regime_trader" in result["available_strategies"]

    @pytest.mark.asyncio
    async def test_paper_mode_returns_info(self):
        from plugins.live_trading import RunStrategyTool
        tool = RunStrategyTool()
        result = await tool.execute(strategy="regime_trader", symbol="SPY", mode="paper")
        assert result["status"] == "info"
        assert "regime_trader" in result["message"]
        assert "paper" in result["message"]
        assert "command" in result

    @pytest.mark.asyncio
    async def test_backtest_mode_import_error(self):
        from plugins.live_trading import RunStrategyTool
        tool = RunStrategyTool()
        result = await tool.execute(strategy="dca_bot", symbol="AAPL", mode="backtest")
        assert result["status"] == "error"
        assert "not found" in result["message"] or "Strategy" in result["message"]


# ── RiskCheck Tool ──────────────────────────────────────────────

class TestRiskCheck:
    @pytest.mark.asyncio
    async def test_error_path(self):
        from plugins.live_trading import RiskCheckTool
        tool = RiskCheckTool()
        result = await tool.execute(symbol="NVDA", capital=50000)
        assert result["status"] == "error"
        assert "message" in result


# ── LiveTradingAgent ────────────────────────────────────────────

class TestLiveTradingAgent:
    def test_agent_has_ten_tools(self):
        from plugins.live_trading import LiveTradingAgent
        agent = LiveTradingAgent()
        assert len(agent.tools) == 10

    def test_agent_name(self):
        from plugins.live_trading import LiveTradingAgent
        agent = LiveTradingAgent()
        assert agent.name == "live_trader"

    def test_agent_has_offline_responses(self):
        from plugins.live_trading import LiveTradingAgent
        agent = LiveTradingAgent()
        assert len(agent.offline_responses) > 0

    def test_agent_tool_names(self):
        from plugins.live_trading import LiveTradingAgent
        agent = LiveTradingAgent()
        tool_names = [t.name for t in agent.tools]
        expected = [
            "ibkr_connect", "ibkr_trade", "ibkr_portfolio",
            "tradestation_trade", "tradestation_account",
            "schwab_trade", "schwab_account",
            "ai_trading_decision", "run_strategy", "risk_check",
        ]
        for name in expected:
            assert name in tool_names
