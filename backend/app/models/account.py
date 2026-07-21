from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

CASH = "cash"
STOCKS = "stocks"
BONDS = "bonds"


class Account(Base):
    """A place value is held.

    `balance` is authoritative for cash- and bonds-type accounts. Stocks-type
    accounts carry no balance — their value is the sum of their holdings at the
    latest quote.
    """

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Open-ended on purpose: 'crypto', 'real_estate', ... can be added without a
    # migration, and the dashboard renders whatever asset classes it receives.
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
