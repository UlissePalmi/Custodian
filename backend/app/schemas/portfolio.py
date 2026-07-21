"""Net worth, holdings and accounts."""

from datetime import date, datetime

from pydantic import field_validator

from app.schemas.base import CamelModel, Money, Percent, Quantity


class NetWorthChangeOut(CamelModel):
    amount: Money
    percent: Percent


class AllocationSliceOut(CamelModel):
    asset_class: str
    label: str
    value: Money
    percent: Percent


class NetWorthPointOut(CamelModel):
    month_key: str
    total: Money


class NetWorthSummaryOut(CamelModel):
    total: Money
    as_of: date
    change_vs_prev_month: NetWorthChangeOut | None = None
    history: list[NetWorthPointOut]
    allocation: list[AllocationSliceOut]


class HoldingOut(CamelModel):
    id: str
    ticker: str
    name: str
    quantity: Quantity
    cost_basis_per_share: Quantity
    current_price: Quantity
    quote_as_of: datetime
    market_value: Money
    total_return: NetWorthChangeOut
    ytd_return_percent: Percent

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_string(cls, value: object) -> str:
        return str(value)


# --------------------------------------------------------------------------
# Admin payloads — no UI yet; used from curl to record what is actually owned.
# --------------------------------------------------------------------------


class HoldingInput(CamelModel):
    ticker: str
    name: str | None = None
    quantity: float
    cost_basis_per_share: float
    purchase_date: date | None = None
    account_id: int | None = None


class AccountOut(CamelModel):
    id: int
    name: str
    type: str
    balance: Money


class AccountInput(CamelModel):
    name: str | None = None
    type: str | None = None
    balance: float | None = None
