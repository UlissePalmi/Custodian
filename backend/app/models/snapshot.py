from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NetWorthSnapshot(Base):
    """Net worth as of the end of one month.

    Snapshots exist for past months only; the current month's point is computed
    live from holdings + cash + bonds, so a confirmed import moves it
    immediately. Written by the import roll-forward.
    """

    __tablename__ = "net_worth_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    month_key: Mapped[str] = mapped_column(String(7), nullable=False, unique=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # {"stocks": 12345.67, "cash": 890.12, "bonds": 0} — JSON so a new asset
    # class does not need a migration.
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
