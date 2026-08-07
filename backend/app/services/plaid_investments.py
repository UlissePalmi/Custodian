"""Plaid investments sync — keeps brokerage positions current.

Separate from `plaid_sync.py` because holdings are a *state*, not a stream of
events: Plaid reports what the account contains right now, so each run
replaces the synced positions rather than appending to them. That is what
makes a sell disappear and a re-buy reappear without any reconciliation
logic.

Only positions Plaid can see are touched. Anything held where Plaid has no
visibility stays `source='manual'` and is left alone — see `models/holding.py`.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.model.investments_refresh_request import InvestmentsRefreshRequest
from plaid.model.investments_transactions_get_request import InvestmentsTransactionsGetRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Account, Holding, PlaidItem
from app.money import ZERO
from app.services.crypto import decrypt_token
from app.services.plaid_client import get_plaid_client

log = logging.getLogger(__name__)

#: Plaid security types that are positions rather than balances. Cash-like
#: rows (a sweep fund, an unsettled negative balance) describe money sitting
#: in the account, not something held, and have no ticker the price feed could
#: quote — they are skipped rather than invented as holdings.
_POSITION_TYPES = {"equity", "etf", "mutual fund", "fixed income", "derivative"}


def get_brokerage_account(db: Session) -> Account:
    """The account synced positions belong to. Single-user app, so the first
    stocks-type account is the only one that matters."""
    account = db.scalar(select(Account).where(Account.type == "stocks").order_by(Account.id))
    if account is None:
        raise ApiError("No brokerage account is configured — run the seed script.", 422)
    return account


def _cost_per_share(cost_basis, quantity: Decimal) -> Decimal:
    """Plaid reports cost basis for the whole position; Custodian stores it
    per share. Missing basis is recorded as zero rather than guessed."""
    if cost_basis is None or quantity == 0:
        return ZERO
    try:
        return (Decimal(str(cost_basis)) / quantity).quantize(Decimal("0.0001"))
    except (InvalidOperation, ZeroDivisionError):
        return ZERO


def _first_bought(item: PlaidItem) -> dict[str, date]:
    """Earliest purchase date per security, from the brokerage's own history.

    Recorded so past net worth can tell when a position was actually held:
    before it was bought that money was cash, which does not move with the
    stock's price. Positions acquired before Plaid's window simply have no buy
    to find, and are treated as held throughout — which is what they were.
    """
    try:
        response = get_plaid_client().investments_transactions_get(
            InvestmentsTransactionsGetRequest(
                access_token=decrypt_token(item.access_token_encrypted),
                start_date=date.today() - timedelta(days=730),
                end_date=date.today(),
            )
        )
    except Exception:
        return {}

    earliest: dict[str, date] = {}
    for txn in response.investment_transactions:
        if str(getattr(txn, "type", "")).lower() != "buy":
            continue
        security_id = getattr(txn, "security_id", None)
        if security_id is None:
            continue
        if security_id not in earliest or txn.date < earliest[security_id]:
            earliest[security_id] = txn.date
    return earliest


def _request_refresh(access_token: str) -> None:
    """Asks Plaid to re-fetch positions from the institution.

    Holdings are not pulled on demand the way transactions are: without this,
    `investments_holdings_get` serves whatever Plaid last happened to collect,
    which can be a day or more stale and silently omits trades made since. It
    is a hint rather than a guarantee — Plaid answers immediately and updates
    behind the scenes — so the read below may still return the previous view
    and pick the trade up on the following run. Best-effort: an institution
    that does not support it must not fail the sync.
    """
    try:
        get_plaid_client().investments_refresh(
            InvestmentsRefreshRequest(access_token=access_token)
        )
    except Exception:
        log.info("investments refresh unavailable for this item", exc_info=True)


def sync_holdings(db: Session, item: PlaidItem) -> int:
    """Replaces this item's synced positions with what Plaid reports now.

    Returns the number of positions held after the sync. Items at institutions
    with no investment accounts simply report none, which correctly clears any
    positions that were there before.
    """
    client = get_plaid_client()
    access_token = decrypt_token(item.access_token_encrypted)
    _request_refresh(access_token)
    response = client.investments_holdings_get(
        InvestmentsHoldingsGetRequest(access_token=access_token)
    )

    securities = {s.security_id: s for s in response.securities}
    bought_on = _first_bought(item)
    account = get_brokerage_account(db)

    existing = {
        h.plaid_security_id: h
        for h in db.scalars(
            select(Holding).where(Holding.source == "plaid", Holding.account_id == account.id)
        )
        if h.plaid_security_id
    }
    seen: set[str] = set()

    for holding in response.holdings:
        security = securities.get(holding.security_id)
        if security is None:
            continue
        security_type = (security.type or "").lower()
        ticker = (security.ticker_symbol or "").strip().upper()
        # No ticker means nothing the price feed can quote; a cash-like row is
        # a balance rather than a position.
        if security_type not in _POSITION_TYPES or not ticker:
            continue

        quantity = Decimal(str(holding.quantity))
        row = existing.get(holding.security_id)
        if row is None:
            row = Holding(
                account_id=account.id,
                source="plaid",
                plaid_security_id=holding.security_id,
            )
            db.add(row)
        row.ticker = ticker
        row.name = (security.name or ticker)[:200]
        row.quantity = quantity
        row.cost_basis_per_share = _cost_per_share(holding.cost_basis, quantity)
        # Only ever filled in, never overwritten: a hand-entered date is the
        # better record, and a position bought before Plaid's window has none.
        if row.purchase_date is None:
            row.purchase_date = bought_on.get(holding.security_id)
        seen.add(holding.security_id)

    # Anything previously synced and no longer reported has been sold.
    for security_id, row in existing.items():
        if security_id not in seen:
            db.delete(row)

    db.commit()
    return len(seen)


#: Not failures: an item linked without investments consent, or at an
#: institution that has no brokerage, simply has no positions to report.
#: Flagging these would leave a permanent error badge on a healthy connection.
_NO_INVESTMENTS = (
    "ADDITIONAL_CONSENT_REQUIRED",
    "PRODUCTS_NOT_SUPPORTED",
    "PRODUCT_NOT_ENABLED",
    "NO_INVESTMENT_ACCOUNTS",
)


def _is_missing_investments(exc: Exception) -> bool:
    body = str(getattr(exc, "body", "") or exc)
    return any(code in body for code in _NO_INVESTMENTS)


def sync_all_holdings(db: Session) -> int:
    """Syncs positions for every linked item. One item's failure must not stop
    the others."""
    total = 0
    for item in db.scalars(select(PlaidItem)).all():
        try:
            total += sync_holdings(db, item)
        except Exception as exc:  # Plaid/network failure, recorded not raised.
            db.rollback()
            if _is_missing_investments(exc):
                continue
            item.status = "error"
            item.last_error = str(exc)[:500]
            db.commit()
    return total
