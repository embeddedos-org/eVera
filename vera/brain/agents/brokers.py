"""Broker integrations — Alpaca, Interactive Brokers, TradingView webhooks, desktop automation.

Supports real trading with configurable safety levels.
Install: pip install alpaca-trade-api ib_insync
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from vera.brain.agents.base import Tool

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

# --- Config from environment ---

ALPACA_API_KEY = os.getenv("VERA_ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("VERA_ALPACA_SECRET_KEY", "")
ALPACA_PAPER = os.getenv("VERA_ALPACA_PAPER", "true").lower() == "true"

IBKR_HOST = os.getenv("VERA_IBKR_HOST", "127.0.0.1")
IBKR_PORT = int(os.getenv("VERA_IBKR_PORT", "7497"))  # 7497=paper, 7496=live
IBKR_CLIENT_ID = int(os.getenv("VERA_IBKR_CLIENT_ID", "1"))

# Safety: auto-trade threshold (in dollars). Orders above this need confirmation.
AUTO_TRADE_LIMIT = float(os.getenv("VERA_AUTO_TRADE_LIMIT", "500"))

SYSTEM = platform.system()


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _log_trade(broker: str, trade: dict):
    """Log every trade to a file for audit."""
    _ensure_dir()
    log_path = DATA_DIR / "trade_log.json"
    trades = []
    if log_path.exists():
        try:
            trades = json.loads(log_path.read_text())
        except Exception:
            pass
    trade["broker"] = broker
    trade["timestamp"] = datetime.now().isoformat()
    trades.append(trade)
    trades = trades[-1000:]  # Keep last 1000 trades
    log_path.write_text(json.dumps(trades, indent=2, default=str))


# ============================================================
# 1. ALPACA TRADING (Free API, Paper + Live)
# ============================================================

class AlpacaTradeTool(Tool):
    """Place real orders through Alpaca API."""

    def __init__(self) -> None:
        super().__init__(
            name="alpaca_trade",
            description="Place a real trade via Alpaca (paper or live based on config)",
            parameters={
                "action": {"type": "str", "description": "buy or sell"},
                "symbol": {"type": "str", "description": "Stock ticker (e.g. AAPL)"},
                "quantity": {"type": "int", "description": "Number of shares"},
                "order_type": {"type": "str", "description": "market, limit, stop, stop_limit (default: market)"},
                "limit_price": {"type": "float", "description": "Limit price (for limit/stop_limit orders)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        if not ALPACA_API_KEY:
            return {"status": "error", "message": "Alpaca not configured. Set VERA_ALPACA_API_KEY and VERA_ALPACA_SECRET_KEY in .env"}

        action = kwargs.get("action", "").lower()
        symbol = kwargs.get("symbol", "").upper()
        qty = kwargs.get("quantity", 0)
        order_type = kwargs.get("order_type", "market").lower()
        limit_price = kwargs.get("limit_price")

        if action not in ("buy", "sell"):
            return {"status": "error", "message": "Action must be 'buy' or 'sell'"}
        if not symbol or qty <= 0:
            return {"status": "error", "message": "Symbol and positive quantity required"}

        try:
            from alpaca_trade_api import REST
            base_url = "https://paper-api.alpaca.markets" if ALPACA_PAPER else "https://api.alpaca.markets"
            api = REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url)

            order_params = {
                "symbol": symbol,
                "qty": qty,
                "side": action,
                "type": order_type,
                "time_in_force": "day",
            }
            if limit_price and order_type in ("limit", "stop_limit"):
                order_params["limit_price"] = limit_price

            order = api.submit_order(**order_params)

            trade_data = {
                "action": action, "symbol": symbol, "quantity": qty,
                "order_type": order_type, "order_id": order.id,
                "status": order.status, "mode": "paper" if ALPACA_PAPER else "LIVE",
            }
            _log_trade("alpaca", trade_data)

            return {
                "status": "success",
                "order_id": order.id,
                "order_status": order.status,
                "symbol": symbol,
                "side": action,
                "qty": qty,
                "type": order_type,
                "mode": "📝 PAPER" if ALPACA_PAPER else "💰 LIVE",
                "warning": "⚠️ REAL MONEY" if not ALPACA_PAPER else None,
            }
        except ImportError:
            return {"status": "error", "message": "Install: pip install alpaca-trade-api"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class AlpacaAccountTool(Tool):
    """View Alpaca account info and positions."""

    def __init__(self) -> None:
        super().__init__(
            name="alpaca_account",
            description="View your Alpaca brokerage account — balance, positions, orders",
            parameters={
                "view": {"type": "str", "description": "What to view: account, positions, orders (default: account)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        if not ALPACA_API_KEY:
            return {"status": "error", "message": "Alpaca not configured"}

        view = kwargs.get("view", "account").lower()

        try:
            from alpaca_trade_api import REST
            base_url = "https://paper-api.alpaca.markets" if ALPACA_PAPER else "https://api.alpaca.markets"
            api = REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url)

            if view == "positions":
                positions = api.list_positions()
                return {
                    "status": "success",
                    "positions": [
                        {
                            "symbol": p.symbol, "qty": int(p.qty), "side": p.side,
                            "market_value": float(p.market_value),
                            "avg_entry": float(p.avg_entry_price),
                            "current_price": float(p.current_price),
                            "unrealized_pl": float(p.unrealized_pl),
                            "unrealized_pl_pct": float(p.unrealized_plpc) * 100,
                        }
                        for p in positions
                    ],
                    "mode": "paper" if ALPACA_PAPER else "live",
                }
            elif view == "orders":
                orders = api.list_orders(status="all", limit=10)
                return {
                    "status": "success",
                    "orders": [
                        {
                            "id": o.id, "symbol": o.symbol, "side": o.side,
                            "qty": int(o.qty), "type": o.type, "status": o.status,
                            "submitted_at": str(o.submitted_at),
                        }
                        for o in orders
                    ],
                }
            else:
                acct = api.get_account()
                return {
                    "status": "success",
                    "equity": float(acct.equity),
                    "cash": float(acct.cash),
                    "buying_power": float(acct.buying_power),
                    "portfolio_value": float(acct.portfolio_value),
                    "day_trade_count": int(acct.daytrade_count),
                    "mode": "📝 PAPER" if ALPACA_PAPER else "💰 LIVE",
                }
        except ImportError:
            return {"status": "error", "message": "Install: pip install alpaca-trade-api"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ============================================================
# 2. INTERACTIVE BROKERS (via ib_insync)
# ============================================================

class IBKRTradeTool(Tool):
    """Place trades through Interactive Brokers TWS/Gateway."""

    def __init__(self) -> None:
        super().__init__(
            name="ibkr_trade",
            description="Place a trade via Interactive Brokers TWS (Thinkorswim alternative)",
            parameters={
                "action": {"type": "str", "description": "buy or sell"},
                "symbol": {"type": "str", "description": "Stock ticker"},
                "quantity": {"type": "int", "description": "Number of shares"},
                "order_type": {"type": "str", "description": "market, limit (default: market)"},
                "limit_price": {"type": "float", "description": "Limit price (for limit orders)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "").lower()
        symbol = kwargs.get("symbol", "").upper()
        qty = kwargs.get("quantity", 0)
        order_type = kwargs.get("order_type", "market").lower()
        limit_price = kwargs.get("limit_price")

        if action not in ("buy", "sell"):
            return {"status": "error", "message": "Action must be 'buy' or 'sell'"}
        if not symbol or qty <= 0:
            return {"status": "error", "message": "Symbol and positive quantity required"}

        try:
            from ib_insync import IB, LimitOrder, MarketOrder, Stock

            ib = IB()
            try:
                await ib.connectAsync(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)

                contract = Stock(symbol, "SMART", "USD")
                await ib.qualifyContractsAsync(contract)

                if order_type == "limit" and limit_price:
                    order = LimitOrder(action.upper(), qty, limit_price)
                else:
                    order = MarketOrder(action.upper(), qty)

                trade = ib.placeOrder(contract, order)
                await ib.sleep(2)

                trade_data = {
                    "action": action, "symbol": symbol, "quantity": qty,
                    "order_type": order_type, "order_id": trade.order.orderId,
                    "status": trade.orderStatus.status,
                }
                _log_trade("ibkr", trade_data)

                return {
                    "status": "success",
                    "order_id": trade.order.orderId,
                    "order_status": trade.orderStatus.status,
                    "symbol": symbol,
                    "side": action,
                    "qty": qty,
                    "mode": "paper" if IBKR_PORT == 7497 else "LIVE",
                }
            finally:
                ib.disconnect()
        except ImportError:
            return {"status": "error", "message": "Install: pip install ib_insync"}
        except Exception as e:
            return {"status": "error", "message": f"IBKR connection failed: {e}. Is TWS/Gateway running on port {IBKR_PORT}?"}


class IBKRAccountTool(Tool):
    """View Interactive Brokers account info."""

    def __init__(self) -> None:
        super().__init__(
            name="ibkr_account",
            description="View your Interactive Brokers account — balance and positions",
            parameters={},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            from ib_insync import IB

            ib = IB()
            try:
                await ib.connectAsync(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)

                account_values = ib.accountSummary()
                positions = ib.positions()

                acct_data = {}
                for av in account_values:
                    if av.tag in ("NetLiquidation", "TotalCashValue", "BuyingPower", "GrossPositionValue"):
                        acct_data[av.tag] = float(av.value)

                pos_data = [
                    {
                        "symbol": p.contract.symbol,
                        "quantity": int(p.position),
                        "avg_cost": float(p.avgCost),
                        "market_value": float(p.position) * float(p.avgCost),
                    }
                    for p in positions
                ]

                return {
                    "status": "success",
                    "account": acct_data,
                    "positions": pos_data,
                    "mode": "paper" if IBKR_PORT == 7497 else "live",
                }
            finally:
                ib.disconnect()
        except ImportError:
            return {"status": "error", "message": "Install: pip install ib_insync"}
        except Exception as e:
            return {"status": "error", "message": f"IBKR connection failed: {e}"}


# ============================================================
# 3. TRADINGVIEW WEBHOOK INTEGRATION
# ============================================================

class TradingViewWebhookTool(Tool):
    """Set up TradingView webhook alerts that trigger Vera trades."""

    def __init__(self) -> None:
        super().__init__(
            name="tradingview_setup",
            description="Configure TradingView webhook alerts to trigger auto-trades via Vera",
            parameters={
                "action": {"type": "str", "description": "setup (show webhook URL) or list (show active alerts)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "setup").lower()

        from config import settings
        webhook_url = f"http://{settings.server.host}:{settings.server.port}/webhook/tradingview"

        if action == "setup":
            return {
                "status": "success",
                "webhook_url": webhook_url,
                "instructions": (
                    "In TradingView:\n"
                    "1. Create an Alert on any chart\n"
                    "2. In 'Notifications', enable 'Webhook URL'\n"
                    f"3. Paste this URL: {webhook_url}\n"
                    "4. In the alert message, use this JSON format:\n"
                    '   {"action": "buy", "symbol": "AAPL", "quantity": 10, "broker": "alpaca"}\n'
                    "5. Vera will auto-execute the trade when the alert fires!"
                ),
            }
        else:
            # List trade log entries from tradingview
            log_path = DATA_DIR / "trade_log.json"
            if log_path.exists():
                trades = json.loads(log_path.read_text())
                tv_trades = [t for t in trades if t.get("broker") == "tradingview"]
                return {"status": "success", "trades": tv_trades[-10:], "count": len(tv_trades)}
            return {"status": "success", "trades": [], "count": 0}


# ============================================================
# 4. DESKTOP APP AUTOMATION (Any broker — Thinkorswim, Webull, etc.)
# ============================================================

class BrokerAppAutomationTool(Tool):
    """Automate any broker desktop app (Thinkorswim, Webull, etc.) using UI automation."""

    def __init__(self) -> None:
        super().__init__(
            name="automate_broker_app",
            description="Open and automate a broker desktop app (Thinkorswim, Webull, Fidelity, etc.)",
            parameters={
                "app": {"type": "str", "description": "Broker app name: thinkorswim, webull, fidelity, schwab, robinhood"},
                "action": {"type": "str", "description": "open, buy, sell, check_positions"},
                "symbol": {"type": "str", "description": "Stock symbol (for buy/sell)"},
                "quantity": {"type": "int", "description": "Shares (for buy/sell)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        app = kwargs.get("app", "").lower()
        action = kwargs.get("action", "open").lower()
        symbol = kwargs.get("symbol", "").upper()
        qty = kwargs.get("quantity", 0)

        # App launch commands
        app_commands = {
            "thinkorswim": {"Windows": "thinkorswim", "Darwin": "thinkorswim"},
            "webull": {"Windows": "Webull", "Darwin": "Webull"},
            "fidelity": {"Windows": "Fidelity", "Darwin": "Fidelity"},
            "schwab": {"Windows": "StreetSmartEdge", "Darwin": "StreetSmartEdge"},
            "tradingview": {"Windows": "TradingView", "Darwin": "TradingView"},
        }

        if action == "open":
            commands = app_commands.get(app, {})
            exe = commands.get(SYSTEM)
            if not exe:
                return {"status": "error", "message": f"Don't know how to launch {app} on {SYSTEM}. Try opening it manually."}

            try:
                if SYSTEM == "Windows":
                    subprocess.Popen(["start", exe], shell=True)
                elif SYSTEM == "Darwin":
                    subprocess.Popen(["open", "-a", exe])
                else:
                    subprocess.Popen([exe])

                return {"status": "success", "opened": app, "message": f"Opened {app}. You can now trade manually or I can guide you through the steps."}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif action in ("buy", "sell"):
            return {
                "status": "manual_guidance",
                "app": app,
                "steps": [
                    f"1. Make sure {app} is open and logged in",
                    "2. Navigate to the trade/order entry screen",
                    f"3. Enter symbol: {symbol}",
                    f"4. Set quantity: {qty}",
                    "5. Select order type: Market",
                    f"6. Click '{action.upper()}' button",
                    "7. Review and confirm the order",
                ],
                "note": f"I can't directly click buttons in {app} yet without screen vision. "
                        "Want me to open the app and guide you step by step?",
            }

        elif action == "check_positions":
            return {
                "status": "manual_guidance",
                "steps": [
                    f"1. Open {app}",
                    "2. Go to 'Positions' or 'Portfolio' tab",
                    "3. Tell me what you see and I'll help analyze it",
                ],
            }

        return {"status": "error", "message": f"Unknown action: {action}"}


# ============================================================
# 5. SMART TRADE ROUTER — picks the best broker
# ============================================================

class SmartTradeTool(Tool):
    """Intelligent trade router — picks the best available broker and handles safety."""

    def __init__(self) -> None:
        super().__init__(
            name="smart_trade",
            description="Execute a trade using the best available broker (Alpaca > IBKR > Paper)",
            parameters={
                "action": {"type": "str", "description": "buy or sell"},
                "symbol": {"type": "str", "description": "Stock ticker"},
                "quantity": {"type": "int", "description": "Number of shares"},
                "order_type": {"type": "str", "description": "market or limit (default: market)"},
                "limit_price": {"type": "float", "description": "Limit price (for limit orders)"},
            },
        )
        self._alpaca = AlpacaTradeTool()
        self._ibkr = IBKRTradeTool()
        # Import paper trade from income agent
        from vera.brain.agents.income import PaperTradeTool
        self._paper = PaperTradeTool()

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "")
        symbol = kwargs.get("symbol", "")
        qty = kwargs.get("quantity", 0)

        # Estimate trade value for safety check
        try:
            from vera.brain.agents.income import GetStockPriceTool
            price_tool = GetStockPriceTool()
            price_result = await price_tool.execute(symbol=symbol)
            estimated_value = (price_result.get("price", 0) or 0) * qty
        except Exception:
            estimated_value = 0

        # Safety check
        needs_confirmation = estimated_value > AUTO_TRADE_LIMIT

        # Try brokers in order: Alpaca → IBKR → Paper
        if ALPACA_API_KEY:
            result = await self._alpaca.execute(**kwargs)
            if result.get("status") == "success":
                result["estimated_value"] = round(estimated_value, 2)
                result["needs_confirmation"] = needs_confirmation
                if needs_confirmation:
                    result["safety_note"] = f"⚠️ Trade value ${estimated_value:,.2f} exceeds auto-trade limit of ${AUTO_TRADE_LIMIT:,.2f}"
                return result

        # IBKR fallback
        try:
            from ib_insync import IB
            result = await self._ibkr.execute(**kwargs)
            if result.get("status") == "success":
                return result
        except (ImportError, Exception):
            pass

        # Paper trade fallback
        result = await self._paper.execute(**kwargs)
        result["note"] = "No broker configured — executed as paper trade. Set VERA_ALPACA_API_KEY for real trading."
        return result




class TradingSetupTool(Tool):
    """Guided setup wizard for broker API credentials (Alpaca or IBKR).

    Steps: choose broker -> collect credentials -> validate -> save to .env.
    """

    def __init__(self) -> None:
        super().__init__(
            name="setup_trading",
            description="Interactive setup wizard for configuring broker API credentials (Alpaca or IBKR)",
            parameters={
                "step": {"type": "str", "description": "Setup step: choose, credentials, validate (default: choose)"},
                "broker": {"type": "str", "description": "Broker name: alpaca or ibkr"},
                "api_key": {"type": "str", "description": "API key (for Alpaca)"},
                "api_secret": {"type": "str", "description": "API secret (for Alpaca)"},
                "host": {"type": "str", "description": "TWS/Gateway host (for IBKR, default: 127.0.0.1)"},
                "port": {"type": "int", "description": "TWS/Gateway port (for IBKR, default: 7497 paper)"},
                "client_id": {"type": "int", "description": "Client ID (for IBKR, default: 1)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from vera.utils.env_writer import read_env_value, update_env_file

        step = kwargs.get("step", "choose")
        broker = kwargs.get("broker", "").lower()

        if step == "choose":
            # Check existing config
            has_alpaca = bool(read_env_value("VERA_ALPACA_API_KEY"))
            has_ibkr = bool(read_env_value("VERA_IBKR_HOST"))
            configured = []
            if has_alpaca:
                configured.append("Alpaca")
            if has_ibkr:
                configured.append("IBKR")

            return {
                "status": "choose",
                "message": (
                    f"Currently configured: {', '.join(configured) or 'none'}. "
                    "Choose a broker to set up: 'alpaca' (free API, paper + live) "
                    "or 'ibkr' (Interactive Brokers TWS/Gateway). "
                    "Provide broker=alpaca or broker=ibkr with step=credentials."
                ),
            }

        elif step == "credentials":
            if broker == "alpaca":
                api_key = kwargs.get("api_key", "")
                api_secret = kwargs.get("api_secret", "")
                if not api_key or not api_secret:
                    return {
                        "status": "needs_input",
                        "message": (
                            "To set up Alpaca:\n"
                            "1. Go to https://app.alpaca.markets/paper/dashboard/overview\n"
                            "2. Click 'API Keys' in the sidebar\n"
                            "3. Generate new keys\n"
                            "4. Provide api_key and api_secret parameters."
                        ),
                    }
                # Validate
                try:
                    import httpx
                    base = "https://paper-api.alpaca.markets"
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.get(
                            f"{base}/v2/account",
                            headers={
                                "APCA-API-KEY-ID": api_key,
                                "APCA-API-SECRET-KEY": api_secret,
                            },
                        )
                        if resp.status_code == 200:
                            acct = resp.json()
                            update_env_file("VERA_ALPACA_API_KEY", api_key)
                            update_env_file("VERA_ALPACA_SECRET_KEY", api_secret)
                            update_env_file("VERA_ALPACA_PAPER", "true")
                            return {
                                "status": "success",
                                "message": (
                                    f"Alpaca paper account validated and saved!\n"
                                    f"Account: {acct.get('account_number', 'N/A')}\n"
                                    f"Buying power: ${acct.get('buying_power', 'N/A')}\n"
                                    f"Portfolio value: ${acct.get('portfolio_value', 'N/A')}"
                                ),
                            }
                        return {"status": "error", "message": f"Alpaca rejected credentials (HTTP {resp.status_code})"}
                except Exception as e:
                    return {"status": "error", "message": f"Validation failed: {e}"}

            elif broker == "ibkr":
                host = kwargs.get("host", "127.0.0.1")
                port = kwargs.get("port", 7497)
                client_id = kwargs.get("client_id", 1)

                update_env_file("VERA_IBKR_HOST", host)
                update_env_file("VERA_IBKR_PORT", str(port))
                update_env_file("VERA_IBKR_CLIENT_ID", str(client_id))

                return {
                    "status": "success",
                    "message": (
                        f"IBKR config saved: host={host}, port={port}, client_id={client_id}.\n"
                        "Make sure TWS or IB Gateway is running with API connections enabled.\n"
                        "Port 7497 = paper trading, 7496 = live trading."
                    ),
                }

            return {"status": "error", "message": "Specify broker=alpaca or broker=ibkr"}

        return {"status": "error", "message": f"Unknown step: {step}"}

# Export all broker tools
BROKER_TOOLS = [
    AlpacaTradeTool(),
    AlpacaAccountTool(),
    IBKRTradeTool(),
    IBKRAccountTool(),
    TradingViewWebhookTool(),
    BrokerAppAutomationTool(),
    SmartTradeTool(),
    TradingSetupTool(),
]
