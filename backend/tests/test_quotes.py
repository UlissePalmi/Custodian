"""Quote-source routing and bond-source parsing.

Network-free: the sources are exercised by monkeypatching `_get_json` (payload
parsing) or the source functions themselves (fallback order) — never a real
request.
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


def test_positive_number_parses_numbers_and_german_strings() -> None:
    assert quotes._positive_number(45.978) == Decimal("45.978")
    assert quotes._positive_number("46,144") == Decimal("46.144")


@pytest.mark.parametrize("value", ["./.", None, 0, -1])
def test_positive_number_rejects_placeholders(value: object) -> None:
    assert quotes._positive_number(value) is None


def _patch_json(monkeypatch: pytest.MonkeyPatch, payloads: dict[str, dict]) -> None:
    """Serve canned payloads keyed by a substring of the requested URL."""

    def fake_get_json(url: str) -> dict:
        for fragment, payload in payloads.items():
            if fragment in url:
                return payload
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(quotes, "_get_json", fake_get_json)


def test_tradegate_untraded_falls_back_to_bid_ask_mid(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_json(
        monkeypatch,
        {"tradegate": {"bid": 45.978, "ask": 45.997, "last": "./.", "close": 46.144}},
    )
    assert quotes._fetch_tradegate("US912810SN90") == Decimal("45.9875")


def test_tradegate_prefers_last_trade(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_json(
        monkeypatch,
        {"tradegate": {"bid": 45.978, "ask": 45.997, "last": 46.02, "close": 46.144}},
    )
    assert quotes._fetch_tradegate("US912810SN90") == Decimal("46.02")


def test_tradegate_closed_market_uses_close(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_json(
        monkeypatch,
        {"tradegate": {"bid": 0, "ask": 0, "last": "./.", "close": 46.144}},
    )
    assert quotes._fetch_tradegate("US912810SN90") == Decimal("46.144")


def test_frankfurt_prefers_last_then_previous_close(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        quotes,
        "_get_sse_json",
        lambda url: {"lastPrice": None, "closingPricePrevTradingDay": 46.02},
    )
    assert quotes._fetch_frankfurt("US912810SN90") == Decimal("46.02")


def test_onvista_resolves_isin_then_reads_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_json(
        monkeypatch,
        {
            "query": {"list": [{"isin": "US912810SN90", "entityValue": "175613092"}]},
            "snapshot": {"quote": {"last": 45.9755, "previousLast": 46.1255}},
        },
    )
    assert quotes._fetch_onvista("US912810SN90") == Decimal("45.9755")


def test_onvista_unknown_isin_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_json(monkeypatch, {"query": {"list": []}})
    assert quotes._fetch_onvista("XS0000000009") is None


def test_isin_fetch_falls_through_dead_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    def dead(isin: str) -> Decimal | None:
        raise OSError("venue offline")

    monkeypatch.setattr(quotes, "_fetch_tradegate", dead)
    monkeypatch.setattr(quotes, "_fetch_frankfurt", lambda isin: None)
    monkeypatch.setattr(quotes, "_fetch_onvista", lambda isin: Decimal("46.02"))
    assert quotes._fetch_isin("US912810SN90") == (Decimal("46.0200"), None)


def test_isin_fetch_stops_at_first_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    def untouched(isin: str) -> Decimal | None:
        raise AssertionError("later source should not be called")

    monkeypatch.setattr(quotes, "_fetch_tradegate", lambda isin: Decimal("45.9875"))
    monkeypatch.setattr(quotes, "_fetch_frankfurt", untouched)
    monkeypatch.setattr(quotes, "_fetch_onvista", untouched)
    assert quotes._fetch_isin("US912810SN90") == (Decimal("45.9875"), None)


def test_isin_fetch_all_dead_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("_fetch_tradegate", "_fetch_frankfurt", "_fetch_onvista"):
        monkeypatch.setattr(quotes, name, lambda isin: None)
    assert quotes._fetch_isin("US912810SN90") == (None, None)
