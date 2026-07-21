"""Net worth and holdings.

Mirrors the mock's `readNetWorth` / `readHoldings`: nothing aggregate is
stored for the current month. Stored snapshots cover past months only, and the
live point is recomputed from holdings + account balances on every read — which
is why a confirmed import moves the dashboard immediately.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Holding, NetWorthSnapshot, PriceQuote
from app.money import ZERO, percent_of, round_cents
from app.months import compare_month_keys, current_snapshot_month
from app.services.quotes import get_quotes

#: Asset classes the dashboard always shows, even at zero.
BASE_ASSET_CLASSES = ("stocks", "cash", "bonds")

ASSET_CLASS_LABELS = {"stocks": "Stocks", "cash": "Cash", "bonds": "Bonds"}


def _label_for(asset_class: str) -> str:
    return ASSET_CLASS_LABELS.get(asset_class, asset_class.replace("_", " ").title())


def _price_for(holding: Holding, quotes: dict[str, PriceQuote]) -> tuple[Decimal, datetime]:
    """Latest quote for a holding, or its cost basis when we have never fetched one.

    The fallback keeps a fresh offline install renderable: the position shows at
    cost with an obviously old timestamp rather than at zero.
    """
    quote = quotes.get(holding.ticker.upper())
    if quote is None:
        return holding.cost_basis_per_share, datetime.now(timezone.utc) - timedelta(days=1)
    return quote.price, quote.as_of


def read_holdings(db: Session) -> list[dict]:
    holdings = list(db.scalars(select(Holding).order_by(Holding.ticker)))
    quotes = get_quotes(db, [h.ticker for h in holdings])

    result = []
    for holding in holdings:
        price, as_of = _price_for(holding, quotes)
        market_value = round_cents(holding.quantity * price)
        cost_basis = holding.quantity * holding.cost_basis_per_share
        gain = round_cents(market_value - cost_basis)
        quote = quotes.get(holding.ticker.upper())

        result.append(
            {
                "id": holding.id,
                "ticker": holding.ticker,
                "name": holding.name,
                "quantity": holding.quantity,
                "cost_basis_per_share": holding.cost_basis_per_share,
                "current_price": price,
                "quote_as_of": as_of,
                "market_value": market_value,
                "total_return": {
                    "amount": gain,
                    "percent": percent_of(gain, round_cents(cost_basis)),
                },
                "ytd_return_percent": (
                    quote.ytd_return_percent
                    if quote is not None and quote.ytd_return_percent is not None
                    else ZERO
                ),
            }
        )
    return result


def stocks_value(db: Session) -> Decimal:
    holdings = list(db.scalars(select(Holding)))
    if not holdings:
        return ZERO
    quotes = get_quotes(db, [h.ticker for h in holdings])
    total = ZERO
    for holding in holdings:
        price, _ = _price_for(holding, quotes)
        total += holding.quantity * price
    return round_cents(total)


def balances_by_asset_class(db: Session) -> dict[str, Decimal]:
    """Account balances grouped by account type, plus the live stocks value."""
    totals: dict[str, Decimal] = {asset_class: ZERO for asset_class in BASE_ASSET_CLASSES}
    for account in db.scalars(select(Account)):
        if account.type == "stocks":
            # Stocks are valued from their holdings, never from a balance.
            continue
        totals[account.type] = round_cents(totals.get(account.type, ZERO) + account.balance)
    totals["stocks"] = stocks_value(db)
    return totals


def compute_totals(db: Session) -> tuple[Decimal, dict[str, Decimal]]:
    breakdown = balances_by_asset_class(db)
    total = round_cents(sum(breakdown.values(), ZERO))
    return total, breakdown


def read_net_worth(db: Session, today: date | None = None) -> dict:
    today = today or date.today()
    current_month = current_snapshot_month(today)
    total, breakdown = compute_totals(db)

    allocation = [
        {
            "asset_class": asset_class,
            "label": _label_for(asset_class),
            "value": value,
            "percent": percent_of(value, total),
        }
        for asset_class, value in sorted(
            breakdown.items(),
            key=lambda item: (
                BASE_ASSET_CLASSES.index(item[0]) if item[0] in BASE_ASSET_CLASSES else len(BASE_ASSET_CLASSES),
                item[0],
            ),
        )
    ]

    # Stored snapshots for past months; the current month is always live.
    history = [
        {"month_key": snapshot.month_key, "total": snapshot.total}
        for snapshot in db.scalars(select(NetWorthSnapshot).order_by(NetWorthSnapshot.month_key))
        if compare_month_keys(snapshot.month_key, current_month) < 0
    ]
    history.append({"month_key": current_month, "total": total})

    previous = history[-2] if len(history) > 1 else None
    change = None
    if previous is not None and previous["total"] != 0:
        delta = round_cents(total - previous["total"])
        change = {"amount": delta, "percent": percent_of(delta, previous["total"])}

    return {
        "total": total,
        "as_of": today,
        "change_vs_prev_month": change,
        "history": history,
        "allocation": allocation,
    }


def upsert_snapshot(db: Session, month_key: str, today: date | None = None) -> Decimal:
    """Records net worth for `month_key`. Returns the total written."""
    total, breakdown = compute_totals(db)
    snapshot = db.scalar(select(NetWorthSnapshot).where(NetWorthSnapshot.month_key == month_key))
    if snapshot is None:
        snapshot = NetWorthSnapshot(month_key=month_key)
        db.add(snapshot)
    snapshot.as_of = today or date.today()
    snapshot.total = total
    snapshot.breakdown = {key: float(value) for key, value in breakdown.items()}
    db.flush()
    return total
