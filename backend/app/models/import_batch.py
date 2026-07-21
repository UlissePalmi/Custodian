from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImportBatch(Base):
    """A confirmed Chase import.

    The batch id is the primary key, which is what makes confirming idempotent:
    a second confirm of the same batch collides on insert and can never
    double-count. `cash_delta` is stored so deleting the batch can reverse the
    exact amount that was applied.
    """

    __tablename__ = "import_batches"

    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    month_key: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    cash_delta: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
