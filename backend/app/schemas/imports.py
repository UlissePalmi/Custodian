"""What a sync did to the ledger.

Returned by a Plaid sync and mirrored by `ImportResult` in
`frontend/src/api/types.ts`.
"""

from app.schemas.base import CamelModel, Money


class ImportResult(CamelModel):
    batch_id: str
    month_key: str
    imported_count: int
    #: Net cash movement of the batch (income − expenses). Applied to the cash
    #: account balance and rolled into the month's net worth snapshot; stored
    #: on the batch so deleting it reverses the exact amount applied.
    cash_delta: Money
    new_net_worth_total: Money
