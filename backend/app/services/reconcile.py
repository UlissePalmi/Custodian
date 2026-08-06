"""Taking account balances from the bank, and checking the ledger against them.

A balance that accumulates locally cannot track the account it names. Every
transaction's cash effect lands on one account (`networth.get_cash_account`),
so card spending moves the checking balance; and transfers are deliberately
excluded as internal, though each one really does leave checking. Custodian
read $4,023.94 against Chase's $2,729.61 by exactly that route.

So a mapped account's `balance` is simply what the bank says, refreshed every
sync, and transactions no longer move it — they exist to categorise spending.
Accounts Plaid cannot see stay manual and are never touched here.

That removes per-account drift by construction, but not the question worth
asking: *did Custodian record everything that moved?* See `checkpoint` below,
which compares how much banked cash actually changed against how much the
ledger says it should have.
"""

from datetime import datetime, timezone
from decimal import Decimal

from plaid.model.accounts_get_request import AccountsGetRequest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, BalanceCheckpoint, Category, Holding, PlaidItem, Transaction
from app.money import ZERO, round_cents
from app.services.crypto import decrypt_token
from app.services.plaid_client import get_plaid_client

#: Below this, a shift is rounding rather than a missed transaction.
DRIFT_TOLERANCE = Decimal("1.00")


def _plaid_accounts(item: PlaidItem) -> list[dict]:
    """Raw account dicts. The SDK's typed accessors raise on investment
    accounts whose balance fields differ between the base and composed models,
    so the response is read as plain data."""
    response = get_plaid_client().accounts_get(
        AccountsGetRequest(access_token=decrypt_token(item.access_token_encrypted))
    )
    return response.to_dict().get("accounts", [])


def refresh_balances(db: Session) -> int:
    """Records the current bank balance on every mapped account.

    Returns how many were updated. Unmapped accounts — anything Plaid cannot
    see — are left entirely alone.
    """
    mapped = {
        a.plaid_account_id: a
        for a in db.scalars(select(Account).where(Account.plaid_account_id.is_not(None)))
    }
    if not mapped:
        return 0

    now = datetime.now(timezone.utc)
    updated = 0
    for item in db.scalars(select(PlaidItem)).all():
        try:
            accounts = _plaid_accounts(item)
        except Exception:
            continue  # A failing item must not stop the others.
        for raw in accounts:
            account = mapped.get(raw["account_id"])
            if account is None:
                continue
            balances = raw.get("balances") or {}
            current = balances.get("current")
            if current is None:
                continue
            account.plaid_balance = round_cents(Decimal(str(current)))
            account.plaid_balance_as_of = now
            if account.type == "stocks":
                # Uninvested cash only — the positions are `holdings`, and
                # `current` counts both, so taking it here would double them.
                available = balances.get("available")
                if available is not None:
                    account.balance = round_cents(Decimal(str(available)))
            else:
                account.balance = account.plaid_balance
            updated += 1
    db.commit()
    return updated


def _tracked_total(db: Session) -> Decimal:
    """Money in a form that only moves when something real happens.

    Connected cash, minus card debt, plus brokerage cash, plus positions **at
    cost**. Cost rather than market is the point: a price move is not a
    transaction, and buying a share only converts cash into holdings of equal
    value, so neither disturbs this figure. Unconnected accounts are excluded —
    nothing observes them independently, so they cannot corroborate anything.
    """
    from app.services.networth import _fx_ticker
    from app.services.quotes import get_quotes

    accounts = [
        a
        for a in db.scalars(select(Account))
        if a.plaid_account_id is not None
    ]
    fx_tickers = [_fx_ticker(a.currency) for a in accounts if a.currency != "usd"]
    rates = get_quotes(db, fx_tickers) if fx_tickers else {}

    total = ZERO
    for account in accounts:
        balance = account.balance
        if account.currency != "usd":
            rate = rates.get(_fx_ticker(account.currency))
            balance = round_cents(balance * rate.price) if rate is not None else ZERO
        total += -balance if account.type == "credit" else balance

    account_ids = {a.id for a in accounts}
    for holding in db.scalars(select(Holding)):
        if holding.account_id in account_ids:
            total += holding.quantity * holding.cost_basis_per_share
    return round_cents(total)


def _ledger_net(db: Session) -> Decimal:
    """Cumulative income minus expenses Custodian has recorded."""
    rows = db.execute(
        select(Category.kind, func.sum(Transaction.amount))
        .join(Category, Category.id == Transaction.category_id)
        .group_by(Category.kind)
    ).all()
    totals = {kind: amount or ZERO for kind, amount in rows}
    return round_cents(totals.get("income", ZERO) - totals.get("expense", ZERO))


def checkpoint(db: Session) -> BalanceCheckpoint:
    """Records what is held against what was recorded, and returns it."""
    row = BalanceCheckpoint(tracked_total=_tracked_total(db), ledger_net=_ledger_net(db))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def drifts(db: Session, tolerance: Decimal = DRIFT_TOLERANCE) -> list[dict]:
    """Whether the ledger has stopped keeping pace with the money.

    `tracked_total - ledger_net` is a constant offset absorbing everything
    that predates the ledger; its value is meaningless. A *change* in it is
    not: money moved without an entry, or an entry exists for money that never
    moved. Returns a single row when the offset has shifted since the previous
    checkpoint, empty when it held.

    A realised gain or loss on a sale moves it legitimately — the proceeds
    differ from the cost that left the books — so an isolated shift after a
    trade is expected. A persistent one is not.
    """
    recent = list(
        db.scalars(
            select(BalanceCheckpoint).order_by(BalanceCheckpoint.taken_at.desc()).limit(2)
        )
    )
    if len(recent) < 2:
        return []

    latest, previous = recent[0], recent[1]
    offset_now = round_cents(latest.tracked_total - latest.ledger_net)
    offset_before = round_cents(previous.tracked_total - previous.ledger_net)
    shift = round_cents(offset_now - offset_before)
    if abs(shift) <= tolerance:
        return []

    return [
        {
            "unexplained": shift,
            "tracked_change": round_cents(latest.tracked_total - previous.tracked_total),
            "ledger_change": round_cents(latest.ledger_net - previous.ledger_net),
            "since": previous.taken_at,
            "as_of": latest.taken_at,
        }
    ]


def drift_summary(db: Session) -> str | None:
    """One line for the sync log. None when the ledger kept pace."""
    rows = drifts(db)
    if not rows:
        return None
    r = rows[0]
    return (
        f"{r['unexplained']:+} unexplained since {r['since']:%Y-%m-%d %H:%M} "
        f"(balances moved {r['tracked_change']:+}, ledger recorded {r['ledger_change']:+})"
    )
