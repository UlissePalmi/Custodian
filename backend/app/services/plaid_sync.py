"""Plaid transaction sync — auto-applies new bank transactions to the ledger.

No confirm step: bank-sourced data doesn't carry the OCR/parsing risk the
Chase upload path's preview guards against, so this posts straight to the
ledger using the same batch/cash-delta/snapshot mechanics
`services/importer.confirm_import` uses for a Chase import — including reuse
of `services/importer.delete_batch` (unchanged) for undo, since a Plaid sync
writes the same `ImportBatch`/`Transaction` tables.
"""

import secrets
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from plaid.model.transactions_sync_request import TransactionsSyncRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, ImportBatch, PlaidCategoryMap, PlaidItem, Transaction
from app.money import ZERO, round_cents
from app.months import is_within_ledger_range, month_key_from_date
from app.schemas.chase import ImportResult
from app.schemas.ledger import TransactionInput
from app.services import networth
from app.services.crypto import decrypt_token
from app.services.dedup import existing_transaction_counts, natural_key
from app.services.importer import FALLBACK_EXPENSE_CATEGORY_ID, FALLBACK_INCOME_CATEGORY_ID
from app.services.ledger import create_transaction
from app.services.plaid_client import get_plaid_client


@dataclass
class _PlaidRow:
    transaction_id: str
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

    Plaid's amount sign decides direction — it's authoritative here since
    there's no human in the loop to catch a mis-signed category the way the
    Chase preview lets one flag and fix. A mapped category is only trusted
    when its kind agrees with that sign, mirroring
    `importer._propose_category`'s "kind must agree" rule.
    """
    kind = "expense" if row.amount > 0 else "income"
    mapped = mapping.get(row.plaid_category) if row.plaid_category else None
    if mapped and kinds.get(mapped) == kind:
        return mapped, kind
    return (FALLBACK_EXPENSE_CATEGORY_ID if kind == "expense" else FALLBACK_INCOME_CATEGORY_ID), kind


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
            commit=False,
        )
        cash_delta += amount if kind == "income" else -amount

    cash_delta = round_cents(cash_delta)
    batch.cash_delta = cash_delta

    account = networth.get_cash_account(db)
    account.balance = round_cents(account.balance + cash_delta)

    total = ZERO
    for month_key in sorted(month_keys):
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
