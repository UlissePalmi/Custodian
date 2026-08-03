"""Shared duplicate-detection for anything that lands transactions in the ledger.

Both the Chase upload path and the Plaid sync path need to recognise "this
transaction is already in the ledger, however it got there" — a manual entry
blocks a duplicate Chase import just as much as an earlier Plaid sync would,
and vice versa. One implementation, so the two paths can't drift apart.
"""

from collections import Counter
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Transaction


def natural_key(txn_date: date, description: str, amount: Decimal, kind: str) -> tuple:
    return (txn_date, description.strip().lower(), amount, kind)


def existing_transaction_counts(db: Session, dates: list[date]) -> Counter:
    """Counts of (date, description, amount, kind) already in the ledger,
    across every source, for transactions dated within `dates`' range.

    Counted rather than a plain set, so two genuinely repeated transactions
    (e.g. two identical coffees on the same day) aren't both treated as
    duplicates when only one of them is actually already in the ledger.
    """
    if not dates:
        return Counter()
    existing = db.execute(
        select(Transaction.date, Transaction.description, Transaction.amount, Category.kind)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.date >= min(dates), Transaction.date <= max(dates))
    ).all()
    return Counter(natural_key(*row) for row in existing)
