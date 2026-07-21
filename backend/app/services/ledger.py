"""Categories, transaction CRUD and the monthly ledger.

Validation messages and status codes here match the mock API
(`src/api/mock/store.ts`) word for word — the front end surfaces `detail`
directly to the user, so a divergence would show up on screen.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Category, Transaction
from app.money import ZERO, round_cents
from app.months import (
    LEDGER_START,
    compare_month_keys,
    is_valid_month_key,
    is_within_ledger_range,
    month_key_from_date,
    month_key_range,
)
from app.schemas.ledger import TransactionInput


# --------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------


def list_categories(db: Session, *, include_archived: bool = False) -> list[Category]:
    """Income categories first, then expense; each group by its sort order."""
    stmt = select(Category)
    if not include_archived:
        stmt = stmt.where(Category.archived.is_(False))
    categories = db.scalars(stmt).all()
    return sorted(categories, key=lambda c: (0 if c.kind == "income" else 1, c.sort_order, c.name))


def get_category(db: Session, category_id: str) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise ApiError(f"Unknown category: {category_id}", 422)
    return category


def _slugify(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip())
    parts = [p for p in cleaned.split("-") if p]
    return "cat-" + "-".join(parts)


def create_category(db: Session, name: str, kind: str, sort_order: int | None) -> Category:
    name = name.strip()
    if not name:
        raise ApiError("Category name is required.", 422)

    base_id = _slugify(name)
    category_id = base_id
    suffix = 2
    while db.get(Category, category_id) is not None:
        category_id = f"{base_id}-{suffix}"
        suffix += 1

    if sort_order is None:
        existing = [c.sort_order for c in db.scalars(select(Category).where(Category.kind == kind))]
        sort_order = (max(existing) + 1) if existing else 0

    category = Category(id=category_id, name=name, kind=kind, sort_order=sort_order)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(
    db: Session,
    category_id: str,
    *,
    name: str | None = None,
    sort_order: int | None = None,
    archived: bool | None = None,
) -> Category:
    category = get_category(db, category_id)
    if name is not None:
        if not name.strip():
            raise ApiError("Category name is required.", 422)
        category.name = name.strip()
    if sort_order is not None:
        category.sort_order = sort_order
    if archived is not None:
        category.archived = archived
    db.commit()
    db.refresh(category)
    return category


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def validate_month_key(month_key: str) -> str:
    if not is_valid_month_key(month_key):
        raise ApiError(f"Invalid month: {month_key}", 422)
    if not is_within_ledger_range(month_key):
        raise ApiError(f"{month_key} is outside the ledger range.", 404)
    return month_key


def _validate_input(db: Session, payload: TransactionInput) -> tuple[Decimal, str, Category]:
    """Shared create/update validation. Returns the cleaned amount, description and category."""
    if compare_month_keys(month_key_from_date(payload.date), LEDGER_START) < 0:
        raise ApiError(
            f"Custodian's ledger starts in {LEDGER_START}. Earlier dates are not accepted.", 422
        )

    try:
        amount = round_cents(Decimal(str(payload.amount)))
    except (InvalidOperation, ValueError):
        raise ApiError("Amount must be greater than zero.", 422) from None
    if not amount.is_finite() or amount <= 0:
        raise ApiError("Amount must be greater than zero.", 422)

    description = payload.description.strip()
    if not description:
        raise ApiError("Description is required.", 422)

    category = get_category(db, payload.category_id)
    return amount, description, category


# --------------------------------------------------------------------------
# Transaction CRUD
# --------------------------------------------------------------------------


def create_transaction(
    db: Session,
    month_key: str,
    payload: TransactionInput,
    *,
    source: str = "manual",
    import_batch_id: str | None = None,
    commit: bool = True,
) -> Transaction:
    if month_key_from_date(payload.date) != month_key:
        raise ApiError(f"Date {payload.date.isoformat()} does not fall in {month_key}.", 422)

    amount, description, category = _validate_input(db, payload)
    transaction = Transaction(
        date=payload.date,
        amount=amount,
        description=description,
        category_id=category.id,
        source=source,
        import_batch_id=import_batch_id,
    )
    db.add(transaction)
    if commit:
        db.commit()
        db.refresh(transaction)
    else:
        db.flush()
    return transaction


def update_transaction(db: Session, transaction_id: int, payload: TransactionInput) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise ApiError("Transaction not found.", 404)

    amount, description, category = _validate_input(db, payload)
    transaction.date = payload.date
    transaction.amount = amount
    transaction.description = description
    transaction.category_id = category.id
    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, transaction_id: int) -> None:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise ApiError("Transaction not found.", 404)
    db.delete(transaction)
    db.commit()


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


def transactions_for_month(db: Session, month_key: str) -> list[Transaction]:
    start, end = _month_bounds(month_key)
    stmt = (
        select(Transaction)
        .where(Transaction.date >= start, Transaction.date <= end)
        .order_by(Transaction.date, Transaction.id)
    )
    return list(db.scalars(stmt).unique())


def _month_bounds(month_key: str) -> tuple[date, date]:
    from app.months import days_in_month, parse_month_key

    year, month = parse_month_key(month_key)
    return date(year, month, 1), date(year, month, days_in_month(month_key))


def read_month_ledger(db: Session, month_key: str) -> dict:
    entries = transactions_for_month(db, month_key)
    income = [t for t in entries if t.category.kind == "income"]
    expenses = [t for t in entries if t.category.kind == "expense"]

    total_income = round_cents(sum((t.amount for t in income), ZERO))
    total_expenses = round_cents(sum((t.amount for t in expenses), ZERO))

    return {
        "month_key": month_key,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net": round_cents(total_income - total_expenses),
        "income": [hydrate(t) for t in income],
        "expenses": [hydrate(t) for t in expenses],
    }


def read_months(db: Session) -> list[dict]:
    """Every month in the ledger range, including the empty ones.

    The picker renders the full range and uses `hasData` to grey out months
    that have nothing in them yet.
    """
    stmt = select(Transaction).order_by(Transaction.date, Transaction.id)
    by_month: dict[str, list[Transaction]] = {}
    for transaction in db.scalars(stmt).unique():
        by_month.setdefault(month_key_from_date(transaction.date), []).append(transaction)

    months = []
    for month_key in month_key_range():
        entries = by_month.get(month_key, [])
        total_income = round_cents(
            sum((t.amount for t in entries if t.category.kind == "income"), ZERO)
        )
        total_expenses = round_cents(
            sum((t.amount for t in entries if t.category.kind == "expense"), ZERO)
        )
        months.append(
            {
                "month_key": month_key,
                "has_data": bool(entries),
                "total_income": total_income,
                "total_expenses": total_expenses,
                "net": round_cents(total_income - total_expenses),
            }
        )
    return months


def hydrate(transaction: Transaction) -> dict:
    """Adds the denormalised display fields the contract promises."""
    return {
        "id": transaction.id,
        "date": transaction.date,
        "amount": transaction.amount,
        "description": transaction.description,
        "category_id": transaction.category_id,
        "category_name": transaction.category.name,
        "kind": transaction.category.kind,
        "source": transaction.source,
        "import_batch_id": transaction.import_batch_id,
    }
