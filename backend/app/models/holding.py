from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.account import Account


class Holding(Base):
    """A position in one security.

    The current price is deliberately absent: it lives in `price_quotes`, keyed
    by ticker, so a position's market value always reflects the latest cached
    quote rather than a copy that could go stale.
    """

    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 6), nullable=False)
    cost_basis_per_share: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)

    account: Mapped[Account] = relationship()
