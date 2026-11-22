"""currency_convert must not report a conversion at a made-up rate of 1.

``CurrencyConvertTool`` looked the target currency up in the API's ``rates``
with a default of 1, so a code the table does not have under that exact key
(a lowercase "eur", a typo, or an error response with no ``rates`` at all)
came back as a successful conversion with the amount unchanged.
"""

from __future__ import annotations

import httpx

from vera.brain.agents.travel_agent import CurrencyConvertTool

RATES = {"base": "USD", "rates": {"USD": 1, "EUR": 0.5, "JPY": 150.0}}


def _fake_api(monkeypatch, payload: dict) -> list[str]:
    urls: list[str] = []

    class FakeResponse:
        def json(self) -> dict:
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *exc) -> None:
            return None

        async def get(self, url: str) -> FakeResponse:
            urls.append(url)
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    return urls


async def test_known_currencies_convert(monkeypatch):
    _fake_api(monkeypatch, RATES)
    result = await CurrencyConvertTool().execute(amount=100, from_currency="USD", to_currency="EUR")
    assert result["status"] == "success"
    assert result["rate"] == 0.5
    assert result["converted"] == 50.0


async def test_lowercase_codes_use_the_real_rate(monkeypatch):
    urls = _fake_api(monkeypatch, RATES)
    result = await CurrencyConvertTool().execute(amount=100, from_currency="usd", to_currency="eur")
    assert result["status"] == "success"
    assert result["converted"] == 50.0
    assert result["from"] == "USD" and result["to"] == "EUR"
    assert urls[0].endswith("/latest/USD")


async def test_unknown_target_currency_is_an_error(monkeypatch):
    _fake_api(monkeypatch, RATES)
    result = await CurrencyConvertTool().execute(amount=100, from_currency="USD", to_currency="XYZ")
    assert result["status"] == "error"
    assert "XYZ" in result["message"]


async def test_error_response_without_rates_is_an_error(monkeypatch):
    # A response with no rates table at all, such as an error body.
    _fake_api(monkeypatch, {"result": "error", "error-type": "unsupported-code"})
    result = await CurrencyConvertTool().execute(amount=100, from_currency="ABC", to_currency="EUR")
    assert result["status"] == "error"


async def test_amount_given_as_text(monkeypatch):
    _fake_api(monkeypatch, RATES)
    result = await CurrencyConvertTool().execute(amount="2.5", from_currency="USD", to_currency="JPY")
    assert result["status"] == "success"
    assert result["converted"] == 375.0
