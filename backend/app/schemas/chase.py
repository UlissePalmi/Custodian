"""Chase import preview and confirmation.

The preview is not persisted: it round-trips through the client, which may edit
categories and untick rows before posting it back to `/confirm`. That keeps the
upload endpoint a pure read, exactly as the contract describes.
"""

from datetime import date
from typing import Literal

from app.schemas.base import CamelModel, Money


class ProposedTransaction(CamelModel):
    id: str
    date: date
    amount: Money
    description: str
    chase_category: str
    category_id: str
    kind: Literal["income", "expense"]
    flagged_for_review: bool
    include: bool = True


class ImportPreview(CamelModel):
    batch_id: str
    file_name: str
    detected_month_key: str
    transactions: list[ProposedTransaction]


class ImportResult(CamelModel):
    batch_id: str
    month_key: str
    imported_count: int
    cash_delta: Money
    new_net_worth_total: Money
