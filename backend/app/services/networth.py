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

from app.errors import ApiError
from app.models import Account, Holding, NetWorthSnapshot, PriceQuote
from app.money import ZERO, percent_of, round_cents
from app.months import compare_month_keys, current_snapshot_month
from app.services.quotes import get_quotes

#: Asset classes the dashboard always shows, even at zero.
BASE_ASSET_CLASSES = ("stocks", "bonds", "cash")

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


def holdings_value_for_account(db: Session, account_id: int) -> Decimal:
    """Market value of one account's positions, for reconciling it against the
    balance the bank reports for the account as a whole."""
    holdings = list(db.scalars(select(Holding).where(Holding.account_id == account_id)))
    if not holdings:
        return ZERO
    quotes = get_quotes(db, [h.ticker for h in holdings])
    total = ZERO
    for holding in holdings:
        price, _ = _price_for(holding, quotes)
        total += holding.quantity * price
    return round_cents(total)


def holdings_value_by_type(db: Session) -> dict[str, Decimal]:
    """Market value of all holdings, grouped by their account's asset class.

    A holding's own account decides its bucket — a stock ETF and a Treasury
    held by ISIN both live in `holdings`, priced the same way, but they
    belong to different asset classes on the dashboard.
    """
    holdings = list(db.scalars(select(Holding)))
    if not holdings:
        return {}
    quotes = get_quotes(db, [h.ticker for h in holdings])
    totals: dict[str, Decimal] = {}
    for holding in holdings:
        price, _ = _price_for(holding, quotes)
        asset_class = holding.account.type
        totals[asset_class] = totals.get(asset_class, ZERO) + holding.quantity * price
    return {asset_class: round_cents(value) for asset_class, value in totals.items()}


def _fx_ticker(currency: str) -> str:
    return f"{currency.upper()}USD=X"


def get_cash_account(db: Session) -> Account:
    """The account any cash-moving write (an import, a manual transaction)
    applies its delta to. Single-user app, so the first cash-type account is
    the only one that matters."""
    account = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    if account is None:
        raise ApiError("No cash account is configured — run the seed script.", 422)
    return account


def apply_cash_effect(db: Session, delta: Decimal) -> None:
    """Moves the cash account by `delta` — unless the bank owns its balance.

    A mapped account's balance is written from Plaid on every sync (see
    `services/reconcile.py`), so nudging it here as well would double-count:
    the transaction is already reflected in the figure the bank reported.
    Accumulating locally is only correct where Plaid cannot see the account,
    which is also the only case where nothing else would record the movement.
    """
    account = get_cash_account(db)
    if account.plaid_account_id is not None:
        return
    account.balance = round_cents(account.balance + delta)


def balances_by_asset_class(db: Session) -> dict[str, Decimal]:
    """Account balances grouped by account type, plus holdings valued at market.

    Non-USD balances are converted through the same cached quote feed used for
    holdings — an account's `currency` just becomes another "ticker" (e.g.
    'EURUSD=X'), so this picks up the delayed-refresh/offline-fallback behavior
    quotes already have for free.

    An account's balance does not always count under its own name. A credit
    account holds what is *owed*, so it nets against cash rather than counting
    as an asset — net worth means assets minus debts. And a stocks account's
    balance is the *uninvested* cash sitting in the brokerage: money that is
    not exposed to the market, so counting it as stocks would overstate that
    exposure. It counts as cash, while the account's positions come from
    `holdings` and count as stocks.
    """
    accounts = list(db.scalars(select(Account)))
    fx_tickers = [_fx_ticker(a.currency) for a in accounts if a.currency != "usd"]
    fx_rates = get_quotes(db, fx_tickers) if fx_tickers else {}

    totals: dict[str, Decimal] = {asset_class: ZERO for asset_class in BASE_ASSET_CLASSES}
    for account in accounts:
        balance = account.balance
        if account.currency != "usd":
            rate = fx_rates.get(_fx_ticker(account.currency))
            balance = round_cents(balance * rate.price) if rate is not None else ZERO
        if account.type == "credit":
            totals["cash"] = round_cents(totals["cash"] - balance)
            continue
        if account.type == "stocks":
            totals["cash"] = round_cents(totals["cash"] + balance)
            continue
        totals[account.type] = round_cents(totals.get(account.type, ZERO) + balance)
    for asset_class, value in holdings_value_by_type(db).items():
        totals[asset_class] = round_cents(totals.get(asset_class, ZERO) + value)
    return totals


def accounts_breakdown(db: Session) -> list[dict]:
    """Every account, what it is worth in USD, and what it holds.

    Deliberately mirrors `balances_by_asset_class`'s rules rather than
    inventing its own — a credit account counts negative, and a stocks
    account is its uninvested cash *plus* its positions — so this page and the
    dashboard can never disagree about the total.

    Quotes and FX rates are fetched in one batch each: valuing accounts by
    calling `holdings_value_for_account` in a loop would issue a request per
    account.
    """
    accounts = list(db.scalars(select(Account).order_by(Account.id)))
    holdings = list(db.scalars(select(Holding)))

    fx_tickers = [_fx_ticker(a.currency) for a in accounts if a.currency != "usd"]
    quotes = get_quotes(db, [h.ticker for h in holdings] + fx_tickers)

    by_account: dict[int, list[dict]] = {}
    for holding in holdings:
        price, as_of = _price_for(holding, quotes)
        by_account.setdefault(holding.account_id, []).append(
            {
                "id": holding.id,
                "ticker": holding.ticker,
                "name": holding.name,
                "quantity": holding.quantity,
                "current_price": price,
                "market_value": round_cents(holding.quantity * price),
                "quote_as_of": as_of,
                "source": holding.source,
            }
        )

    total, _ = compute_totals(db)

    def row(account: Account, asset_class: str, value: Decimal, lines: list[dict]) -> dict:
        return {
            "id": account.id,
            "name": account.name,
            "type": account.type,
            "asset_class": asset_class,
            "currency": account.currency,
            "balance": account.balance,
            "value": value,
            "percent": percent_of(value, total),
            "is_connected": account.plaid_account_id is not None,
            "balance_as_of": account.plaid_balance_as_of,
            "holdings": lines,
        }

    rows = []
    for account in accounts:
        balance = account.balance
        if account.currency != "usd":
            rate = quotes.get(_fx_ticker(account.currency))
            balance = round_cents(balance * rate.price) if rate is not None else ZERO

        lines = sorted(by_account.get(account.id, []), key=lambda h: h["ticker"])
        holdings_value = round_cents(sum((h["market_value"] for h in lines), ZERO))

        if account.type == "credit":
            # What is owed counts against net worth, and against cash.
            rows.append(row(account, "cash", round_cents(-balance), []))
        elif account.type == "stocks":
            # Split the way the allocation does: positions are market
            # exposure, the uninvested balance is not. One account, two rows,
            # so the page's groups and the dashboard's slices agree.
            rows.append(row(account, "stocks", holdings_value, lines))
            if balance != 0:
                rows.append(row(account, "cash", balance, []))
        else:
            rows.append(row(account, account.type, round_cents(balance + holdings_value), lines))
    return rows


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
