"""Monthly ledger: validation, CRUD and the shapes the front end expects."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account
from app.services import networth
from app.months import LEDGER_END, LEDGER_START, month_key_range

STARTING_CASH = 10000


@pytest.fixture
def cash_account(client: TestClient, db: Session) -> Account:
    account = db.scalar(select(Account).where(Account.type == "cash"))
    client.put(f"/api/accounts/{account.id}", json={"balance": STARTING_CASH})
    return account


def net_worth_total(db: Session) -> Decimal:
    """Net worth is computed on read now that monthly snapshots are gone, so
    this asserts the same thing the dashboard would show."""
    db.expire_all()
    total, _ = networth.compute_totals(db)
    return total


def cash_balance(db: Session) -> Decimal:
    db.expire_all()
    return db.scalar(select(Account.balance).where(Account.type == "cash"))



def create(client: TestClient, month_key: str, **overrides) -> dict:
    payload = {
        "date": f"{month_key}-05",
        "amount": 100,
        "description": "Test entry",
        "categoryId": "cat-groceries",
    } | overrides
    return client.post(f"/api/months/{month_key}/transactions", json=payload).json()


def test_categories_are_income_first_then_sort_order(client: TestClient) -> None:
    categories = client.get("/api/categories").json()
    kinds = [c["kind"] for c in categories]
    assert kinds == sorted(kinds, key=lambda k: 0 if k == "income" else 1)
    assert categories[0]["id"] == "cat-main-income"
    assert [c["sortOrder"] for c in categories if c["kind"] == "expense"] == list(range(8))


def test_months_covers_the_whole_ledger_range(client: TestClient) -> None:
    months = client.get("/api/months").json()
    assert [m["monthKey"] for m in months] == month_key_range()
    assert months[0]["monthKey"] == LEDGER_START
    assert months[-1]["monthKey"] == LEDGER_END
    assert all(m["hasData"] is False for m in months)


def test_month_has_data_flips_once_a_transaction_exists(client: TestClient) -> None:
    create(client, "2026-08")
    months = {m["monthKey"]: m for m in client.get("/api/months").json()}
    assert months["2026-08"]["hasData"] is True
    assert months["2026-09"]["hasData"] is False


def test_create_returns_hydrated_transaction(client: TestClient) -> None:
    body = create(client, "2026-07", amount=128.75, description="  Trader Joe's  ")
    assert body["amount"] == 128.75
    assert body["description"] == "Trader Joe's"  # trimmed
    assert body["categoryName"] == "Groceries"
    assert body["kind"] == "expense"
    assert body["source"] == "manual"
    assert isinstance(body["id"], str)


def test_month_ledger_totals(client: TestClient) -> None:
    create(client, "2026-07", amount=3200, categoryId="cat-main-income", description="Pay")
    create(client, "2026-07", amount=1850, categoryId="cat-rent", description="Rent")
    create(client, "2026-07", amount=92.40, categoryId="cat-utilities", description="Power")

    ledger = client.get("/api/months/2026-07").json()
    assert ledger["totalIncome"] == 3200
    assert ledger["totalExpenses"] == 1942.40
    assert ledger["net"] == 1257.60
    assert len(ledger["income"]) == 1
    assert len(ledger["expenses"]) == 2


def test_update_and_delete(client: TestClient) -> None:
    created = create(client, "2026-07")
    transaction_id = created["id"]

    updated = client.put(
        f"/api/transactions/{transaction_id}",
        json={
            "date": "2026-07-09",
            "amount": 55.5,
            "description": "Changed",
            "categoryId": "cat-dining",
        },
    ).json()
    assert updated["amount"] == 55.5
    assert updated["categoryName"] == "Dining"

    assert client.delete(f"/api/transactions/{transaction_id}").status_code == 204
    assert client.get("/api/months/2026-07").json()["expenses"] == []


def test_manual_income_moves_cash_and_net_worth(
    client: TestClient, cash_account: Account, db: Session
) -> None:
    """Chase never reports income, so it's always entered by hand — it has to
    roll into cash/net worth the same way a Chase-imported expense does."""
    create(client, "2026-07", amount=500, categoryId="cat-main-income", description="Freelance")
    assert cash_balance(db) == STARTING_CASH + Decimal("500")
    assert net_worth_total(db) == STARTING_CASH + Decimal("500")


def test_manual_expense_moves_cash_and_net_worth(
    client: TestClient, cash_account: Account, db: Session
) -> None:
    create(client, "2026-07", amount=42.50, categoryId="cat-groceries", description="Snacks")
    assert cash_balance(db) == STARTING_CASH - Decimal("42.50")
    assert net_worth_total(db) == STARTING_CASH - Decimal("42.50")


def test_updating_a_transaction_reverses_the_old_cash_effect(
    client: TestClient, cash_account: Account, db: Session
) -> None:
    created = create(client, "2026-07", amount=100, categoryId="cat-groceries", description="Groceries")
    assert cash_balance(db) == STARTING_CASH - Decimal("100")

    client.put(
        f"/api/transactions/{created['id']}",
        json={"date": "2026-07-10", "amount": 30, "description": "Groceries", "categoryId": "cat-groceries"},
    )
    assert cash_balance(db) == STARTING_CASH - Decimal("30")
    assert net_worth_total(db) == STARTING_CASH - Decimal("30")


def test_updating_a_transactions_category_flips_its_cash_direction(
    client: TestClient, cash_account: Account, db: Session
) -> None:
    created = create(client, "2026-07", amount=100, categoryId="cat-groceries", description="Oops")
    assert cash_balance(db) == STARTING_CASH - Decimal("100")

    # Turns out it was a refund, not an expense.
    client.put(
        f"/api/transactions/{created['id']}",
        json={"date": "2026-07-05", "amount": 100, "description": "Refund", "categoryId": "cat-main-income"},
    )
    assert cash_balance(db) == STARTING_CASH + Decimal("100")


def test_moving_a_transaction_across_months_keeps_its_cash_effect(
    client: TestClient, cash_account: Account, db: Session
) -> None:
    """The edit reverses the old effect and applies the new one; changing the
    month must not make it count twice or not at all."""
    created = create(client, "2026-07", amount=100, categoryId="cat-groceries", description="Groceries")

    client.put(
        f"/api/transactions/{created['id']}",
        json={"date": "2026-08-05", "amount": 100, "description": "Groceries", "categoryId": "cat-groceries"},
    )

    assert cash_balance(db) == STARTING_CASH - Decimal("100")


def test_deleting_a_transaction_reverses_its_cash_effect(
    client: TestClient, cash_account: Account, db: Session
) -> None:
    created = create(client, "2026-07", amount=250, categoryId="cat-main-income", description="Bonus")
    assert cash_balance(db) == STARTING_CASH + Decimal("250")

    assert client.delete(f"/api/transactions/{created['id']}").status_code == 204
    assert cash_balance(db) == STARTING_CASH
    assert net_worth_total(db) == STARTING_CASH


def test_invalid_month_key_is_422(client: TestClient) -> None:
    response = client.get("/api/months/2026-13")
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid month: 2026-13"


def test_month_outside_ledger_range_is_404(client: TestClient) -> None:
    response = client.get("/api/months/2030-01")
    assert response.status_code == 404
    assert response.json()["detail"] == "2030-01 is outside the ledger range."


def test_date_must_fall_in_the_posted_month(client: TestClient) -> None:
    response = client.post(
        "/api/months/2026-07/transactions",
        json={
            "date": "2026-08-05",
            "amount": 10,
            "description": "x",
            "categoryId": "cat-rent",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Date 2026-08-05 does not fall in 2026-07."


def test_amount_must_be_positive(client: TestClient) -> None:
    response = client.post(
        "/api/months/2026-07/transactions",
        json={"date": "2026-07-05", "amount": 0, "description": "x", "categoryId": "cat-rent"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Amount must be greater than zero."


def test_description_is_required(client: TestClient) -> None:
    response = client.post(
        "/api/months/2026-07/transactions",
        json={"date": "2026-07-05", "amount": 5, "description": "   ", "categoryId": "cat-rent"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Description is required."


def test_unknown_category_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/months/2026-07/transactions",
        json={"date": "2026-07-05", "amount": 5, "description": "x", "categoryId": "cat-nope"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Unknown category: cat-nope"


def test_missing_transaction_is_404(client: TestClient) -> None:
    assert client.delete("/api/transactions/9999").status_code == 404
    assert client.delete("/api/transactions/not-a-number").status_code == 404
