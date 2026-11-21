"""get_stock_history reports the return over the period that was asked for.

``GetStockHistoryTool`` lists only the last 30 rows of the history, and it
used to take ``start_price`` and ``total_return_pct`` from those rows too.
For any period longer than about six weeks ("3mo", "1y", "5y") the
reported return was the last 30 trading days' return, not the period's.
"""

from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

from vera.brain.agents.income import GetStockHistoryTool


def _install_fake_yfinance(monkeypatch, closes: list[float]) -> None:
    index = pd.date_range("2026-01-01", periods=len(closes), freq="B")
    frame = pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": [1000] * len(closes)},
        index=index,
    )

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, period: str) -> pd.DataFrame:
            return frame

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=FakeTicker))


async def test_return_covers_the_whole_period(monkeypatch):
    # 60 trading days: 100 for the first 30, then 150, ending at 200.
    closes = [100.0] * 30 + [150.0] * 29 + [200.0]
    _install_fake_yfinance(monkeypatch, closes)

    result = await GetStockHistoryTool().execute(symbol="ACME", period="3mo")

    assert result["status"] == "success"
    assert result["start_price"] == 100.0
    assert result["end_price"] == 200.0
    assert result["total_return_pct"] == 100.0
    # The listed rows are still capped at the last 30.
    assert len(result["data"]) == 30
    assert result["data"][0]["close"] == 150.0


@pytest.mark.parametrize("closes, expected", [([50.0, 55.0], 10.0), ([80.0] * 10 + [60.0], -25.0)])
async def test_short_history_return_unchanged(monkeypatch, closes, expected):
    _install_fake_yfinance(monkeypatch, closes)

    result = await GetStockHistoryTool().execute(symbol="ACME", period="5d")

    assert result["total_return_pct"] == expected
    assert len(result["data"]) == len(closes)
