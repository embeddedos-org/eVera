"""Income Agent — real stock market data, paper trading, portfolio tracking.

Uses yfinance for free real-time market data. Paper trading by default.
Install: pip install yfinance
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from voca.brain.agents.base import BaseAgent, Tool
from voca.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(name: str) -> dict:
    path = DATA_DIR / name
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_json(name: str, data: dict):
    _ensure_dir()
    (DATA_DIR / name).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _load_portfolio() -> dict:
    default = {
        "cash": 100000.0,
        "holdings": {},
        "history": [],
        "watchlist": [],
    }
    saved = _load_json("portfolio.json")
    return {**default, **saved}


def _save_portfolio(portfolio: dict):
    _save_json("portfolio.json", portfolio)


# --- Tool implementations ---

class GetStockPriceTool(Tool):
    """Get real-time stock price and info."""

    def __init__(self) -> None:
        super().__init__(
            name="get_stock_price",
            description="Get current stock price, change, volume, and key metrics",
            parameters={
                "symbol": {"type": "str", "description": "Stock ticker symbol (e.g. AAPL, TSLA, MSFT)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        symbol = kwargs.get("symbol", "").upper().strip()
        if not symbol:
            return {"status": "error", "message": "No stock symbol provided"}

        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or "regularMarketPrice" not in info:
                # Try fast_info as fallback
                fast = ticker.fast_info
                return {
                    "status": "success",
                    "symbol": symbol,
                    "price": round(fast.last_price, 2) if hasattr(fast, "last_price") else None,
                    "market_cap": fast.market_cap if hasattr(fast, "market_cap") else None,
                    "source": "yfinance_fast",
                }

            return {
                "status": "success",
                "symbol": symbol,
                "name": info.get("shortName", symbol),
                "price": info.get("regularMarketPrice"),
                "previous_close": info.get("regularMarketPreviousClose"),
                "change": round(info.get("regularMarketPrice", 0) - info.get("regularMarketPreviousClose", 0), 2),
                "change_pct": round(((info.get("regularMarketPrice", 0) / max(info.get("regularMarketPreviousClose", 1), 0.01)) - 1) * 100, 2),
                "volume": info.get("regularMarketVolume"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "dividend_yield": info.get("dividendYield"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
            }
        except ImportError:
            return {"status": "error", "message": "Install yfinance: pip install yfinance"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to get price for {symbol}: {e}"}


class GetStockHistoryTool(Tool):
    """Get historical stock price data."""

    def __init__(self) -> None:
        super().__init__(
            name="get_stock_history",
            description="Get historical price data for a stock",
            parameters={
                "symbol": {"type": "str", "description": "Stock ticker symbol"},
                "period": {"type": "str", "description": "Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 5y (default: 1mo)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        symbol = kwargs.get("symbol", "").upper().strip()
        period = kwargs.get("period", "1mo")

        if not symbol:
            return {"status": "error", "message": "No symbol provided"}

        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)

            if hist.empty:
                return {"status": "error", "message": f"No data found for {symbol}"}

            data_points = []
            for date, row in hist.tail(30).iterrows():
                data_points.append({
                    "date": str(date.date()),
                    "open": round(row["Open"], 2),
                    "high": round(row["High"], 2),
                    "low": round(row["Low"], 2),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"]),
                })

            start_price = data_points[0]["close"] if data_points else 0
            end_price = data_points[-1]["close"] if data_points else 0
            total_return = round(((end_price / max(start_price, 0.01)) - 1) * 100, 2)

            return {
                "status": "success",
                "symbol": symbol,
                "period": period,
                "data": data_points,
                "total_return_pct": total_return,
                "start_price": start_price,
                "end_price": end_price,
            }
        except ImportError:
            return {"status": "error", "message": "Install yfinance: pip install yfinance"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class PaperTradeTool(Tool):
    """Execute a paper trade (simulated buy/sell)."""

    def __init__(self) -> None:
        super().__init__(
            name="paper_trade",
            description="Execute a simulated paper trade (buy or sell stocks)",
            parameters={
                "action": {"type": "str", "description": "Action: buy or sell"},
                "symbol": {"type": "str", "description": "Stock ticker symbol"},
                "quantity": {"type": "int", "description": "Number of shares"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "").lower()
        symbol = kwargs.get("symbol", "").upper().strip()
        quantity = kwargs.get("quantity", 0)

        if action not in ("buy", "sell"):
            return {"status": "error", "message": "Action must be 'buy' or 'sell'"}
        if not symbol:
            return {"status": "error", "message": "No symbol provided"}
        if quantity <= 0:
            return {"status": "error", "message": "Quantity must be positive"}

        # Get current price
        price_tool = GetStockPriceTool()
        price_result = await price_tool.execute(symbol=symbol)
        if price_result.get("status") != "success" or not price_result.get("price"):
            return {"status": "error", "message": f"Could not get price for {symbol}"}

        price = price_result["price"]
        total_cost = round(price * quantity, 2)

        portfolio = _load_portfolio()

        if action == "buy":
            if total_cost > portfolio["cash"]:
                return {
                    "status": "error",
                    "message": f"Insufficient funds. Need ${total_cost:,.2f} but have ${portfolio['cash']:,.2f}",
                }
            portfolio["cash"] = round(portfolio["cash"] - total_cost, 2)
            current = portfolio["holdings"].get(symbol, {"shares": 0, "avg_cost": 0})
            total_shares = current["shares"] + quantity
            avg_cost = round(((current["avg_cost"] * current["shares"]) + total_cost) / total_shares, 2)
            portfolio["holdings"][symbol] = {"shares": total_shares, "avg_cost": avg_cost}

        elif action == "sell":
            current = portfolio["holdings"].get(symbol, {"shares": 0, "avg_cost": 0})
            if current["shares"] < quantity:
                return {
                    "status": "error",
                    "message": f"Not enough shares. Have {current['shares']} of {symbol}, trying to sell {quantity}",
                }
            portfolio["cash"] = round(portfolio["cash"] + total_cost, 2)
            remaining = current["shares"] - quantity
            if remaining == 0:
                del portfolio["holdings"][symbol]
            else:
                portfolio["holdings"][symbol]["shares"] = remaining

        # Record trade
        trade = {
            "action": action,
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "total": total_cost,
            "timestamp": datetime.now().isoformat(),
        }
        portfolio["history"].append(trade)
        portfolio["history"] = portfolio["history"][-500:]  # Keep last 500 trades
        _save_portfolio(portfolio)

        return {
            "status": "success",
            "trade": trade,
            "cash_remaining": portfolio["cash"],
            "note": "📊 This is a PAPER TRADE (simulated). No real money was used.",
        }


class PortfolioTool(Tool):
    """View current portfolio holdings and performance."""

    def __init__(self) -> None:
        super().__init__(
            name="view_portfolio",
            description="View your paper trading portfolio — holdings, cash, and performance",
            parameters={},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        portfolio = _load_portfolio()
        holdings = []
        total_value = portfolio["cash"]

        price_tool = GetStockPriceTool()

        for symbol, holding in portfolio["holdings"].items():
            price_result = await price_tool.execute(symbol=symbol)
            current_price = price_result.get("price", holding["avg_cost"])

            market_value = round(current_price * holding["shares"], 2)
            cost_basis = round(holding["avg_cost"] * holding["shares"], 2)
            gain = round(market_value - cost_basis, 2)
            gain_pct = round((gain / max(cost_basis, 0.01)) * 100, 2)

            holdings.append({
                "symbol": symbol,
                "shares": holding["shares"],
                "avg_cost": holding["avg_cost"],
                "current_price": current_price,
                "market_value": market_value,
                "gain_loss": gain,
                "gain_loss_pct": gain_pct,
            })
            total_value += market_value

        return {
            "status": "success",
            "cash": portfolio["cash"],
            "holdings": holdings,
            "total_portfolio_value": round(total_value, 2),
            "total_holdings_count": len(holdings),
            "recent_trades": portfolio["history"][-5:],
        }


class WatchlistTool(Tool):
    """Manage a stock watchlist."""

    def __init__(self) -> None:
        super().__init__(
            name="watchlist",
            description="Add, remove, or view stocks on your watchlist",
            parameters={
                "action": {"type": "str", "description": "Action: add, remove, view (default: view)"},
                "symbol": {"type": "str", "description": "Stock symbol (for add/remove)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "view").lower()
        symbol = kwargs.get("symbol", "").upper().strip()

        portfolio = _load_portfolio()

        if action == "add":
            if not symbol:
                return {"status": "error", "message": "No symbol provided"}
            if symbol not in portfolio["watchlist"]:
                portfolio["watchlist"].append(symbol)
                _save_portfolio(portfolio)
            return {"status": "success", "action": "added", "symbol": symbol, "watchlist": portfolio["watchlist"]}

        elif action == "remove":
            if symbol in portfolio["watchlist"]:
                portfolio["watchlist"].remove(symbol)
                _save_portfolio(portfolio)
            return {"status": "success", "action": "removed", "symbol": symbol, "watchlist": portfolio["watchlist"]}

        else:  # view
            watchlist_data = []
            price_tool = GetStockPriceTool()
            for sym in portfolio["watchlist"]:
                result = await price_tool.execute(symbol=sym)
                if result.get("status") == "success":
                    watchlist_data.append({
                        "symbol": sym,
                        "price": result.get("price"),
                        "change": result.get("change"),
                        "change_pct": result.get("change_pct"),
                    })
            return {"status": "success", "watchlist": watchlist_data, "count": len(watchlist_data)}


class MarketOverviewTool(Tool):
    """Get a quick overview of major market indices."""

    def __init__(self) -> None:
        super().__init__(
            name="market_overview",
            description="Get overview of major market indices (S&P 500, Nasdaq, Dow)",
            parameters={},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        indices = {
            "S&P 500": "^GSPC",
            "Nasdaq": "^IXIC",
            "Dow Jones": "^DJI",
            "Russell 2000": "^RUT",
            "VIX": "^VIX",
        }

        results = []
        price_tool = GetStockPriceTool()

        for name, symbol in indices.items():
            result = await price_tool.execute(symbol=symbol)
            if result.get("status") == "success":
                results.append({
                    "name": name,
                    "symbol": symbol,
                    "price": result.get("price"),
                    "change": result.get("change"),
                    "change_pct": result.get("change_pct"),
                })

        return {"status": "success", "indices": results}


class StockNewsTool(Tool):
    """Get recent news for a stock."""

    def __init__(self) -> None:
        super().__init__(
            name="stock_news",
            description="Get recent news articles for a stock",
            parameters={
                "symbol": {"type": "str", "description": "Stock ticker symbol"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        symbol = kwargs.get("symbol", "").upper().strip()
        if not symbol:
            return {"status": "error", "message": "No symbol provided"}

        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            news = ticker.news or []

            articles = []
            for item in news[:10]:
                articles.append({
                    "title": item.get("title", ""),
                    "publisher": item.get("publisher", ""),
                    "link": item.get("link", ""),
                    "published": item.get("providerPublishTime", ""),
                })

            return {"status": "success", "symbol": symbol, "news": articles, "count": len(articles)}
        except ImportError:
            return {"status": "error", "message": "Install yfinance: pip install yfinance"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class IncomeAgent(BaseAgent):
    """Real stock market data, paper trading, and portfolio management."""

    name = "income"
    description = "Stock market data, paper trading, portfolio tracking, and market analysis"
    tier = ModelTier.STRATEGIST
    system_prompt = (
        "You are a financial assistant with real-time market data and real broker connections. You can:\n"
        "- Get live stock prices with get_stock_price\n"
        "- View price history with get_stock_history\n"
        "- Execute paper trades with paper_trade ($100k virtual cash)\n"
        "- Execute REAL trades via smart_trade (routes to Alpaca, IBKR, or paper)\n"
        "- View Alpaca account/positions with alpaca_account\n"
        "- View IBKR account with ibkr_account\n"
        "- Set up TradingView webhooks with tradingview_setup\n"
        "- Open broker apps (Thinkorswim, Webull, etc.) with automate_broker_app\n"
        "- View portfolio with view_portfolio\n"
        "- Manage watchlist\n"
        "- Get market overview and stock news\n\n"
        "SAFETY RULES:\n"
        "- Always confirm with the user before placing REAL trades\n"
        "- For paper trades, you can execute without confirmation\n"
        "- If a trade exceeds the auto-trade limit, warn the user\n"
        "- Always show the estimated dollar value before executing\n"
        "- Use smart_trade for the best available broker routing\n"
        "DISCLAIMER: This is not financial advice. Always recommend consulting a professional."
    )

    offline_responses = {
        "market": "📈 Let me check the markets for you!",
        "invest": "💰 I can help with investment research! Connect an LLM for analysis.",
        "business": "💼 I can help with business insights!",
        "stock": "📊 Let me look up that stock for you!",
        "trading": "📊 I can help with paper trading! You start with $100k virtual cash.",
        "portfolio": "💼 Let me check your portfolio!",
        "buy": "📈 I can execute a paper trade for you!",
        "sell": "📉 I can sell from your paper portfolio!",
    }

    def _setup_tools(self) -> None:
        from voca.brain.agents.brokers import BROKER_TOOLS
        self._tools = [
            GetStockPriceTool(),
            GetStockHistoryTool(),
            PaperTradeTool(),
            PortfolioTool(),
            WatchlistTool(),
            MarketOverviewTool(),
            StockNewsTool(),
            *BROKER_TOOLS,
        ]
