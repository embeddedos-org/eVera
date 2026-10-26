"""Unit tests for the proactive scheduler — S4: stock alerts (yfinance).

Covers vera/scheduler.py (issue #46 coverage drive), slice S4 of the
decomposition in docs/scheduler-coverage-scoping.md: the
_check_stock_alerts worker. yfinance is stubbed in sys.modules (the
S1/S3 pattern): a fake module whose Ticker returns canned fast_info
values, so no test touches the network or the real package. The
ImportError path is pinned by installing None in sys.modules, which
makes `import yfinance` raise ImportError exactly as an absent
package does.

Behaviour pinned as the code implements it:

- The symbol set is watchlist ∪ holdings keys, checked in set order,
  capped at the first 10 symbols ([:10] slice): with 12 qualifying
  symbols exactly 10 alerts fire.
- The alert threshold is inclusive: |change| >= 5% fires, +4.x% does
  not. Payload, formatting ("{:+.1f}%" / "${:.2f}") and mood mapping
  (up -> "excited", down -> "empathetic") are asserted exactly.
- A symbol whose Ticker/fast_info raises is skipped silently and
  does not stop later symbols; a missing price or a non-positive
  previous close is skipped without an alert.
- fast_info attributes are read via hasattr: an info object without
  last_price/previous_close attributes is treated as no data.
- No portfolio file, malformed JSON, and an empty symbol set all
  return silently before yfinance is ever imported.
"""

from __future__ import annotations

import json
import sys
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import vera.scheduler as scheduler_module
from vera.scheduler import ProactiveScheduler


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(scheduler_module, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def recorder():
    received: list[dict] = []

    async def record(notification: dict) -> None:
        received.append(notification)

    return record, received


def make_scheduler(record) -> ProactiveScheduler:
    scheduler = ProactiveScheduler()
    scheduler.add_notification_handler(record)
    return scheduler


def write_portfolio(data_dir: Path, payload) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    (data_dir / "portfolio.json").write_text(text)


def install_yfinance(monkeypatch: pytest.MonkeyPatch, tickers: dict) -> list[str]:
    """Install a fake yfinance module. `tickers` maps symbol -> either a
    fast_info namespace or an Exception instance to raise. Returns the
    list of symbols Ticker was constructed with."""
    calls: list[str] = []

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            calls.append(symbol)
            self._entry = tickers[symbol]

        @property
        def fast_info(self):
            if isinstance(self._entry, Exception):
                raise self._entry
            return self._entry

    module = types.ModuleType("yfinance")
    module.Ticker = FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", module)
    return calls


def info(price, prev):
    return SimpleNamespace(last_price=price, previous_close=prev)


async def test_no_portfolio_file_is_silent(data_dir, recorder, monkeypatch):
    record, received = recorder
    calls = install_yfinance(monkeypatch, {})
    scheduler = make_scheduler(record)

    await scheduler._check_stock_alerts()

    assert received == []
    assert calls == []


async def test_malformed_portfolio_is_silent(data_dir, recorder, monkeypatch):
    record, received = recorder
    write_portfolio(data_dir, "{not json")
    calls = install_yfinance(monkeypatch, {})
    scheduler = make_scheduler(record)

    await scheduler._check_stock_alerts()

    assert received == []
    assert calls == []


async def test_empty_symbol_set_is_silent(data_dir, recorder, monkeypatch):
    record, received = recorder
    write_portfolio(data_dir, {"watchlist": [], "holdings": {}})
    calls = install_yfinance(monkeypatch, {})
    scheduler = make_scheduler(record)

    await scheduler._check_stock_alerts()

    assert received == []
    assert calls == []


async def test_up_move_alerts_with_exact_payload(data_dir, recorder, monkeypatch):
    record, received = recorder
    write_portfolio(data_dir, {"watchlist": ["AAA"], "holdings": {}})
    install_yfinance(monkeypatch, {"AAA": info(110.0, 100.0)})
    scheduler = make_scheduler(record)

    await scheduler._check_stock_alerts()

    assert len(received) == 1
    note = dict(received[0])
    timestamp = note.pop("timestamp")  # _notify stamps every notification
    datetime.fromisoformat(timestamp)
    assert note == {
        "type": "stock_alert",
        "message": "📈 AAA moved +10.0% to $110.00!",
        "mood": "excited",
        "data": {"symbol": "AAA", "price": 110.0, "change_pct": 10.0},
    }


async def test_down_move_alerts_empathetic(data_dir, recorder, monkeypatch):
    record, received = recorder
    write_portfolio(data_dir, {"watchlist": [], "holdings": {"BBB": 3}})
    install_yfinance(monkeypatch, {"BBB": info(90.0, 100.0)})
    scheduler = make_scheduler(record)

    await scheduler._check_stock_alerts()

    assert len(received) == 1
    assert received[0]["message"] == "📉 BBB moved -10.0% to $90.00!"
    assert received[0]["mood"] == "empathetic"
    assert received[0]["data"] == {"symbol": "BBB", "price": 90.0, "change_pct": -10.0}


async def test_threshold_is_inclusive_at_five_percent(
    data_dir, recorder, monkeypatch
):
    record, received = recorder
    write_portfolio(data_dir, {"watchlist": ["AAA", "CCC"], "holdings": {}})
    install_yfinance(
        monkeypatch, {"AAA": info(105.0, 100.0), "CCC": info(104.0, 100.0)}
    )
    scheduler = make_scheduler(record)

    await scheduler._check_stock_alerts()

    assert [n["data"]["symbol"] for n in received] == ["AAA"]


async def test_missing_or_zero_price_data_is_skipped(
    data_dir, recorder, monkeypatch
):
    record, received = recorder
    write_portfolio(
        data_dir, {"watchlist": ["NUL", "ZERO", "NOATTR"], "holdings": {}}
    )
    install_yfinance(
        monkeypatch,
        {
            "NUL": info(None, 100.0),
            "ZERO": info(50.0, 0),
            "NOATTR": SimpleNamespace(),
        },
    )
    scheduler = make_scheduler(record)

    await scheduler._check_stock_alerts()

    assert received == []


async def test_failing_symbol_does_not_stop_others(
    data_dir, recorder, monkeypatch
):
    record, received = recorder
    write_portfolio(data_dir, {"watchlist": ["BAD", "AAA"], "holdings": {}})
    install_yfinance(
        monkeypatch,
        {"BAD": RuntimeError("feed down"), "AAA": info(120.0, 100.0)},
    )
    scheduler = make_scheduler(record)

    await scheduler._check_stock_alerts()

    assert [n["data"]["symbol"] for n in received] == ["AAA"]


async def test_symbol_cap_is_ten(data_dir, recorder, monkeypatch):
    record, received = recorder
    symbols = [f"S{i:02d}" for i in range(12)]
    write_portfolio(data_dir, {"watchlist": symbols, "holdings": {}})
    calls = install_yfinance(
        monkeypatch, {s: info(110.0, 100.0) for s in symbols}
    )
    scheduler = make_scheduler(record)

    await scheduler._check_stock_alerts()

    assert len(calls) == 10
    assert len(received) == 10


async def test_missing_yfinance_is_silent(data_dir, recorder, monkeypatch):
    record, received = recorder
    write_portfolio(data_dir, {"watchlist": ["AAA"], "holdings": {}})
    monkeypatch.setitem(sys.modules, "yfinance", None)
    scheduler = make_scheduler(record)

    await scheduler._check_stock_alerts()

    assert received == []
