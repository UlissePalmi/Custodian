"""Decimal money helpers.

Every dollar amount in the app is a `Decimal` internally and a 2-dp JSON number
on the wire. Rounding happens at each aggregation step, mirroring the front
end's `roundCents` (`src/utils/money.ts`), so totals computed here and there
can never drift apart.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")

ZERO = Decimal("0.00")


def round_cents(value: Decimal | float | int) -> Decimal:
    """Rounds to two decimal places, half away from zero (as JS `Math.round`)."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def percent_of(part: Decimal, whole: Decimal) -> Decimal:
    """`part` as a percentage of `whole`, rounded to 2 dp. Zero whole -> 0."""
    if whole == 0:
        return ZERO
    return round_cents(part / whole * 100)
