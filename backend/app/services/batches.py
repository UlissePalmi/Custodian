"""Undoing a batch of automatically-created transactions.

A sync writes its transactions and the cash delta they add up to in one
database transaction (see `services/plaid_sync.py`). This reverses exactly
that, using the delta the batch recorded rather than recomputing it — so an
undo moves the cash balance by the amount that batch actually applied,
whatever has happened since.
"""

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import ImportBatch, Transaction
from app.services import networth


def delete_batch(db: Session, batch_id: str) -> None:
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise ApiError("Import batch not found.", 404)

    # Bulk delete, flushed before the batch row goes: the ORM has no
    # relationship between the two tables and would otherwise be free to drop
    # the batch first and let the database's cascade do this implicitly.
    db.execute(delete(Transaction).where(Transaction.import_batch_id == batch_id))
    db.flush()

    networth.apply_cash_effect(db, -batch.cash_delta)

    db.delete(batch)
    db.flush()

    db.commit()
