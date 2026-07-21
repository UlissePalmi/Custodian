from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

INCOME = "income"
EXPENSE = "expense"


class Category(Base):
    """A ledger category.

    The primary key is a readable slug (`cat-groceries`) rather than a serial:
    the Chase mapping table and the yearly table's `cells` object both key on
    it, and the front end's seed data uses the same slugs.
    """

    __tablename__ = "categories"
    __table_args__ = (CheckConstraint("kind IN ('income', 'expense')", name="ck_category_kind"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Archived categories stay attached to historical transactions but drop out
    # of the pickers and the yearly table's columns.
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
