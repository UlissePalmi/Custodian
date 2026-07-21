"""Delayed price feed.

Quotes are refreshed lazily: a read checks the cache's age and only calls out
when it is stale and the market is plausibly open. Every failure path falls
back to the cached row with its real `as_of`, so an offline Pi shows slightly
old prices rather than an error — the front end displays the timestamp.
"""

import logging
import threading
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Holding, PriceQuote
from app.money import round_cents

log = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(16, 30)

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


def get_quotes(db: Session, tickers: list[str]) -> dict[str, PriceQuote]:
    """Cached quotes for `tickers`, refreshed first if stale."""
    if not tickers:
        return {}

    wanted = sorted({t.upper() for t in tickers})
    cached = {q.ticker: q for q in db.scalars(select(PriceQuote).where(PriceQuote.ticker.in_(wanted)))}
    now = datetime.now(timezone.utc)

    stale = [t for t in wanted if _is_stale(cached.get(t), now)]
    never_fetched = [t for t in wanted if t not in cached]

    # Outside market hours the cache is good enough, unless we have never seen
    # the ticker at all and have nothing to show.
    if stale and (_near_market_hours(now) or never_fetched):
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


def held_tickers(db: Session) -> list[str]:
    return sorted({t for t in db.scalars(select(Holding.ticker))})
