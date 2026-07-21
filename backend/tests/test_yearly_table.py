"""The yearly table is derived from transactions, never stored."""

from fastapi.testclient import TestClient

from app.months import month_keys_in_year


def add(client: TestClient, iso_date: str, amount: float, category_id: str) -> None:
    client.post(
        f"/api/months/{iso_date[:7]}/transactions",
        json={
            "date": iso_date,
            "amount": amount,
            "description": "entry",
            "categoryId": category_id,
        },
    )


def test_rows_cover_the_ledger_months_of_that_year(client: TestClient) -> None:
    table = client.get("/api/yearly-table?year=2026").json()
    assert [r["monthKey"] for r in table["rows"]] == month_keys_in_year(2026)
    # 2026 only opens in July, so six rows rather than twelve.
    assert len(table["rows"]) == 6


def test_columns_are_the_visible_categories(client: TestClient) -> None:
    table = client.get("/api/yearly-table?year=2026").json()
    categories = client.get("/api/categories").json()
    assert [c["id"] for c in table["columns"]] == [c["id"] for c in categories]


def test_cells_and_totals_aggregate_by_category(client: TestClient) -> None:
    add(client, "2026-07-04", 128.75, "cat-groceries")
    add(client, "2026-07-11", 94.20, "cat-groceries")
    add(client, "2026-07-01", 3200, "cat-main-income")
    add(client, "2026-08-03", 103.27, "cat-groceries")
    add(client, "2026-08-01", 3200, "cat-main-income")

    table = client.get("/api/yearly-table?year=2026").json()
    rows = {r["monthKey"]: r for r in table["rows"]}

    assert rows["2026-07"]["cells"]["cat-groceries"] == 222.95
    assert rows["2026-07"]["totalIncome"] == 3200
    assert rows["2026-07"]["totalExpenses"] == 222.95
    assert rows["2026-07"]["net"] == 2977.05

    assert rows["2026-08"]["cells"]["cat-groceries"] == 103.27
    assert rows["2026-09"]["cells"] == {}

    totals = table["totals"]
    assert totals["cells"]["cat-groceries"] == 326.22
    assert totals["cells"]["cat-main-income"] == 6400
    assert totals["totalIncome"] == 6400
    assert totals["totalExpenses"] == 326.22
    assert totals["net"] == 6073.78


def test_table_agrees_with_the_monthly_ledger(client: TestClient) -> None:
    """The invariant: both read the same transactions, so they cannot diverge."""
    add(client, "2026-07-04", 128.75, "cat-groceries")
    add(client, "2026-07-06", 78.00, "cat-dining")
    add(client, "2026-07-01", 3200, "cat-main-income")

    ledger = client.get("/api/months/2026-07").json()
    row = next(r for r in client.get("/api/yearly-table?year=2026").json()["rows"] if r["monthKey"] == "2026-07")

    assert row["totalIncome"] == ledger["totalIncome"]
    assert row["totalExpenses"] == ledger["totalExpenses"]
    assert row["net"] == ledger["net"]


def test_deleting_a_transaction_updates_the_table(client: TestClient) -> None:
    created = client.post(
        "/api/months/2026-07/transactions",
        json={
            "date": "2026-07-04",
            "amount": 50,
            "description": "entry",
            "categoryId": "cat-groceries",
        },
    ).json()

    client.delete(f"/api/transactions/{created['id']}")
    table = client.get("/api/yearly-table?year=2026").json()
    assert table["totals"]["cells"] == {}
    assert table["totals"]["totalExpenses"] == 0


def test_year_outside_the_ledger_returns_no_rows(client: TestClient) -> None:
    table = client.get("/api/yearly-table?year=2020").json()
    assert table["rows"] == []
    assert table["totals"]["net"] == 0
