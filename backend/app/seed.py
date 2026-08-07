"""Seed the database with the reference data the app cannot run without.

Not sample data — every row here is required. Transactions carry a category
foreign key, so an empty `categories` table means nothing can be written; the
sync reads its category mapping from `plaid_category_map` rather than from the
dict below; and `networth.get_cash_account` and
`plaid_investments.get_brokerage_account` both refuse to work with no account
to point at.

Safe to re-run: every insert is guarded by an existence check, so it only
fills in what is missing. The test suite relies on that, calling `seed_base`
before every test.

    python -m app.seed
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Account, Category, PlaidCategoryMap

CATEGORIES = [
    ("cat-main-income", "Main income", "income", 0),
    ("cat-secondary-income", "Secondary income", "income", 1),
    ("cat-rent", "Rent", "expense", 0),
    ("cat-utilities", "Utilities", "expense", 1),
    ("cat-phone", "Phone", "expense", 2),
    ("cat-groceries", "Groceries", "expense", 3),
    ("cat-dining", "Dining", "expense", 4),
    ("cat-transport", "Transport", "expense", 5),
    ("cat-subscriptions", "Subscriptions", "expense", 6),
    ("cat-other", "Other", "expense", 7),
]

# Plaid's `personal_finance_category.primary` enum. Editable through the
# database as Plaid adds values; unmapped ones fall through to a fallback
# income/expense category (see services/plaid_sync.py's `_propose`).
PLAID_CATEGORY_MAP = {
    # INCOME is the only thing that means earnings; money arriving from
    # somewhere else is not a paycheck and would otherwise make the main
    # income column read as more than was earned.
    "INCOME": "cat-main-income",
    "TRANSFER_IN": "cat-secondary-income",
    "TRANSFER_OUT": "cat-other",
    "LOAN_PAYMENTS": "cat-other",
    "BANK_FEES": "cat-other",
    "ENTERTAINMENT": "cat-subscriptions",
    "FOOD_AND_DRINK": "cat-dining",
    "GENERAL_MERCHANDISE": "cat-other",
    "HOME_IMPROVEMENT": "cat-other",
    "MEDICAL": "cat-other",
    "PERSONAL_CARE": "cat-other",
    "GENERAL_SERVICES": "cat-subscriptions",
    "GOVERNMENT_AND_NON_PROFIT": "cat-other",
    "TRANSPORTATION": "cat-transport",
    "TRAVEL": "cat-transport",
    "RENT_AND_UTILITIES": "cat-utilities",
}

ACCOUNTS = [("Cash", "cash"), ("Bonds", "bonds"), ("Brokerage", "stocks")]


def seed_base(db: Session) -> None:
    for category_id, name, kind, sort_order in CATEGORIES:
        if db.get(Category, category_id) is None:
            db.add(Category(id=category_id, name=name, kind=kind, sort_order=sort_order))
    db.flush()

    for plaid_category, category_id in PLAID_CATEGORY_MAP.items():
        if db.get(PlaidCategoryMap, plaid_category) is None:
            db.add(PlaidCategoryMap(plaid_category=plaid_category, category_id=category_id))

    for name, account_type in ACCOUNTS:
        existing = db.scalar(select(Account).where(Account.type == account_type))
        if existing is None:
            db.add(Account(name=name, type=account_type, balance=Decimal("0.00")))

    db.commit()


def main() -> None:
    with SessionLocal() as db:
        seed_base(db)
    print("Seeded base data.")


if __name__ == "__main__":
    main()
