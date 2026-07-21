from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.category import Category

MANUAL = "manual"
CHASE_IMPORT = "chase_import"


class Transaction(Base):
    """One ledger entry.

    `amount` is always positive; direction comes from the category's `kind`.
    The month key is derived from `date` rather than stored, so editing a date
    can never leave a stale month behind.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transaction_amount_positive"),
        CheckConstraint("source IN ('manual', 'chase_import')", name="ck_transaction_source"),
        Index("ix_transactions_date", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default=MANUAL)
    import_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_batches.batch_id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Eager-loaded because every serialised transaction carries `categoryName`
    # and `kind` — a lazy load here would be an N+1 on every ledger read.
    category: Mapped[Category] = relationship(lazy="joined")
