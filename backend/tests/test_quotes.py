"""Quote-source routing and Tradegate payload parsing.

Network-free: `_fetch_tradegate` is exercised through its parsing helpers and a
monkeypatched payload, never a real request.
"""

from decimal import Decimal

import pytest

from app.services import quotes


@pytest.mark.parametrize("isin", ["US912810SN90", "DE0001102580", "IE00B4L5Y983"])
def test_isin_pattern_matches(isin: str) -> None:
    assert quotes.ISIN.fullmatch(isin)


@pytest.mark.parametrize("ticker", ["VOO", "BRK.B", "US912810SN9", "US912810SN900"])
def test_isin_pattern_rejects_plain_tickers(ticker: str) -> None:
    assert not quotes.ISIN.fullmatch(ticker)


def test_tradegate_number_parses_numbers_and_german_strings() -> None:
    assert quotes._tradegate_number(45.978) == Decimal("45.978")
    assert quotes._tradegate_number("46,144") == Decimal("46.144")


@pytest.mark.parametrize("value", ["./.", None, 0, -1])
def test_tradegate_number_rejects_placeholders(value: object) -> None:
    assert quotes._tradegate_number(value) is None


def _patch_payload(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    import contextlib
    import io
    import json

    @contextlib.contextmanager
    def fake_urlopen(url: str, timeout: float):
        yield io.StringIO(json.dumps(payload))

    monkeypatch.setattr(quotes, "urlopen", fake_urlopen)


def test_tradegate_untraded_falls_back_to_bid_ask_mid(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_payload(
        monkeypatch,
        {"bid": 45.978, "ask": 45.997, "last": "./.", "close": 46.144},
    )
    price, ytd = quotes._fetch_tradegate("US912810SN90")
    assert price == Decimal("45.9875")
    assert ytd is None


def test_tradegate_prefers_last_trade(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_payload(
        monkeypatch,
        {"bid": 45.978, "ask": 45.997, "last": 46.02, "close": 46.144},
    )
    price, _ = quotes._fetch_tradegate("US912810SN90")
    assert price == Decimal("46.0200")


def test_tradegate_closed_market_uses_close(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_payload(
        monkeypatch,
        {"bid": 0, "ask": 0, "last": "./.", "close": 46.144},
    )
    price, _ = quotes._fetch_tradegate("US912810SN90")
    assert price == Decimal("46.1440")
