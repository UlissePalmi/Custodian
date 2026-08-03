from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

CHASE_IMPORT = "chase_import"
PLAID = "plaid"


class ImportBatch(Base):
    """A confirmed import — from a Chase upload or a Plaid sync.

    The batch id is the primary key, which is what makes confirming idempotent:
    a second confirm of the same batch collides on insert and can never
    double-count. `cash_delta` is stored so deleting the batch can reverse the
    exact amount that was applied. A Plaid sync writes this same table (see
    `services/plaid_sync.py`) so `services/importer.delete_batch` reverses
    either source without any Plaid-specific undo path.
    """

    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint(f"source IN ('{CHASE_IMPORT}', '{PLAID}')", name="ck_import_batch_source"),
    )

    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    month_key: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    cash_delta: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, default=CHASE_IMPORT)
    #: Set when `source == 'plaid'`; which linked bank this sync came from.
    #: SET NULL on delete: unlinking an item is not the same as reversing the
    #: batches it produced, so past batches must survive losing their item.
    plaid_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("plaid_items.item_id", ondelete="SET NULL"), nullable=True
    )
