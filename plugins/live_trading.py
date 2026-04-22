"""eVera Trading Plugin — bridges stocks_plugin into eVera's agent system.

Connects eVera voice commands to live trading on IBKR, TradeStation,
Schwab/thinkorswim, and TradingView via the stocks_plugin framework.

Supports:
- Live trading (IBKR TWS API, TradeStation REST, Schwab API)
- TradingView webhook alerts
- Self-learning AI agent decisions
- Portfolio analytics & risk management
- Strategy backtesting

Drop this file in eVera's plugins/ directory to auto-register.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add stocks_plugin to Python path
STOCKS_PLUGIN_DIR = Path(__file__).resolve().parent.parent / "dev_platfrom" / "stocks_plugin"
if not STOCKS_PLUGIN_DIR.exists():
    # Try relative to eVera project root
    STOCKS_PLUGIN_DIR = Path(__file__).resolve().parent.parent.parent / "stocks_plugin"
if STOCKS_PLUGIN_DIR.exists() and str(STOCKS_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(STOCKS_PLUGIN_DIR))

from vera.brain.agents.base import BaseAgent, Tool  # noqa: E402
from vera.providers.models import ModelTier  # noqa: E402

logger = logging.getLogger(__name__)


# ─── IBKR Tools ─────────────────────────────────────────────

class IBKRConnectTool(Tool):
    def __init__(self):
        super().__init__(
            name="ibkr_connect",
            description="Connect to Interactive Brokers TWS/Gateway",
            parameters={
                "host": {"type": "str", "description": "TWS host (default: 127.0.0.1)"},
                "port": {"type": "int", "description": "TWS port (7497=paper, 7496=live)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            from interactive_brokers.utils.ib_connection import IBInsyncConnection
            host = kwargs.get("host", "127.0.0.1")
            port = int(kwargs.get("port", 7497))
            conn = IBInsyncConnection(host=host, port=port)
            conn.connect()
            return {"status": "success", "message": f"Connected to IBKR at {host}:{port}", "paper": port == 7497}
        except ImportError:
            return {"status": "error", "message": "stocks_plugin not found. Ensure it's at ../stocks_plugin/"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class IBKRTradeTool(Tool):
    def __init__(self):
        super().__init__(
            name="ibkr_trade",
            description="Place a trade on Interactive Brokers (requires confirmation)",
            parameters={
                "action": {"type": "str", "description": "BUY or SELL"},
                "symbol": {"type": "str", "description": "Stock symbol (e.g. AAPL)"},
                "quantity": {"type": "int", "description": "Number of shares"},
                "order_type": {"type": "str", "description": "MARKET, LIMIT, STOP (default: MARKET)"},
                "limit_price": {"type": "float", "description": "Limit price (for LIMIT orders)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            from interactive_brokers.utils.ib_connection import IBInsyncConnection
            from interactive_brokers.utils.order_manager import OrderManager

            action = kwargs.get("action", "").upper()
            symbol = kwargs.get("symbol", "").upper()
            quantity = int(kwargs.get("quantity", 0))
            order_type = kwargs.get("order_type", "MARKET").upper()

            if not action or not symbol or quantity <= 0:
                return {"status": "error", "message": "action, symbol, and quantity > 0 required"}

            conn = IBInsyncConnection()
            order_mgr = OrderManager(conn)

            result = order_mgr.place_order(
                symbol=symbol, action=action, quantity=quantity,
                order_type=order_type,
                limit_price=kwargs.get("limit_price"),
            )
            return {"status": "success", "order": result, "broker": "IBKR"}
        except ImportError:
            return {"status": "error", "message": "stocks_plugin/interactive_brokers not available"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class IBKRPortfolioTool(Tool):
    def __init__(self):
        super().__init__(
            name="ibkr_portfolio",
            description="View IBKR portfolio positions, P&L, and account info",
            parameters={
                "detail": {"type": "str", "description": "Level: summary, positions, pnl (default: summary)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            from interactive_brokers.analytics.portfolio_tracker import PortfolioTracker
            from interactive_brokers.utils.ib_connection import IBInsyncConnection

            conn = IBInsyncConnection()
            tracker = PortfolioTracker(conn)
            detail = kwargs.get("detail", "summary")

            if detail == "positions":
                return {"status": "success", "positions": tracker.get_positions()}
            elif detail == "pnl":
                return {"status": "success", "pnl": tracker.get_pnl()}
            else:
                return {"status": "success", "account": tracker.get_summary()}
        except ImportError:
            return {"status": "error", "message": "stocks_plugin/interactive_brokers not available"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ─── TradeStation Tools ─────────────────────────────────────

class TradeStationTradeTool(Tool):
    def __init__(self):
        super().__init__(
            name="tradestation_trade",
            description="Place a trade on TradeStation via REST API",
            parameters={
                "action": {"type": "str", "description": "BUY or SELL"},
                "symbol": {"type": "str", "description": "Stock symbol"},
                "quantity": {"type": "int", "description": "Number of shares"},
                "order_type": {"type": "str", "description": "Market, Limit, StopMarket"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            from tradestation.api.order_router import TradeStationOrderRouter
            router = TradeStationOrderRouter()
            result = router.place_order(
                symbol=kwargs.get("symbol", "").upper(),
                action=kwargs.get("action", "").upper(),
                quantity=int(kwargs.get("quantity", 0)),
                order_type=kwargs.get("order_type", "Market"),
            )
            return {"status": "success", "order": result, "broker": "TradeStation"}
        except ImportError:
            return {"status": "error", "message": "stocks_plugin/tradestation not available"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class TradeStationAccountTool(Tool):
    def __init__(self):
        super().__init__(
            name="tradestation_account",
            description="View TradeStation account balances and positions",
            parameters={},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            from tradestation.api.account_monitor import TradeStationAccountMonitor
            monitor = TradeStationAccountMonitor()
            return {"status": "success", "account": monitor.get_summary()}
        except ImportError:
            return {"status": "error", "message": "stocks_plugin/tradestation not available"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ─── Schwab/thinkorswim Tools ───────────────────────────────

class SchwabTradeTool(Tool):
    def __init__(self):
        super().__init__(
            name="schwab_trade",
            description="Place a trade on Charles Schwab via API (thinkorswim)",
            parameters={
                "action": {"type": "str", "description": "BUY or SELL"},
                "symbol": {"type": "str", "description": "Stock symbol"},
                "quantity": {"type": "int", "description": "Number of shares"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            from thinkorswim.api.schwab_client import SchwabClient
            client = SchwabClient()
            result = client.place_order(
                symbol=kwargs.get("symbol", "").upper(),
                action=kwargs.get("action", "").upper(),
                quantity=int(kwargs.get("quantity", 0)),
            )
            return {"status": "success", "order": result, "broker": "Schwab"}
        except ImportError:
            return {"status": "error", "message": "stocks_plugin/thinkorswim not available"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class SchwabAccountTool(Tool):
    def __init__(self):
        super().__init__(
            name="schwab_account",
            description="View Schwab account info, positions, and balances",
            parameters={},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            from thinkorswim.api.schwab_client import SchwabClient
            client = SchwabClient()
            return {"status": "success", "account": client.get_account()}
        except ImportError:
            return {"status": "error", "message": "stocks_plugin/thinkorswim not available"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ─── AI Trading Tools ───────────────────────────────────────

class AITradingDecisionTool(Tool):
    def __init__(self):
        super().__init__(
            name="ai_trading_decision",
            description="Get AI self-learning agent's trading decision for a symbol",
            parameters={
                "symbol": {"type": "str", "description": "Stock symbol to analyze"},
                "action": {"type": "str", "description": "decide, performance, weights (default: decide)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            from shared.ml.self_learning_agent import SelfLearningAgent
            agent = SelfLearningAgent()
            symbol = kwargs.get("symbol", "SPY").upper()
            action = kwargs.get("action", "decide")

            if action == "performance":
                return {"status": "success", "performance": agent.get_performance(lookback_days=30)}
            elif action == "weights":
                return {"status": "success", "weights": agent.get_weight_summary()}
            else:
                decision = agent.decide(symbol=symbol)
                return {
                    "status": "success",
                    "symbol": symbol,
                    "action": decision.get("action", "HOLD"),
                    "confidence": decision.get("confidence", 0),
                    "reasoning": decision.get("reasoning", ""),
                    "regime": decision.get("regime", "unknown"),
                }
        except ImportError:
            return {"status": "error", "message": "stocks_plugin/shared/ml not available"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class RunStrategyTool(Tool):
    def __init__(self):
        super().__init__(
            name="run_strategy",
            description="Run/backtest a trading strategy from stocks_plugin",
            parameters={
                "strategy": {"type": "str", "description": "Strategy: regime_trader, dca_bot, pairs_trading, momentum_rebalancer, options_wheel, self_learning"},
                "symbol": {"type": "str", "description": "Stock symbol(s), comma-separated"},
                "mode": {"type": "str", "description": "Mode: live, paper, backtest (default: paper)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        strategy = kwargs.get("strategy", "")
        symbol = kwargs.get("symbol", "SPY")
        mode = kwargs.get("mode", "paper")

        if not strategy:
            available = ["regime_trader", "dca_bot", "pairs_trading", "momentum_rebalancer", "options_wheel", "self_learning"]
            return {"status": "info", "available_strategies": available, "message": "Specify a strategy name"}

        try:
            if mode == "backtest":
                from strategies.runner import run_backtest
                result = run_backtest(strategy=strategy, symbols=symbol.split(","))
                return {"status": "success", "backtest": result}
            else:
                return {
                    "status": "info",
                    "message": f"Strategy '{strategy}' ready for {mode} mode on {symbol}. "
                               f"Use ibkr_connect first, then run_strategy with mode={mode}.",
                    "command": f"python -m strategies.runner {mode} --strategy {strategy} --symbols {symbol}",
                }
        except ImportError as e:
            return {"status": "error", "message": f"Strategy module not found: {e}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class RiskCheckTool(Tool):
    def __init__(self):
        super().__init__(
            name="risk_check",
            description="Check risk metrics before trading — position sizing, drawdown, daily limits",
            parameters={
                "symbol": {"type": "str", "description": "Symbol to check"},
                "capital": {"type": "float", "description": "Available capital"},
                "risk_per_trade": {"type": "float", "description": "Risk per trade as % (default: 1.0)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            from shared.risk_manager import RiskManager
            rm = RiskManager()
            symbol = kwargs.get("symbol", "SPY")
            capital = float(kwargs.get("capital", 100000))
            risk_pct = float(kwargs.get("risk_per_trade", 1.0))

            check = rm.pre_trade_check(symbol=symbol, capital=capital, risk_pct=risk_pct)
            return {"status": "success", "risk_check": check}
        except ImportError:
            return {"status": "error", "message": "stocks_plugin/shared/risk_manager not available"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ─── Plugin Agent ────────────────────────────────────────────

class LiveTradingAgent(BaseAgent):
    """Live trading agent — bridges eVera to IBKR, TradeStation, Schwab, and TradingView.

    Connects to stocks_plugin for real broker APIs, AI trading decisions,
    portfolio analytics, and risk management.

    Voice commands:
    - "Connect to IBKR paper trading"
    - "Buy 10 shares of AAPL on Interactive Brokers"
    - "What does the AI think about Tesla?"
    - "Show my IBKR portfolio"
    - "Run the regime trader strategy on SPY"
    - "Check risk for buying NVDA with $50k"
    """

    name = "live_trader"
    description = "Live trading on IBKR, TradeStation, Schwab/thinkorswim with AI strategies and risk management"
    tier = ModelTier.STRATEGIST
    system_prompt = (
        "You are a professional trading assistant with access to live broker APIs. "
        "You can connect to Interactive Brokers, TradeStation, and Charles Schwab for "
        "real and paper trading. You have access to AI self-learning trading models, "
        "risk management tools, and multiple strategy bots. "
        "CRITICAL RULES:\n"
        "1. ALWAYS confirm with the user before placing ANY real trade\n"
        "2. Default to PAPER trading (port 7497) unless explicitly told to use live\n"
        "3. ALWAYS run risk_check before suggesting a trade\n"
        "4. Report position sizing recommendations from the risk manager\n"
        "5. Never place trades exceeding the user's stated risk tolerance\n"
        "When the user asks about trading, first check which broker they want to use. "
        "For AI decisions, use ai_trading_decision. For risk checks, use risk_check."
    )

    offline_responses = {
        "trade": "📈 I can help you trade! Which broker? IBKR, TradeStation, or Schwab?",
        "buy": "📈 I'll set up that trade! Let me check risk first.",
        "sell": "📉 I'll prepare that sell order. Checking positions...",
        "portfolio": "💼 Let me pull up your portfolio!",
        "strategy": "🤖 I'll run that strategy for you!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            IBKRConnectTool(),
            IBKRTradeTool(),
            IBKRPortfolioTool(),
            TradeStationTradeTool(),
            TradeStationAccountTool(),
            SchwabTradeTool(),
            SchwabAccountTool(),
            AITradingDecisionTool(),
            RunStrategyTool(),
            RiskCheckTool(),
        ]
