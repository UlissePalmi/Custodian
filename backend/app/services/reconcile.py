"""Comparing the ledger's running balance against what the bank reports.

Custodian's `Account.balance` moves by every transaction it records, starting
from whatever it was set to. The bank's balance is the truth. Keeping only the
first means silent drift; keeping only the second throws away the check —
because the *gap between them* is the one thing that reveals a transaction
that was missed, double-counted, or dated wrongly.

So both are stored and neither overwrites the other. This module records what
the bank says and reports where the two disagree.

The exception is a brokerage's uninvested cash: no transaction ever moves it,
so there is no ledger-side figure to preserve and it is simply taken from the
bank.
"""

from datetime import datetime, timezone
from decimal import Decimal

from plaid.model.accounts_get_request import AccountsGetRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, PlaidItem
from app.money import ZERO, round_cents
from app.services.crypto import decrypt_token
from app.services.plaid_client import get_plaid_client

#: Below this, a difference is rounding or a quote moving, not a missed
#: transaction. Worth a dollar of slack rather than crying wolf daily.
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
                # Uninvested cash only; the positions are `holdings`. Nothing
                # in the ledger tracks this, so there is no local figure worth
                # preserving against it.
                available = balances.get("available")
                if available is not None:
                    account.balance = round_cents(Decimal(str(available)))
            elif account.type == "credit":
                # What is owed is a state the bank reports, not something the
                # ledger accumulates: card purchases are recorded as spending
                # and the payment that clears them is excluded as a transfer,
                # so nothing here would ever add up to a balance.
                account.balance = account.plaid_balance
            updated += 1
    db.commit()
    return updated


def drifts(db: Session, tolerance: Decimal = DRIFT_TOLERANCE) -> list[dict]:
    """Mapped accounts whose ledger balance disagrees with the bank's.

    A stocks account is compared whole — uninvested cash plus positions at
    market — since the bank reports the account's total, not its cash.
    """
    from app.services.networth import holdings_value_for_account

    results = []
    accounts = db.scalars(
        select(Account).where(Account.plaid_account_id.is_not(None)).order_by(Account.id)
    )
    for account in accounts:
        if account.plaid_balance is None:
            continue
        ours = account.balance
        if account.type == "stocks":
            ours = round_cents(ours + holdings_value_for_account(db, account.id))
        difference = round_cents(ours - account.plaid_balance)
        if abs(difference) <= tolerance:
            continue
        results.append(
            {
                "account_id": account.id,
                "name": account.name,
                "type": account.type,
                "ledger_balance": ours,
                "bank_balance": account.plaid_balance,
                "difference": difference,
                "as_of": account.plaid_balance_as_of,
            }
        )
    return results


def drift_summary(db: Session) -> str | None:
    """One line per drifting account, for the sync log. None when all agree."""
    rows = drifts(db)
    if not rows:
        return None
    return "; ".join(
        f"{r['name']}: ledger {r['ledger_balance']} vs bank {r['bank_balance']} "
        f"({r['difference']:+})"
        for r in rows
    )
