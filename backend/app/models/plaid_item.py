from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ACTIVE = "active"
ERROR = "error"
DISCONNECTED = "disconnected"


class PlaidItem(Base):
    """A linked bank connection (one per Plaid Item).

    `access_token_encrypted` is the Fernet-encrypted Plaid access token — the
    only credential Custodian stores for the connection. `cursor` is Plaid's
    opaque `/transactions/sync` cursor; advancing it only ever happens in the
    same commit as the ledger writes it produced, so a crash mid-sync safely
    re-fetches the same page next run instead of skipping it.
    """

    __tablename__ = "plaid_items"
    __table_args__ = (
        CheckConstraint(f"status IN ('{ACTIVE}', '{ERROR}', '{DISCONNECTED}')", name="ck_plaid_item_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(String(500), nullable=False)
    institution_name: Mapped[str] = mapped_column(String(120), nullable=False)
    cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ACTIVE)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
