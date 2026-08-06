from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

CASH = "cash"
STOCKS = "stocks"
BONDS = "bonds"
#: What is owed on a card. Stored positive and subtracted at read time, so the
#: number here reads the way a statement does.
CREDIT = "credit"


class Account(Base):
    """A place value is held.

    `balance` is authoritative for cash- and bonds-type accounts, and is what
    is owed on a credit-type one. A stocks-type account's balance is only its
    *uninvested* cash — the positions themselves are `holdings`, valued at the
    latest quote — so the two add up rather than double-counting.

    `plaid_account_id` binds this to a real account at a bank. When set, every
    sync records what the bank says in `plaid_balance` without overwriting
    `balance`: the two are kept side by side deliberately, because the ledger
    balance drifting away from the bank's is the signal that a transaction was
    missed or counted twice. See `services/reconcile.py`.
    """

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Open-ended on purpose: 'crypto', 'real_estate', ... can be added without a
    # migration, and the dashboard renders whatever asset classes it receives.
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    # ISO 4217, lowercase. `balance` is in this currency; non-'usd' accounts are
    # converted to USD at read time (see services/networth.py) via the same
    # cached quote feed used for holdings, keyed by e.g. 'EURUSD=X'.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    #: The Plaid account this mirrors; null for anything Plaid cannot see.
    plaid_account_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    #: What the bank last reported, for comparison against `balance`.
    plaid_balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    plaid_balance_as_of: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
