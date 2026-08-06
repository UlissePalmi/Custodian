"""Net worth day by day.

Only today's net worth is directly observable — balances are what the bank
says *now*, and holdings are priced at the latest quote. The past has to be
reconstructed, and it can be, because everything that moves net worth is
either recorded or recoverable:

* **recorded income and expenses** — dated daily in the ledger
* **market movement** — real closing prices, fetched per holding
* **transfers** — net to zero across accounts, so they cannot move the total
  and are ignored. Buying a position is the same: cash becomes stock of equal
  value.

So the series is walked backwards from today, which is measured rather than
derived, and each earlier day removes that day's cash flow and price moves.
Ending exactly on today's figure is therefore a property of the arithmetic,
not a coincidence — `backfill` asserts it.

Where a price is missing (a weekend, or before a source's history begins) the
last known price carries backwards. That is exact across closed markets and
approximate only at the very start of the window.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Category, DailyNetWorth, Holding, Transaction
from app.money import ZERO, round_cents
from app.months import LEDGER_START, parse_month_key
from app.services import networth
from app.services.quotes import history_for

log = logging.getLogger(__name__)

#: Where the series begins — the ledger's own start, since nothing before it
#: can be reconstructed from transactions that were never recorded.
_year, _month = parse_month_key(LEDGER_START)
SERIES_START = date(_year, _month, 1)


def _ledger_net_by_day(db: Session) -> dict[date, Decimal]:
    """Income minus expenses recorded against each day."""
    rows = db.execute(
        select(Transaction.date, Category.kind, Transaction.amount).join(
            Category, Category.id == Transaction.category_id
        )
    ).all()
    net: dict[date, Decimal] = {}
    for day, kind, amount in rows:
        effect = amount if kind == "income" else -amount
        net[day] = net.get(day, ZERO) + effect
    return {day: round_cents(value) for day, value in net.items()}


def _price_series(db: Session, start: date, end: date) -> dict[str, dict[date, Decimal]]:
    holdings = list(db.scalars(select(Holding)))
    tickers = {h.ticker for h in holdings}
    # The euro balance is converted through the same feed, as a "ticker".
    if any(a.currency != "usd" for a in db.scalars(select(Account))):
        tickers.add("EURUSD=X")
    return {ticker: history_for(ticker, start, end) for ticker in sorted(tickers)}


def _price_on(series: dict[date, Decimal], day: date, fallback: Decimal) -> Decimal:
    """The close on `day`, or the most recent one before it.

    Markets shut at weekends, and a source's history may start after the
    window does; carrying the last known price forward is what a holding's
    value actually did on those days.
    """
    if not series:
        return fallback
    candidates = [d for d in series if d <= day]
    if candidates:
        return series[max(candidates)]
    # Before any known close — carry the earliest one backwards.
    return series[min(series)]


def _quantity_on(db: Session, holding: Holding, day: date) -> Decimal:
    """How much of a position was held on `day`.

    Positions synced from a brokerage carry no acquisition date, so today's
    quantity is assumed throughout. That is right for the total either way: a
    purchase converts cash into stock of equal value, so the only thing it
    changes is which side of the split the money sits on, and the series
    tracks the total.
    """
    if holding.purchase_date and day < holding.purchase_date:
        return ZERO
    return holding.quantity


def _market_move(
    db: Session,
    day: date,
    holdings: list[Holding],
    prices: dict[str, dict[date, Decimal]],
) -> Decimal:
    """How much prices moved net worth on `day` — and only prices.

    Buying does not change net worth: cash becomes stock of equal value. So a
    position appearing must not be read as a gain, which is why the price
    delta is weighted by the quantity held the day *before*. What a new
    position does contribute is the move from the price paid to that day's
    close, which is a real gain and is added separately.
    """
    total = ZERO
    for holding in holdings:
        series = prices.get(holding.ticker, {})
        previous_quantity = _quantity_on(db, holding, day - timedelta(days=1))
        quantity = _quantity_on(db, holding, day)

        if previous_quantity > 0:
            price_then = _price_on(series, day - timedelta(days=1), holding.cost_basis_per_share)
            price_now = _price_on(series, day, holding.cost_basis_per_share)
            total += previous_quantity * (price_now - price_then)

        bought = quantity - previous_quantity
        if bought > 0:
            price_now = _price_on(series, day, holding.cost_basis_per_share)
            total += bought * (price_now - holding.cost_basis_per_share)

    return round_cents(total)


def reconstruct(db: Session, start: date = SERIES_START, today: date | None = None) -> list[dict]:
    """Net worth for every day from `start` to today, oldest first.

    Today's figure comes from `networth.compute_totals`; each earlier day
    subtracts the cash flow and price movement that happened after it.
    """
    today = today or date.today()
    if start > today:
        return []

    total_today, _ = networth.compute_totals(db)
    holdings = list(db.scalars(select(Holding)))
    prices = _price_series(db, start, today)
    ledger = _ledger_net_by_day(db)

    # Walk backwards accumulating what to undo, then reverse at the end.
    series: list[dict] = [{"day": today, "total": total_today}]
    running = total_today
    day = today
    while day > start:
        previous = day - timedelta(days=1)
        # Undo what happened *on* `day`: the money recorded that day, and the
        # price movement between the previous close and this one.
        running = round_cents(
            running - ledger.get(day, ZERO) - _market_move(db, day, holdings, prices)
        )
        series.append({"day": previous, "total": running})
        day = previous

    series.reverse()
    return series


def record_day(db: Session, day: date | None = None) -> DailyNetWorth:
    """Stores today's net worth as observed, replacing any existing row."""
    day = day or date.today()
    total, breakdown = networth.compute_totals(db)
    row = db.get(DailyNetWorth, day)
    if row is None:
        row = DailyNetWorth(day=day)
        db.add(row)
    row.total = total
    row.breakdown = {key: float(value) for key, value in breakdown.items()}
    db.commit()
    return row


def ensure_days(db: Session, today: date | None = None) -> int:
    """Fills in any day that has no row yet, and refreshes today's.

    Serves both the initial backfill and catching up after the Pi was off, so
    there is only one way a day can come into existence. Returns how many were
    written.
    """
    today = today or date.today()
    existing = {row.day for row in db.scalars(select(DailyNetWorth))}
    missing = [d for d in _days(SERIES_START, today) if d not in existing]
    if not missing and today in existing:
        record_day(db, today)  # today moves, so always refresh it
        return 0

    series = reconstruct(db, SERIES_START, today)
    written = 0
    for point in series:
        if point["day"] in existing and point["day"] != today:
            continue
        row = db.get(DailyNetWorth, point["day"])
        if row is None:
            row = DailyNetWorth(day=point["day"], breakdown={})
            db.add(row)
        row.total = point["total"]
        written += 1
    # Today's breakdown is known exactly rather than reconstructed.
    db.commit()
    record_day(db, today)
    return written


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def read_daily(db: Session) -> list[dict]:
    rows = db.scalars(select(DailyNetWorth).order_by(DailyNetWorth.day))
    return [{"day": row.day, "total": row.total, "breakdown": row.breakdown} for row in rows]
