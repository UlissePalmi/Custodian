"""Delayed price feed.

Quotes are refreshed lazily on read. While the market is open, a quote is
good for `quote_ttl_minutes`. Once the market has closed, the cache is only
good until the *next* close — so the first read after today's close always
fetches the final closing price, then goes quiet until the following
session's close. Every failure path falls back to the cached row with its
real `as_of`, so an offline Pi shows slightly old prices rather than an
error — the front end displays the timestamp.
"""

import json
import logging
import re
import threading
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PriceQuote
from app.money import round_cents

log = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(16, 30)

# Holdings entered by ISIN (bonds, mostly) have no yfinance listing; those are
# priced off German trading venues instead, tried in order — see `_fetch_isin`.
ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
TRADEGATE_REFRESH = "https://www.tradegatebsx.com/refresh.php?isin="
FRANKFURT_PRICE = "https://api.boerse-frankfurt.de/v1/data/price_information?mic=XFRA&isin="
ONVISTA_SEARCH = "https://api.onvista.de/api/v1/instruments/query?limit=5&searchValue="
ONVISTA_SNAPSHOT = "https://api.onvista.de/api/v1/bonds/{entity}/snapshot"

# One refresh at a time: several dashboard requests can land together and there
# is no point in each of them hitting the network.
_refresh_lock = threading.Lock()


def _near_market_hours(now: datetime | None = None) -> bool:
    now_et = (now or datetime.now(timezone.utc)).astimezone(EASTERN)
    if now_et.weekday() >= 5:
        return False
    return MARKET_OPEN <= now_et.time() <= MARKET_CLOSE


def _is_stale(quote: PriceQuote | None, now: datetime) -> bool:
    if quote is None:
        return True
    age = now - quote.as_of
    return age > timedelta(minutes=settings.quote_ttl_minutes)


def _last_close_at_or_before(now_et: datetime) -> datetime:
    """The most recent market-close instant at or before `now_et` (ET).

    Walks back one calendar day at a time until it lands on a weekday whose
    close time has already passed — Friday's close on a Saturday or Sunday,
    the prior weekday's close before today's session has opened.
    """
    day = now_et.date()
    while True:
        close = datetime.combine(day, MARKET_CLOSE, tzinfo=EASTERN)
        if close <= now_et and day.weekday() < 5:
            return close
        day -= timedelta(days=1)


def get_quotes(db: Session, tickers: list[str], now: datetime | None = None) -> dict[str, PriceQuote]:
    """Cached quotes for `tickers`, refreshed first if stale.

    `now` is exposed for tests; callers always take the default (real UTC now).
    """
    if not tickers:
        return {}

    wanted = sorted({t.upper() for t in tickers})
    cached = {q.ticker: q for q in db.scalars(select(PriceQuote).where(PriceQuote.ticker.in_(wanted)))}
    now = now or datetime.now(timezone.utc)

    if _near_market_hours(now):
        # Market's open: the usual short TTL applies.
        stale = [t for t in wanted if _is_stale(cached.get(t), now)]
    else:
        # Market's closed: the cache is only good until the next close, so a
        # quote from before the last close is stale no matter how "fresh" its
        # TTL looks — this is what makes the first read after today's close
        # always fetch the final price instead of waiting for the next
        # market-hours window.
        boundary = _last_close_at_or_before(now.astimezone(EASTERN))
        stale = [t for t in wanted if (q := cached.get(t)) is None or q.as_of < boundary]

    if stale:
        refreshed = _refresh(db, stale)
        cached.update(refreshed)

    return cached


def _refresh(db: Session, tickers: list[str]) -> dict[str, PriceQuote]:
    updated: dict[str, PriceQuote] = {}
    with _refresh_lock:
        for ticker in tickers:
            try:
                price, ytd = _fetch_one(ticker)
            except Exception as exc:  # noqa: BLE001 - offline is an expected state here
                log.warning("Quote refresh failed for %s: %s", ticker, exc)
                continue
            if price is None:
                continue

            quote = db.get(PriceQuote, ticker)
            if quote is None:
                quote = PriceQuote(ticker=ticker)
                db.add(quote)
            quote.price = price
            quote.as_of = datetime.now(timezone.utc)
            if ytd is not None:
                quote.ytd_return_percent = ytd
            updated[ticker] = quote
        if updated:
            db.commit()
    return updated


def _fetch_one(ticker: str) -> tuple[Decimal | None, Decimal | None]:
    if ISIN.fullmatch(ticker):
        return _fetch_isin(ticker)
    return _fetch_yfinance(ticker)


def _fetch_isin(isin: str) -> tuple[Decimal | None, Decimal | None]:
    """Quote for an ISIN, from the first bond source that answers.

    Three German venues quote US Treasuries by ISIN through plain JSON
    endpoints, all by the usual bond convention — percent of face value — so a
    position's `quantity` must be face value / 100 for market value to come out
    right. They are redundant on purpose: each is unofficial and could vanish,
    and prices agree to within a few basis points, so the first answer wins.
    None of them serves history, hence no YTD figure.
    """
    for name, source in (
        ("Tradegate", _fetch_tradegate),
        ("Boerse Frankfurt", _fetch_frankfurt),
        ("onvista", _fetch_onvista),
    ):
        try:
            price = source(isin)
        except Exception as exc:  # noqa: BLE001 - a dead venue must not stop the next one
            log.warning("Bond source %s failed for %s: %s", name, isin, exc)
            continue
        if price is not None:
            return price.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), None
    return None, None


def _fetch_tradegate(isin: str) -> Decimal | None:
    """Tradegate's per-instrument feed. Fields with no value yet come back as
    the string "./."; `last` stays that way until the instrument trades, so
    fall back to the live bid/ask mid, then to the previous close."""
    payload = _get_json(TRADEGATE_REFRESH + isin)
    price = _positive_number(payload.get("last"))
    if price is None:
        bid = _positive_number(payload.get("bid"))
        ask = _positive_number(payload.get("ask"))
        if bid is not None and ask is not None:
            price = (bid + ask) / 2
    return price or _positive_number(payload.get("close"))


def _fetch_frankfurt(isin: str) -> Decimal | None:
    """Börse Frankfurt's price feed. The endpoint is server-sent events and
    never closes the connection, so read only the first `data:` frame instead
    of reading to EOF (which would hang until the timeout)."""
    payload = _get_sse_json(FRANKFURT_PRICE + isin)
    if payload is None:
        return None
    return _positive_number(payload.get("lastPrice")) or _positive_number(
        payload.get("closingPricePrevTradingDay")
    )


def _fetch_onvista(isin: str) -> Decimal | None:
    """onvista's API: resolve the ISIN to its numeric entity id, then read the
    bond snapshot's quote (Baader OTC prices)."""
    hits = _get_json(ONVISTA_SEARCH + isin).get("list", [])
    entity = next((h.get("entityValue") for h in hits if h.get("isin") == isin), None)
    if entity is None:
        return None
    quote = _get_json(ONVISTA_SNAPSHOT.format(entity=entity)).get("quote", {})
    price = _positive_number(quote.get("last"))
    if price is None:
        bid = _positive_number(quote.get("bid"))
        ask = _positive_number(quote.get("ask"))
        if bid is not None and ask is not None:
            price = (bid + ask) / 2
    return price or _positive_number(quote.get("previousLast"))


def _get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "custodian/1.0"})
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_sse_json(url: str) -> dict | None:
    """First `data:` frame of a server-sent-events stream, or None if the
    stream yields none within its first few lines."""
    request = Request(url, headers={"User-Agent": "custodian/1.0"})
    with urlopen(request, timeout=10) as response:
        for _ in range(10):
            line = response.readline().decode("utf-8").strip()
            if line.startswith("data:"):
                return json.loads(line.removeprefix("data:"))
    return None


def _positive_number(value: object) -> Decimal | None:
    """A payload field as a positive Decimal, or None for "./.", nulls, zeros."""
    if isinstance(value, str):
        value = value.replace(",", ".")
    try:
        number = Decimal(str(value))
    except ArithmeticError:
        return None
    return number if number > 0 else None


def _fetch_yfinance(ticker: str) -> tuple[Decimal | None, Decimal | None]:
    """Latest close and year-to-date return for one ticker.

    Imported lazily so the app starts (and the test suite runs) without paying
    yfinance's import cost or needing a network.
    """
    import yfinance as yf

    history = yf.Ticker(ticker).history(period="ytd", auto_adjust=False)
    if history is None or history.empty:
        history = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
    if history is None or history.empty:
        return None, None

    closes = history["Close"].dropna()
    if closes.empty:
        return None, None

    last = Decimal(str(float(closes.iloc[-1])))
    first = Decimal(str(float(closes.iloc[0])))
    ytd = round_cents((last - first) / first * 100) if first > 0 else None
    return round_cents(last).quantize(Decimal("0.0001")), ytd



# --------------------------------------------------------------------------
# Historical prices
#
# Only used to reconstruct past net worth (see `services/history.py`), never
# to value anything now — the live path above is unaffected. Deliberately
# uncached: a backfill runs rarely, and `price_quotes` holds one row per
# ticker by design.
# --------------------------------------------------------------------------

ONVISTA_EOD = "https://api.onvista.de/api/v1/instruments/BOND/{entity}/eod_history?range=Y1"


def history_for(ticker: str, start: date, end: date) -> dict[date, Decimal]:
    """Daily closing prices for one holding, keyed by day.

    Days the market was shut are simply absent; callers carry the last known
    price forward. Returns `{}` rather than raising when a source has nothing,
    so one unavailable holding cannot fail an entire reconstruction.
    """
    try:
        if ISIN.match(ticker):
            return _history_isin(ticker, start, end)
        return _history_yfinance(ticker, start, end)
    except Exception:
        log.warning("no price history for %s", ticker, exc_info=True)
        return {}


def _history_yfinance(ticker: str, start: date, end: date) -> dict[date, Decimal]:
    import yfinance as yf

    frame = yf.Ticker(ticker).history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat())
    if frame is None or len(frame) == 0:
        return {}
    return {
        index.date(): round_cents(Decimal(str(row["Close"])))
        for index, row in frame.iterrows()
    }


def _history_isin(isin: str, start: date, end: date) -> dict[date, Decimal]:
    """Bond history from onvista, quoted as percent of face value.

    Matches how such a holding's `quantity` is stored (face value / 100), so
    price × quantity gives a value the same way the live path does. onvista
    keeps roughly a month for these, and returns the same window whatever
    `range` is asked for.
    """
    hits = _get_json(ONVISTA_SEARCH + isin).get("list", [])
    entity = next((h.get("entityValue") for h in hits if h.get("entityValue")), None)
    if entity is None:
        return {}

    payload = _get_json(ONVISTA_EOD.format(entity=entity))
    stamps = payload.get("datetimeLast") or []
    closes = payload.get("last") or []

    history: dict[date, Decimal] = {}
    for stamp, close in zip(stamps, closes):
        day = datetime.fromtimestamp(stamp, timezone.utc).date()
        if start <= day <= end:
            price = _positive_number(close)
            if price is not None:
                history[day] = price
    return history
