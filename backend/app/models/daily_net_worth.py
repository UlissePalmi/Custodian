from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyNetWorth(Base):
    """Net worth at the end of one day.

    Days recorded as they happened and days reconstructed afterwards are stored
    identically — there is no provenance flag, so nothing distinguishes a
    measurement from a reconstruction once written. That is a deliberate
    simplification; the reconstruction is exact wherever prices and the ledger
    are (see `services/history.py`), and only 1–3 July hold a price flat.

    Separate from `net_worth_snapshots`, which stores one row per month and is
    written by the sync roll-forward for a different purpose.
    """

    __tablename__ = "daily_net_worth"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # {"stocks": 2197.70, "cash": 3182.53, "bonds": 55292.77} — JSON so a new
    # asset class needs no migration.
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
