"""Quote-source routing and Tradegate payload parsing.

Network-free: `_fetch_tradegate` is exercised through its parsing helpers and a
monkeypatched payload, never a real request.
"""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models import PriceQuote
from app.services import quotes

EASTERN = ZoneInfo("America/New_York")


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


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # Weekday evening, well after close: today's own close.
        (datetime(2026, 7, 22, 20, 0, tzinfo=EASTERN), datetime(2026, 7, 22, 16, 30, tzinfo=EASTERN)),
        # Weekday, before the session opens: falls back to the prior day's close.
        (datetime(2026, 7, 22, 6, 0, tzinfo=EASTERN), datetime(2026, 7, 21, 16, 30, tzinfo=EASTERN)),
        # Saturday: last close was Friday's.
        (datetime(2026, 7, 25, 12, 0, tzinfo=EASTERN), datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN)),
        # Sunday: still Friday's close.
        (datetime(2026, 7, 26, 12, 0, tzinfo=EASTERN), datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN)),
        # Monday before open: weekend rolls all the way back to Friday.
        (datetime(2026, 7, 27, 6, 0, tzinfo=EASTERN), datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN)),
    ],
)
def test_last_close_at_or_before(now: datetime, expected: datetime) -> None:
    assert quotes._last_close_at_or_before(now) == expected


def test_get_quotes_refreshes_on_first_read_after_close(monkeypatch: pytest.MonkeyPatch, db) -> None:
    """A quote fetched during the trading day is stale as soon as the market
    closes, even though it's well within the TTL — the first read after
    close must fetch the real closing price rather than wait out the day."""
    stale_as_of = datetime(2026, 7, 24, 11, 0, tzinfo=EASTERN)
    db.add(PriceQuote(ticker="VOO", price=Decimal("500.00"), as_of=stale_as_of))
    db.commit()

    after_close = datetime(2026, 7, 24, 20, 0, tzinfo=EASTERN).astimezone(ZoneInfo("UTC"))
    monkeypatch.setattr(quotes, "_fetch_one", lambda ticker: (Decimal("501.00"), None))

    result = quotes.get_quotes(db, ["VOO"], now=after_close)
    assert result["VOO"].price == Decimal("501.00")


def test_get_quotes_skips_refresh_once_todays_close_is_cached(monkeypatch: pytest.MonkeyPatch, db) -> None:
    """Once we already have a quote fetched at/after today's close, further
    reads before the next close must not hit the network."""
    fetched_after_close = datetime(2026, 7, 24, 17, 0, tzinfo=EASTERN)
    db.add(PriceQuote(ticker="VOO", price=Decimal("500.00"), as_of=fetched_after_close))
    db.commit()

    later_same_evening = datetime(2026, 7, 24, 22, 0, tzinfo=EASTERN).astimezone(ZoneInfo("UTC"))

    def _boom(ticker: str) -> tuple[Decimal, None]:
        raise AssertionError("should not refetch: already have today's close")

    monkeypatch.setattr(quotes, "_fetch_one", _boom)

    result = quotes.get_quotes(db, ["VOO"], now=later_same_evening)
    assert result["VOO"].price == Decimal("500.00")
