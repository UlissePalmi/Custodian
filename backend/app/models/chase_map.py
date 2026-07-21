from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChaseCategoryMap(Base):
    """Chase's export category -> a Custodian category.

    A table rather than a constant so the mapping can be corrected from the API
    as new Chase category strings turn up. Anything unmapped falls through to
    "Other" and is flagged for review in the import preview.
    """

    __tablename__ = "chase_category_map"

    chase_category: Mapped[str] = mapped_column(String(120), primary_key=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), nullable=False)
