"""The yearly table.

Computed by aggregating transactions at request time — there is no stored
yearly table. The monthly ledger is the single source of truth, so the two can
never disagree.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.money import ZERO, round_cents
from app.months import month_keys_in_year
from app.services.ledger import list_categories


def read_yearly_table(db: Session, year: int) -> dict:
    columns = list_categories(db)
    month_keys = month_keys_in_year(year)
    if not month_keys:
        empty = {"cells": {}, "total_income": ZERO, "total_expenses": ZERO, "net": ZERO}
        return {"year": year, "columns": columns, "rows": [], "totals": empty}

    month_expr = func.to_char(Transaction.date, "YYYY-MM").label("month_key")
    stmt = (
        select(month_expr, Transaction.category_id, func.sum(Transaction.amount))
        .where(month_expr.in_(month_keys))
        .group_by(month_expr, Transaction.category_id)
    )

    kinds = {c.id: c.kind for c in db.scalars(select(Category)).all()}

    # month_key -> category_id -> summed amount
    aggregated: dict[str, dict[str, object]] = {key: {} for key in month_keys}
    for month_key, category_id, total in db.execute(stmt):
        aggregated[month_key][category_id] = round_cents(total)

    rows = []
    totals_cells: dict[str, object] = {}
    grand_income = ZERO
    grand_expenses = ZERO

    for month_key in month_keys:
        cells = aggregated[month_key]
        total_income = ZERO
        total_expenses = ZERO
        for category_id, amount in cells.items():
            if kinds.get(category_id) == "income":
                total_income += amount
            else:
                total_expenses += amount
            totals_cells[category_id] = round_cents(totals_cells.get(category_id, ZERO) + amount)

        total_income = round_cents(total_income)
        total_expenses = round_cents(total_expenses)
        grand_income += total_income
        grand_expenses += total_expenses

        rows.append(
            {
                "month_key": month_key,
                "cells": cells,
                "total_income": total_income,
                "total_expenses": total_expenses,
                "net": round_cents(total_income - total_expenses),
            }
        )

    grand_income = round_cents(grand_income)
    grand_expenses = round_cents(grand_expenses)

    return {
        "year": year,
        "columns": columns,
        "rows": rows,
        "totals": {
            "cells": totals_cells,
            "total_income": grand_income,
            "total_expenses": grand_expenses,
            "net": round_cents(grand_income - grand_expenses),
        },
    }
