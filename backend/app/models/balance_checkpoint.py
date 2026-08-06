from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BalanceCheckpoint(Base):
    """One observation of "what we hold" against "what we recorded".

    Per-account drift stopped being a useful check once balances came from the
    bank — they cannot disagree. The question that survives is whether the
    ledger saw everything that moved, and that needs two figures over time
    rather than one at a moment.

    `tracked_total` is money in a form that only changes when something real
    happens: connected cash, minus card debt, plus brokerage cash, plus
    positions *at cost*. Cost rather than market is what makes it comparable —
    a price move is not a transaction, and buying a share just converts cash
    into holdings at the same value.

    `ledger_net` is the cumulative income minus expenses Custodian has
    recorded.

    Neither is meaningful alone: `tracked_total - ledger_net` is a constant
    offset absorbing everything from before the ledger began. What matters is
    that the offset *stays* constant. A change in it means money moved without
    a matching entry, or an entry exists for money that never moved.
    """

    __tablename__ = "balance_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    tracked_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    ledger_net: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
