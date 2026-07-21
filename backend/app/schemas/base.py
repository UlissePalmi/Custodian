"""Shared schema plumbing.

The front end's types are camelCase (`src/api/types.ts`), so every schema here
derives from `CamelModel` and is serialised by alias. Money is emitted as a
plain 2-dp JSON number, matching the contract's "Decimal serialised as a JSON
number rounded to 2 dp".
"""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel

from app.money import round_cents


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        ser_json_inf_nan="null",
    )


def _as_money(value: Decimal) -> float:
    return float(round_cents(value))


def _as_plain(value: Decimal) -> float:
    return float(value)


#: Dollar amount. Always rounded to cents on the way out.
Money = Annotated[Decimal, PlainSerializer(_as_money, return_type=float)]

#: Whole-number percentage, e.g. `12.5` meaning 12.5%.
Percent = Annotated[Decimal, PlainSerializer(_as_money, return_type=float)]

#: Share counts and per-share prices, which carry more than two decimals.
Quantity = Annotated[Decimal, PlainSerializer(_as_plain, return_type=float)]
