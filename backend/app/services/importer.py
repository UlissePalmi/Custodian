"""Chase import: preview, confirm, and undo.

Confirming is the one place where the ledger and net worth move together. It
runs as a single database transaction: the batch row, its transactions, the
cash balance and the month's snapshot all land or none of them do. The batch id
is the batch table's primary key, so a repeated confirm collides instead of
double-counting.
"""

import re
import secrets

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Account, Category, ChaseCategoryMap, ImportBatch, Transaction
from app.money import ZERO, round_cents
from app.months import (
    LEDGER_START,
    compare_month_keys,
    current_snapshot_month,
    is_within_ledger_range,
    month_key_from_date,
    to_month_key,
)
from app.schemas.chase import ImportPreview
from app.schemas.ledger import TransactionInput
from app.services import networth
from app.services.chase_parser import ParsedRow, dominant_month, parse_chase_file
from app.services.ledger import create_transaction

ACCEPTED_EXTENSIONS = (".csv", ".xls", ".xlsx")

FALLBACK_EXPENSE_CATEGORY_ID = "cat-other"
FALLBACK_INCOME_CATEGORY_ID = "cat-main-income"

_FILENAME_MONTH = re.compile(r"(20\d{2})[-_.]?(0[1-9]|1[0-2])")


# --------------------------------------------------------------------------
# Preview
# --------------------------------------------------------------------------


def _month_from_filename(filename: str) -> str | None:
    match = _FILENAME_MONTH.search(filename)
    if not match:
        return None
    key = to_month_key(int(match.group(1)), int(match.group(2)))
    return key if is_within_ledger_range(key) else None


def _detect_month(rows: list[ParsedRow], filename: str, hint: str | None) -> str:
    """Statement month, most trustworthy source first."""
    from_rows = dominant_month(rows)
    if from_rows and is_within_ledger_range(from_rows):
        return from_rows
    from_name = _month_from_filename(filename)
    if from_name:
        return from_name
    if hint and is_within_ledger_range(hint):
        return hint
    return current_snapshot_month()


def _category_lookup(db: Session) -> tuple[dict[str, str], dict[str, str]]:
    """Chase category -> Custodian id, and Custodian id -> kind."""
    mapping = {
        row.chase_category.strip().lower(): row.category_id
        for row in db.scalars(select(ChaseCategoryMap))
    }
    kinds = {c.id: c.kind for c in db.scalars(select(Category))}
    return mapping, kinds


def _propose_category(
    row: ParsedRow, mapping: dict[str, str], kinds: dict[str, str]
) -> tuple[str, bool]:
    """Category for a parsed row, plus whether it needs a human look.

    The category decides the transaction's direction on our side, so a mapping
    is only usable when its kind agrees with the direction the parser read off
    the file — otherwise a refund tagged "Groceries" would be filed as an
    expense while carrying a positive amount.
    """
    mapped = mapping.get(row.chase_category.strip().lower())
    if mapped and kinds.get(mapped) == row.kind:
        return mapped, False

    fallback = FALLBACK_INCOME_CATEGORY_ID if row.kind == "income" else FALLBACK_EXPENSE_CATEGORY_ID
    return fallback, True


def build_preview(
    db: Session, content: bytes, filename: str, hint_month_key: str | None = None
) -> dict:
    if not filename.lower().endswith(ACCEPTED_EXTENSIONS):
        raise ApiError("Please upload a Chase export as .csv, .xls or .xlsx.", 415)
    if not content:
        raise ApiError("That file is empty.", 422)

    rows = parse_chase_file(content, filename)
    detected_month_key = _detect_month(rows, filename, hint_month_key)
    mapping, kinds = _category_lookup(db)

    transactions = []
    for index, row in enumerate(rows, start=1):
        category_id, flagged = _propose_category(row, mapping, kinds)
        # Nothing before the ledger opens can ever be stored, so such rows come
        # back unticked rather than failing at confirm time.
        too_old = compare_month_keys(month_key_from_date(row.date), LEDGER_START) < 0
        transactions.append(
            {
                "id": f"preview-{index}",
                "date": row.date,
                "amount": row.amount,
                "description": row.description,
                "chase_category": row.chase_category,
                "category_id": category_id,
                "kind": row.kind,
                "flagged_for_review": flagged or too_old,
                "include": not too_old,
            }
        )

    return {
        "batch_id": f"batch-{secrets.token_hex(6)}",
        "file_name": filename,
        "detected_month_key": detected_month_key,
        "transactions": transactions,
    }


# --------------------------------------------------------------------------
# Confirm
# --------------------------------------------------------------------------


def _cash_account(db: Session) -> Account:
    account = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    if account is None:
        raise ApiError("No cash account is configured — run the seed script.", 422)
    return account


def confirm_import(db: Session, preview: ImportPreview) -> dict:
    if db.get(ImportBatch, preview.batch_id) is not None:
        raise ApiError("This import has already been confirmed.", 409)
    if not is_within_ledger_range(preview.detected_month_key):
        raise ApiError(f"{preview.detected_month_key} is outside the ledger range.", 422)

    included = [t for t in preview.transactions if t.include]
    if not included:
        raise ApiError("No transactions selected to import.", 422)

    kinds = {c.id: c.kind for c in db.scalars(select(Category))}

    batch = ImportBatch(
        batch_id=preview.batch_id,
        file_name=preview.file_name,
        month_key=preview.detected_month_key,
        cash_delta=ZERO,
        imported_count=len(included),
    )
    db.add(batch)
    db.flush()  # Claims the batch id before any transaction is written.

    cash_delta = ZERO
    for row in included:
        create_transaction(
            db,
            month_key_from_date(row.date),
            TransactionInput(
                date=row.date,
                amount=float(row.amount),
                description=row.description,
                category_id=row.category_id,
            ),
            source="chase_import",
            import_batch_id=batch.batch_id,
            commit=False,
        )
        # Direction comes from the stored category, so the cash movement always
        # agrees with what the ledger will show.
        if kinds.get(row.category_id) == "income":
            cash_delta += row.amount
        else:
            cash_delta -= row.amount

    cash_delta = round_cents(cash_delta)
    batch.cash_delta = cash_delta

    account = _cash_account(db)
    account.balance = round_cents(account.balance + cash_delta)

    total = networth.upsert_snapshot(db, preview.detected_month_key)
    db.commit()

    return {
        "batch_id": batch.batch_id,
        "month_key": batch.month_key,
        "imported_count": batch.imported_count,
        "cash_delta": cash_delta,
        "new_net_worth_total": total,
    }


def delete_batch(db: Session, batch_id: str) -> None:
    """Undoes a confirmed import, reversing the exact cash delta it applied."""
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise ApiError("Import batch not found.", 404)

    # Bulk delete, flushed before the batch row goes: the ORM has no
    # relationship between the two tables and would otherwise be free to drop
    # the batch first and let the database's cascade do this implicitly.
    db.execute(delete(Transaction).where(Transaction.import_batch_id == batch_id))
    db.flush()

    account = _cash_account(db)
    account.balance = round_cents(account.balance - batch.cash_delta)

    month_key = batch.month_key
    db.delete(batch)
    db.flush()

    networth.upsert_snapshot(db, month_key)
    db.commit()
