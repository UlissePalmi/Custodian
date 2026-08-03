from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlaidCategoryMap(Base):
    """Plaid's `personal_finance_category.primary` -> a Custodian category.

    Same shape and purpose as `ChaseCategoryMap`: a table rather than a
    constant so it can be corrected from the database as new Plaid category
    values turn up. Unmapped values fall through to the same income/expense
    fallback categories the Chase path uses.
    """

    __tablename__ = "plaid_category_map"

    plaid_category: Mapped[str] = mapped_column(String(64), primary_key=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), nullable=False)
