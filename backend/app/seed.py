"""Seed the database.

Run without arguments for a real, empty ledger: categories, the Chase category
mapping and zero-balance Cash/Bonds accounts — nothing else. `--demo` adds the
front end's fixture data, which is only useful for comparing the API against
the mock.

    python -m app.seed
    python -m app.seed --demo
"""

import argparse
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Account,
    Category,
    ChaseCategoryMap,
    Holding,
    NetWorthSnapshot,
    Transaction,
)

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

# Chase's export categories. Editable through the database as new strings show
# up in real exports; unmapped ones fall through to "Other" and get flagged.
CHASE_CATEGORY_MAP = {
    "Bills & Utilities": "cat-utilities",
    "Groceries": "cat-groceries",
    "Food & Drink": "cat-dining",
    "Travel": "cat-transport",
    "Gas": "cat-transport",
    "Automotive": "cat-transport",
    "Entertainment": "cat-subscriptions",
    "Shopping": "cat-other",
    "Health": "cat-other",
    "Health & Wellness": "cat-other",
    "Personal": "cat-other",
    "Education": "cat-other",
    "Home": "cat-other",
    "Rent": "cat-rent",
    "Payroll": "cat-main-income",
    "ACH_CREDIT": "cat-main-income",
}

ACCOUNTS = [("Cash", "cash"), ("Bonds", "bonds"), ("Brokerage", "stocks")]


def seed_base(db: Session) -> None:
    for category_id, name, kind, sort_order in CATEGORIES:
        if db.get(Category, category_id) is None:
            db.add(Category(id=category_id, name=name, kind=kind, sort_order=sort_order))
    db.flush()

    for chase_category, category_id in CHASE_CATEGORY_MAP.items():
        if db.get(ChaseCategoryMap, chase_category) is None:
            db.add(ChaseCategoryMap(chase_category=chase_category, category_id=category_id))

    for name, account_type in ACCOUNTS:
        existing = db.scalar(select(Account).where(Account.type == account_type))
        if existing is None:
            db.add(Account(name=name, type=account_type, balance=Decimal("0.00")))

    db.commit()


# --------------------------------------------------------------------------
# Demo data — mirrors src/api/mock/seed.ts so the API can be diffed against the
# mock screen by screen.
# --------------------------------------------------------------------------

DEMO_TRANSACTIONS = [
    ("2026-07-01", "3200", "Paycheck — first half", "cat-main-income"),
    ("2026-07-15", "3200", "Paycheck — second half", "cat-main-income"),
    ("2026-07-08", "850", "Freelance — landing page build", "cat-secondary-income"),
    ("2026-07-01", "1850", "July rent", "cat-rent"),
    ("2026-07-03", "92.40", "Con Edison — electric", "cat-utilities"),
    ("2026-07-05", "65", "Verizon", "cat-phone"),
    ("2026-07-04", "128.75", "Trader Joe's", "cat-groceries"),
    ("2026-07-11", "94.20", "Whole Foods", "cat-groceries"),
    ("2026-07-18", "112.60", "Trader Joe's", "cat-groceries"),
    ("2026-07-06", "78", "Sushi with M.", "cat-dining"),
    ("2026-07-12", "42.30", "Coffee + brunch", "cat-dining"),
    ("2026-07-19", "31.50", "Thai takeout", "cat-dining"),
    ("2026-07-02", "132", "MTA monthly", "cat-transport"),
    ("2026-07-14", "23.80", "Uber — airport", "cat-transport"),
    ("2026-07-01", "11.99", "Spotify", "cat-subscriptions"),
    ("2026-07-02", "9.99", "iCloud 2TB", "cat-subscriptions"),
    ("2026-07-07", "15.49", "Netflix", "cat-subscriptions"),
    ("2026-07-09", "45", "Dentist copay", "cat-other"),
    ("2026-07-16", "60", "Birthday gift", "cat-other"),
]

DEMO_HOLDINGS = [
    ("VOO", "Vanguard S&P 500 ETF", "42", "465.20"),
    ("AAPL", "Apple Inc.", "60", "178.50"),
    ("MSFT", "Microsoft Corp.", "25", "372.80"),
    ("NVDA", "NVIDIA Corp.", "30", "118.40"),
    ("VXUS", "Vanguard Total International Stock ETF", "85", "61.30"),
    ("SCHD", "Schwab US Dividend Equity ETF", "70", "79.10"),
]

DEMO_SNAPSHOTS = [
    ("2026-01", "88420"),
    ("2026-02", "90150"),
    ("2026-03", "89280"),
    ("2026-04", "93640"),
    ("2026-05", "96910"),
    ("2026-06", "99780"),
]


def seed_demo(db: Session) -> None:
    if db.scalar(select(Transaction).limit(1)) is None:
        for iso_date, amount, description, category_id in DEMO_TRANSACTIONS:
            db.add(
                Transaction(
                    date=date.fromisoformat(iso_date),
                    amount=Decimal(amount),
                    description=description,
                    category_id=category_id,
                    source="manual",
                )
            )

    brokerage = db.scalar(select(Account).where(Account.type == "stocks"))
    if db.scalar(select(Holding).limit(1)) is None and brokerage is not None:
        for ticker, name, quantity, cost_basis in DEMO_HOLDINGS:
            db.add(
                Holding(
                    ticker=ticker,
                    name=name,
                    quantity=Decimal(quantity),
                    cost_basis_per_share=Decimal(cost_basis),
                    account_id=brokerage.id,
                )
            )

    cash = db.scalar(select(Account).where(Account.type == "cash"))
    bonds = db.scalar(select(Account).where(Account.type == "bonds"))
    if cash is not None and cash.balance == 0:
        cash.balance = Decimal("28450.00")
    if bonds is not None and bonds.balance == 0:
        bonds.balance = Decimal("12300.00")

    for month_key, total in DEMO_SNAPSHOTS:
        existing = db.scalar(
            select(NetWorthSnapshot).where(NetWorthSnapshot.month_key == month_key)
        )
        if existing is None:
            year, month = month_key.split("-")
            db.add(
                NetWorthSnapshot(
                    month_key=month_key,
                    as_of=date(int(year), int(month), 28),
                    total=Decimal(total),
                    breakdown={},
                )
            )

    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Custodian database.")
    parser.add_argument(
        "--demo", action="store_true", help="also load the mock's fixture data"
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        seed_base(db)
        if args.demo:
            seed_demo(db)

    print("Seeded base data." + (" Demo data loaded." if args.demo else ""))


if __name__ == "__main__":
    main()
