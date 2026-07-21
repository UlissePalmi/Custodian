"""Categories, transactions, monthly ledger and the yearly table."""

from datetime import date
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.base import CamelModel, Money

CategoryKind = Literal["income", "expense"]
TransactionSource = Literal["manual", "chase_import"]


# --------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------


class CategoryOut(CamelModel):
    id: str
    name: str
    kind: CategoryKind
    sort_order: int
    archived: bool = False


class CategoryCreate(CamelModel):
    name: str
    kind: CategoryKind
    sort_order: int | None = None


class CategoryUpdate(CamelModel):
    name: str | None = None
    sort_order: int | None = None
    archived: bool | None = None


# --------------------------------------------------------------------------
# Transactions
# --------------------------------------------------------------------------


class TransactionOut(CamelModel):
    id: str
    date: date
    amount: Money
    description: str
    category_id: str
    category_name: str
    kind: CategoryKind
    source: TransactionSource
    import_batch_id: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_string(cls, value: object) -> str:
        # Serial in the database, opaque string in the contract.
        return str(value)


class TransactionInput(CamelModel):
    date: date
    amount: float
    description: str
    category_id: str


# --------------------------------------------------------------------------
# Monthly ledger
# --------------------------------------------------------------------------


class MonthLedgerOut(CamelModel):
    month_key: str
    total_income: Money
    total_expenses: Money
    net: Money
    income: list[TransactionOut]
    expenses: list[TransactionOut]


class MonthInfoOut(CamelModel):
    month_key: str
    has_data: bool
    total_income: Money
    total_expenses: Money
    net: Money


# --------------------------------------------------------------------------
# Yearly table
# --------------------------------------------------------------------------


class YearlyTableRowOut(CamelModel):
    month_key: str
    cells: dict[str, Money] = Field(default_factory=dict)
    total_income: Money
    total_expenses: Money
    net: Money


class YearlyTableTotalsOut(CamelModel):
    cells: dict[str, Money] = Field(default_factory=dict)
    total_income: Money
    total_expenses: Money
    net: Money


class YearlyTableOut(CamelModel):
    year: int
    columns: list[CategoryOut]
    rows: list[YearlyTableRowOut]
    totals: YearlyTableTotalsOut
