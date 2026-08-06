"""Plaid Link + connection status.

Sync results use `ImportResult` from `schemas/imports.py`.
"""

from datetime import datetime
from typing import Literal

from app.schemas.base import CamelModel


class LinkTokenResponse(CamelModel):
    link_token: str


class ExchangeTokenRequest(CamelModel):
    public_token: str
    institution_id: str | None = None
    institution_name: str | None = None


class PlaidConnection(CamelModel):
    item_id: str
    institution_name: str
    status: Literal["active", "error", "disconnected"]
    last_synced_at: datetime | None
    last_error: str | None
