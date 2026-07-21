"""Month-key utilities — a Python port of `src/utils/months.ts`.

A "month key" is the string `YYYY-MM`. The ledger range defined here must stay
in sync with the front end's `LEDGER_START` / `LEDGER_END`; both sides derive
their month pickers and validation from it.
"""

import re
from calendar import monthrange
from datetime import date

LEDGER_START = "2026-07"
LEDGER_END = "2027-12"

_MONTH_KEY_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def is_valid_month_key(key: str) -> bool:
    return bool(_MONTH_KEY_PATTERN.match(key))


def parse_month_key(key: str) -> tuple[int, int]:
    year, month = key.split("-")
    return int(year), int(month)


def to_month_key(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _month_index(key: str) -> int:
    year, month = parse_month_key(key)
    return year * 12 + (month - 1)


def _from_month_index(index: int) -> str:
    return to_month_key(index // 12, (index % 12) + 1)


def compare_month_keys(a: str, b: str) -> int:
    return _month_index(a) - _month_index(b)


def is_within_ledger_range(key: str) -> bool:
    return (
        is_valid_month_key(key)
        and compare_month_keys(key, LEDGER_START) >= 0
        and compare_month_keys(key, LEDGER_END) <= 0
    )


def shift_month_key(key: str, delta: int) -> str | None:
    nxt = _from_month_index(_month_index(key) + delta)
    return nxt if is_within_ledger_range(nxt) else None


def month_key_range(start: str = LEDGER_START, end: str = LEDGER_END) -> list[str]:
    return [_from_month_index(i) for i in range(_month_index(start), _month_index(end) + 1)]


def month_keys_in_year(year: int) -> list[str]:
    return [key for key in month_key_range() if parse_month_key(key)[0] == year]


def month_key_from_date(value: date | str) -> str:
    if isinstance(value, date):
        return value.strftime("%Y-%m")
    return value[:7]


def days_in_month(key: str) -> int:
    year, month = parse_month_key(key)
    return monthrange(year, month)[1]


def iso_date_in(month_key: str, day: int) -> str:
    clamped = min(max(day, 1), days_in_month(month_key))
    return f"{month_key}-{clamped:02d}"


def current_snapshot_month(today: date | None = None) -> str:
    """The month whose net-worth point is computed live rather than stored.

    Clamped into the ledger range so a Pi with a wrong clock, or use before the
    ledger opens, still resolves to a real month.
    """
    today = today or date.today()
    key = to_month_key(today.year, today.month)
    if compare_month_keys(key, LEDGER_START) < 0:
        return LEDGER_START
    if compare_month_keys(key, LEDGER_END) > 0:
        return LEDGER_END
    return key
