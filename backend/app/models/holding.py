from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.account import Account

MANUAL = "manual"
PLAID = "plaid"


class Holding(Base):
    """A position in one security.

    The current price is deliberately absent: it lives in `price_quotes`, keyed
    by ticker, so a position's market value always reflects the latest cached
    quote rather than a copy that could go stale.

    `source` splits ownership of this table. Positions in a linked brokerage
    are replaced wholesale from Plaid on every sync, so trades show up without
    anyone typing them in; anything held somewhere Plaid cannot see (a Treasury
    bought direct, say) stays `manual` and is never touched by a sync. Without
    that split, a synced position and a hand-entered one for the same security
    would silently double the holding.
    """

    __tablename__ = "holdings"
    __table_args__ = (
        CheckConstraint(f"source IN ('{MANUAL}', '{PLAID}')", name="ck_holding_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 6), nullable=False)
    cost_basis_per_share: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default=MANUAL)
    #: Plaid's security id, stable across syncs — how a synced position is
    #: recognised again when its quantity changes.
    plaid_security_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    account: Mapped[Account] = relationship()
