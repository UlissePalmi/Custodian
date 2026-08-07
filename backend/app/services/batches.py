"""Undoing a batch of automatically-created transactions.

A sync writes its transactions, the cash delta they add up to, and the
affected months' snapshots in one database transaction (see
`services/plaid_sync.py`). This reverses exactly that, using the delta the
batch recorded rather than recomputing it — so an undo moves the cash balance
by the amount that batch actually applied, whatever has happened since.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import ImportBatch, Transaction
from app.months import month_key_from_date
from app.services import networth


def delete_batch(db: Session, batch_id: str) -> None:
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise ApiError("Import batch not found.", 404)

    # A batch's transactions can span more than one month, so every month they
    # touched needs its snapshot recomputed below — not just the batch's one
    # "primary" month_key.
    month_keys = {
        month_key_from_date(d)
        for d in db.scalars(
            select(Transaction.date).where(Transaction.import_batch_id == batch_id)
        )
    }

    # Bulk delete, flushed before the batch row goes: the ORM has no
    # relationship between the two tables and would otherwise be free to drop
    # the batch first and let the database's cascade do this implicitly.
    db.execute(delete(Transaction).where(Transaction.import_batch_id == batch_id))
    db.flush()

    networth.apply_cash_effect(db, -batch.cash_delta)

    db.delete(batch)
    db.flush()

    for month_key in month_keys:
        networth.upsert_snapshot(db, month_key)
    db.commit()
