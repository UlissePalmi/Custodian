"""Plaid transaction sync — auto-applies new bank transactions to the ledger.

Transactions post straight to the ledger with no review step. The batch,
the transactions, the cash delta they add up to and every touched month's
snapshot land in one database transaction, so a failure part-way leaves
nothing behind; `services/batches.delete_batch` reverses the lot.
"""

import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from plaid.model.transactions_sync_request import TransactionsSyncRequest
from sqlalchemy import select
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Session

from app.models import Category, ImportBatch, PlaidCategoryMap, PlaidItem, Transaction
from app.money import ZERO, round_cents
from app.months import is_within_ledger_range, month_key_from_date
from app.schemas.imports import ImportResult
from app.schemas.ledger import TransactionInput
from app.services import networth
from app.services.crypto import decrypt_token
from app.services.dedup import existing_transaction_counts, natural_key
from app.services.ledger import create_transaction
from app.services.plaid_client import get_plaid_client

#: Where a transaction lands when Plaid's category has no mapping, or has one
#: whose direction contradicts the amount's sign.
FALLBACK_EXPENSE_CATEGORY_ID = "cat-other"
FALLBACK_INCOME_CATEGORY_ID = "cat-main-income"


@dataclass
class _PlaidRow:
    transaction_id: str
    account_id: str
    date: date
    description: str
    #: Plaid's convention: positive = money leaving the account (expense),
    #: negative = money entering (income/refund) — the opposite of Custodian's
    #: "amount always positive, direction from category".
    amount: Decimal
    plaid_category: str | None


def _fetch_added(item: PlaidItem) -> tuple[list[_PlaidRow], str]:
    """Pages through /transactions/sync. Returns non-pending added rows and the new cursor."""
    client = get_plaid_client()
    access_token = decrypt_token(item.access_token_encrypted)
    cursor = item.cursor
    rows: list[_PlaidRow] = []
    while True:
        # The cursor is omitted (not sent as null) on the very first sync, per
        # Plaid's contract for a brand-new Item.
        request_kwargs = {"access_token": access_token}
        if cursor:
            request_kwargs["cursor"] = cursor
        response = client.transactions_sync(TransactionsSyncRequest(**request_kwargs))
        for txn in response.added:
            if txn.pending:
                continue
            category = (
                txn.personal_finance_category.primary
                if getattr(txn, "personal_finance_category", None)
                else None
            )
            rows.append(
                _PlaidRow(
                    transaction_id=txn.transaction_id,
                    account_id=txn.account_id,
                    date=txn.date,
                    description=txn.name,
                    amount=Decimal(str(txn.amount)),
                    plaid_category=category,
                )
            )
        cursor = response.next_cursor
        if not response.has_more:
            break
    return rows, cursor


def _category_lookup(db: Session) -> tuple[dict[str, str], dict[str, str]]:
    """Plaid category -> Custodian id, and Custodian id -> kind."""
    mapping = {row.plaid_category: row.category_id for row in db.scalars(select(PlaidCategoryMap))}
    kinds = {c.id: c.kind for c in db.scalars(select(Category))}
    return mapping, kinds


def _propose(row: _PlaidRow, mapping: dict[str, str], kinds: dict[str, str]) -> tuple[str, str]:
    """Category id + kind for a Plaid row.

    The amount's sign decides direction, and is authoritative: nothing reviews
    these before they land, so a mapping whose kind contradicts the sign would
    silently file a refund as spending. A mapped category is therefore only
    trusted when its kind agrees; otherwise the row falls back to a category
    of the right direction. The mapping picks the bucket, never the direction.
    """
    kind = "expense" if row.amount > 0 else "income"
    mapped = mapping.get(row.plaid_category) if row.plaid_category else None
    if mapped and kinds.get(mapped) == kind:
        return mapped, kind
    return (FALLBACK_EXPENSE_CATEGORY_ID if kind == "expense" else FALLBACK_INCOME_CATEGORY_ID), kind


#: Plaid categories that describe money moving rather than being earned or
#: spent. Only these are eligible to be paired off as internal transfers.
#: A card payment arrives as LOAN_PAYMENTS on the funding account and
#: LOAN_DISBURSEMENTS on the card — both halves must be listed here, or the
#: pair is never recognised.
_TRANSFER_CATEGORIES = {
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "LOAN_PAYMENTS",
    "LOAN_DISBURSEMENTS",
}

#: How far apart the two halves of one transfer may post. A card payment
#: usually clears the same day, but can straddle a weekend.
_TRANSFER_WINDOW_DAYS = 3


def _drop_internal_transfers(rows: list[_PlaidRow]) -> list[_PlaidRow]:
    """Removes transfers between two accounts the user has linked.

    When both a checking account and a card are connected, a card payment
    arrives twice — leaving checking and landing on the card — and counting
    both inflates income *and* expenses by the same amount while the itemised
    card purchases are already in the ledger.

    Only *matched pairs* are dropped, which is what makes this correct rather
    than merely tidy: a payment to a card that isn't linked has no visible
    purchases behind it, so that payment is the only record of the spending
    and must stay. Likewise an incoming transfer with no matching outgoing is
    real money arriving. Both survive here; only the genuine double-entries go.

    A transfer whose other half sits in an account that was never linked (a
    brokerage, say) cannot be recognised and stays in the ledger.
    """
    candidates = [
        i
        for i, r in enumerate(rows)
        if r.plaid_category in _TRANSFER_CATEGORIES and r.amount != 0
    ]
    dropped: set[int] = set()

    for i in candidates:
        if i in dropped:
            continue
        for j in candidates:
            if j <= i or j in dropped:
                continue
            a, b = rows[i], rows[j]
            # Opposite directions, same magnitude, close in time, and — the
            # part that makes this a transfer rather than a coincidence —
            # sitting in two different linked accounts.
            if a.account_id == b.account_id:
                continue
            if a.amount != -b.amount:
                continue
            if abs((a.date - b.date).days) > _TRANSFER_WINDOW_DAYS:
                continue
            dropped.update({i, j})
            break

    return [r for i, r in enumerate(rows) if i not in dropped]


def _unwind_stored_transaction(db: Session, txn: Transaction) -> str:
    """Removes a transaction that turned out to be half of a transfer.

    Its batch's `cash_delta` and `imported_count` are corrected as it goes:
    `services/batches.delete_batch` reverses a batch using that stored delta,
    so leaving it describing a transaction that no longer exists would make a
    later undo move the cash balance by the wrong amount.

    Returns the month key that needs its snapshot recomputed.
    """
    month_key = month_key_from_date(txn.date)
    effect = txn.amount if txn.category.kind == "income" else -txn.amount

    if txn.import_batch_id:
        batch = db.get(ImportBatch, txn.import_batch_id)
        if batch is not None:
            batch.cash_delta = round_cents(batch.cash_delta - effect)
            batch.imported_count = max(0, batch.imported_count - 1)

    account = networth.get_cash_account(db)
    account.balance = round_cents(account.balance - effect)

    db.delete(txn)
    db.flush()
    return month_key


def _pair_against_ledger(db: Session, rows: list[_PlaidRow]) -> tuple[list[_PlaidRow], set[str]]:
    """Drops transfer rows whose other half is already in the ledger.

    `_drop_internal_transfers` only sees one sync's worth of rows, which is
    enough when both halves live at the same institution (one Plaid item, one
    fetch). Across institutions they arrive in separate syncs — and linking a
    new card replays its whole history at once, so its credits land long after
    the matching payments were stored. Those stored halves are removed here.

    Returns the surviving rows and the months whose snapshots went stale.
    """
    kept: list[_PlaidRow] = []
    touched_months: set[str] = set()
    consumed: set[int] = set()

    for row in rows:
        if row.plaid_category not in _TRANSFER_CATEGORIES or row.amount == 0:
            kept.append(row)
            continue

        amount = round_cents(abs(row.amount))
        # Plaid's sign is money-out-positive; the counterpart moved the other
        # way, so it is stored under the opposite kind.
        counterpart_kind = "income" if row.amount > 0 else "expense"

        match = db.scalars(
            select(Transaction)
            .join(Category, Category.id == Transaction.category_id)
            .where(
                Transaction.source == "plaid",
                Transaction.plaid_category.in_(_TRANSFER_CATEGORIES),
                Transaction.plaid_account_id != row.account_id,
                Transaction.amount == amount,
                Transaction.date >= row.date - timedelta(days=_TRANSFER_WINDOW_DAYS),
                Transaction.date <= row.date + timedelta(days=_TRANSFER_WINDOW_DAYS),
                Transaction.id.notin_(consumed) if consumed else sa_true(),
                Category.kind == counterpart_kind,
            )
            .order_by(Transaction.id)
        ).first()

        if match is None:
            kept.append(row)
            continue

        consumed.add(match.id)
        touched_months.add(_unwind_stored_transaction(db, match))

    return kept, touched_months


def sync_item(db: Session, item: PlaidItem) -> ImportResult | None:
    """Pulls new transactions for one linked item and posts them to the ledger.

    Returns `None` when there was nothing new to apply. One commit covers the
    batch, its transactions, the cash delta, every touched month's snapshot
    and the advanced sync cursor together — a crash mid-run leaves the cursor
    unmoved, so the next run safely re-fetches the same page instead of
    skipping it.
    """
    rows, cursor = _fetch_added(item)

    already_synced = {
        plaid_id
        for plaid_id in db.scalars(
            select(Transaction.plaid_transaction_id).where(
                Transaction.plaid_transaction_id.in_([r.transaction_id for r in rows])
            )
        )
    }
    rows = [r for r in rows if r.transaction_id not in already_synced]
    rows = [r for r in rows if is_within_ledger_range(month_key_from_date(r.date))]
    # Before categorising: a matched transfer pair must never reach the ledger
    # as an income/expense entry at all.
    rows = _drop_internal_transfers(rows)
    # Then against transfers already stored — the other half may have arrived
    # in an earlier sync, from a different linked institution.
    rows, unwound_months = _pair_against_ledger(db, rows)

    mapping, kinds = _category_lookup(db)
    remaining_existing = existing_transaction_counts(db, [r.date for r in rows])

    accepted: list[tuple[_PlaidRow, str, str]] = []
    for row in rows:
        category_id, kind = _propose(row, mapping, kinds)
        amount = round_cents(abs(row.amount))
        key = natural_key(row.date, row.description, amount, kind)
        if remaining_existing[key] > 0:
            remaining_existing[key] -= 1
            continue
        accepted.append((row, category_id, kind))

    if not accepted:
        # Nothing new to add, but unwinding a stored transfer still moved cash
        # and invalidated that month's snapshot.
        for month_key in sorted(unwound_months):
            networth.upsert_snapshot(db, month_key)
        item.cursor = cursor
        item.last_synced_at = datetime.now(timezone.utc)
        item.status = "active"
        item.last_error = None
        db.commit()
        return None

    batch = ImportBatch(
        batch_id=f"plaid-{secrets.token_hex(8)}",
        file_name=f"Plaid sync — {item.institution_name} — {date.today().isoformat()}",
        month_key=month_key_from_date(accepted[0][0].date),
        cash_delta=ZERO,
        imported_count=len(accepted),
        source="plaid",
        plaid_item_id=item.item_id,
    )
    db.add(batch)
    db.flush()  # Claims the batch id before any transaction is written.

    cash_delta = ZERO
    month_keys: set[str] = set()
    for row, category_id, kind in accepted:
        month_key = month_key_from_date(row.date)
        month_keys.add(month_key)
        amount = round_cents(abs(row.amount))
        create_transaction(
            db,
            month_key,
            TransactionInput(date=row.date, amount=float(amount), description=row.description, category_id=category_id),
            source="plaid",
            import_batch_id=batch.batch_id,
            plaid_transaction_id=row.transaction_id,
            plaid_category=row.plaid_category,
            plaid_account_id=row.account_id,
            commit=False,
        )
        cash_delta += amount if kind == "income" else -amount

    cash_delta = round_cents(cash_delta)
    batch.cash_delta = cash_delta

    account = networth.get_cash_account(db)
    account.balance = round_cents(account.balance + cash_delta)

    total = ZERO
    # Unwound months too: removing a stored transfer changed their totals.
    for month_key in sorted(month_keys | unwound_months):
        total = networth.upsert_snapshot(db, month_key)

    item.cursor = cursor
    item.last_synced_at = datetime.now(timezone.utc)
    item.status = "active"
    item.last_error = None
    db.commit()

    return ImportResult(
        batch_id=batch.batch_id,
        month_key=batch.month_key,
        imported_count=len(accepted),
        cash_delta=cash_delta,
        new_net_worth_total=total,
    )


def sync_all_items(db: Session) -> list[ImportResult]:
    """Syncs every linked item. One item's failure doesn't stop the others."""
    results = []
    for item in db.scalars(select(PlaidItem)).all():
        try:
            result = sync_item(db, item)
            if result is not None:
                results.append(result)
        except Exception as exc:  # Plaid SDK/network failure — recorded, not raised.
            db.rollback()
            item.status = "error"
            item.last_error = str(exc)[:500]
            db.commit()
    return results
