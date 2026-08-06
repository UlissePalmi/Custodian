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
    #: Against the same date one month back, not the previous month's close.
    change_vs_month_ago: NetWorthChangeOut | None = None
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
    currency: str


class DailyNetWorthOut(CamelModel):
    """Net worth at the end of one day."""

    day: date
    total: Money


class AccountHoldingLine(CamelModel):
    """One position, as shown beneath the account that holds it."""

    id: int
    ticker: str
    name: str
    quantity: Quantity
    current_price: Money
    market_value: Money
    quote_as_of: datetime
    #: 'plaid' when synced from a linked brokerage, 'manual' otherwise.
    source: str


class AccountBreakdownOut(CamelModel):
    id: int
    name: str
    #: The account's own kind: cash, stocks, bonds, credit.
    type: str
    #: Where this row counts in the allocation, which is not always `type`:
    #: a card's debt and a brokerage's uninvested cash both count as cash.
    #: A brokerage with idle cash therefore yields two rows, one per class.
    asset_class: str
    currency: str
    #: In the account's own currency; `value` is the USD figure net worth uses.
    balance: Money
    #: What this row contributes to net worth under `asset_class`: negative
    #: for a credit account, positions only for a brokerage's stocks row.
    value: Money
    percent: Percent
    #: False for accounts Plaid cannot see, which are maintained by hand.
    is_connected: bool
    #: When the bank last reported; null for unconnected accounts.
    balance_as_of: datetime | None
    holdings: list[AccountHoldingLine]


class AccountInput(CamelModel):
    name: str | None = None
    type: str | None = None
    balance: float | None = None
    currency: str | None = None


class AccountCreate(CamelModel):
    name: str
    type: str
    balance: float = 0
    currency: str = "usd"
