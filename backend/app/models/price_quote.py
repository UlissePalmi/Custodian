from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PriceQuote(Base):
    """Cache of the delayed price feed, one row per ticker.

    `as_of` is served to the front end so a stale quote is visible rather than
    silently presented as live — which is what happens whenever the Pi is
    offline and the cache is all we have.
    """

    __tablename__ = "price_quotes"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ytd_return_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
