"""Chase import: the preview writes nothing, and confirming rolls net worth forward.

The roll-forward is the behaviour most worth pinning down — it is the one place
where confirming an import moves money outside the ledger, and re-running it
must never double-count.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, NetWorthSnapshot, Transaction

# Income 3200.00 + 22.50 refund, expenses 523.92 -> net cash movement.
EXPECTED_CASH_DELTA = Decimal("2698.58")
STARTING_CASH = 10000


@pytest.fixture
def cash_account(client: TestClient, db: Session) -> Account:
    account = db.scalar(select(Account).where(Account.type == "cash"))
    client.put(f"/api/accounts/{account.id}", json={"balance": STARTING_CASH})
    return account


def upload(client: TestClient, content: bytes, filename: str) -> dict:
    response = client.post(
        "/api/import/chase", files={"file": (filename, content, "text/csv")}
    )
    assert response.status_code == 200
    return response.json()


def cash_balance(db: Session) -> Decimal:
    db.expire_all()
    return db.scalar(select(Account.balance).where(Account.type == "cash"))


def test_preview_writes_nothing(client: TestClient, credit_card_csv: bytes, db: Session) -> None:
    preview = upload(client, credit_card_csv, "chase_credit_2026-08.csv")

    assert preview["detectedMonthKey"] == "2026-08"
    assert len(preview["transactions"]) == 13
    assert db.scalar(select(Transaction).limit(1)) is None


def test_preview_maps_categories_and_flags_the_rest(
    client: TestClient, credit_card_csv: bytes
) -> None:
    rows = {t["description"]: t for t in upload(client, credit_card_csv, "chase.csv")["transactions"]}

    mapped = rows["WHOLEFDS MKT #10259"]
    assert mapped["categoryId"] == "cat-groceries"
    assert mapped["flaggedForReview"] is False

    # A refund is income, so an expense mapping cannot be used for it.
    refund = rows["RETURN - AMAZON"]
    assert refund["kind"] == "income"
    assert refund["categoryId"] == "cat-main-income"
    assert refund["flaggedForReview"] is True


def test_unsupported_file_type_is_415(client: TestClient) -> None:
    response = client.post("/api/import/chase", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 415
    assert response.json()["detail"] == "Please upload a Chase export as .csv, .xls, .xlsx or .pdf."


def test_empty_file_is_422(client: TestClient) -> None:
    response = client.post("/api/import/chase", files={"file": ("empty.csv", b"", "text/csv")})
    assert response.status_code == 422


def test_confirm_rolls_cash_and_net_worth_forward(
    client: TestClient, credit_card_csv: bytes, cash_account: Account, db: Session
) -> None:
    preview = upload(client, credit_card_csv, "chase_credit_2026-08.csv")
    result = client.post("/api/import/chase/confirm", json=preview).json()

    assert result["importedCount"] == 13
    assert Decimal(str(result["cashDelta"])) == EXPECTED_CASH_DELTA
    assert Decimal(str(result["newNetWorthTotal"])) == STARTING_CASH + EXPECTED_CASH_DELTA

    assert cash_balance(db) == STARTING_CASH + EXPECTED_CASH_DELTA

    ledger = client.get("/api/months/2026-08").json()
    assert ledger["net"] == float(EXPECTED_CASH_DELTA)
    assert len(ledger["income"]) == 2
    assert len(ledger["expenses"]) == 11


def test_imported_transactions_carry_their_batch(
    client: TestClient, credit_card_csv: bytes, cash_account: Account, db: Session
) -> None:
    preview = upload(client, credit_card_csv, "chase.csv")
    client.post("/api/import/chase/confirm", json=preview)

    transactions = list(db.scalars(select(Transaction)).unique())
    assert all(t.source == "chase_import" for t in transactions)
    assert {t.import_batch_id for t in transactions} == {preview["batchId"]}


def test_reconfirming_the_same_batch_is_rejected_and_changes_nothing(
    client: TestClient, credit_card_csv: bytes, cash_account: Account, db: Session
) -> None:
    preview = upload(client, credit_card_csv, "chase.csv")
    client.post("/api/import/chase/confirm", json=preview)
    after_first = cash_balance(db)

    response = client.post("/api/import/chase/confirm", json=preview)
    assert response.status_code == 409
    assert response.json()["detail"] == "This import has already been confirmed."

    assert cash_balance(db) == after_first
    assert len(list(db.scalars(select(Transaction)).unique())) == 13


def test_excluded_rows_are_skipped(
    client: TestClient, credit_card_csv: bytes, cash_account: Account
) -> None:
    preview = upload(client, credit_card_csv, "chase.csv")
    for row in preview["transactions"]:
        if row["kind"] == "income":
            row["include"] = False

    result = client.post("/api/import/chase/confirm", json=preview).json()

    assert result["importedCount"] == 11
    # Only expenses remain, so cash moves down.
    assert result["cashDelta"] == -523.92


def test_confirming_nothing_is_rejected(
    client: TestClient, credit_card_csv: bytes, cash_account: Account
) -> None:
    preview = upload(client, credit_card_csv, "chase.csv")
    for row in preview["transactions"]:
        row["include"] = False

    response = client.post("/api/import/chase/confirm", json=preview)
    assert response.status_code == 422
    assert response.json()["detail"] == "No transactions selected to import."


def test_deleting_a_batch_undoes_it(
    client: TestClient, credit_card_csv: bytes, cash_account: Account, db: Session
) -> None:
    preview = upload(client, credit_card_csv, "chase.csv")
    client.post("/api/import/chase/confirm", json=preview)

    assert client.delete(f"/api/import/batches/{preview['batchId']}").status_code == 204

    assert cash_balance(db) == STARTING_CASH
    assert db.scalar(select(Transaction).limit(1)) is None
    assert client.get("/api/months/2026-08").json()["net"] == 0


def test_batch_can_be_reimported_after_undo(
    client: TestClient, credit_card_csv: bytes, cash_account: Account, db: Session
) -> None:
    preview = upload(client, credit_card_csv, "chase.csv")
    client.post("/api/import/chase/confirm", json=preview)
    client.delete(f"/api/import/batches/{preview['batchId']}")

    response = client.post("/api/import/chase/confirm", json=preview)
    assert response.status_code == 200
    assert cash_balance(db) == STARTING_CASH + EXPECTED_CASH_DELTA


def test_deleting_an_unknown_batch_is_404(client: TestClient) -> None:
    assert client.delete("/api/import/batches/batch-nope").status_code == 404


def test_spending_report_pdf_confirms(
    client: TestClient, spending_report_pdf: bytes, cash_account: Account, db: Session
) -> None:
    """The fixture spans July (Groceries) and August (Bills & Utilities) —
    both months' transactions should be proposed, none of them pre-existing,
    and confirming should snapshot net worth for both months touched."""
    preview = upload(client, spending_report_pdf, "chase_spending_report_2026.pdf")
    assert {t["date"][:7] for t in preview["transactions"]} == {"2026-07", "2026-08"}
    assert len(preview["transactions"]) == 4
    assert all(t["alreadyImported"] is False and t["include"] is True for t in preview["transactions"])

    result = client.post("/api/import/chase/confirm", json=preview).json()
    # -54.32 WHOLE FOODS -32.10 TRADER JOES -120.00 CON EDISON +15.00 REFUND ADJUSTMENT
    assert result["cashDelta"] == -191.42
    assert cash_balance(db) == STARTING_CASH - Decimal("191.42")

    snapshotted_months = {row.month_key for row in db.scalars(select(NetWorthSnapshot))}
    assert snapshotted_months == {"2026-07", "2026-08"}


def test_spending_report_pdf_skips_transactions_already_in_the_ledger(
    client: TestClient, spending_report_pdf: bytes, cash_account: Account, db: Session
) -> None:
    """The Spending Report is a running year-to-date summary, so a re-upload
    always contains every prior month too. A transaction already in the
    ledger — however it got there — must come back proposed but unchecked
    rather than risk double-counting, while genuinely new ones stay checked."""
    client.post(
        "/api/months/2026-07/transactions",
        json={
            "date": "2026-07-05",
            "amount": 54.32,
            "description": "WHOLE FOODS MARKET",
            "categoryId": "cat-groceries",
        },
    )

    preview = upload(client, spending_report_pdf, "chase_spending_report_2026.pdf")
    rows = {t["description"]: t for t in preview["transactions"]}

    already_there = rows["WHOLE FOODS MARKET"]
    assert already_there["alreadyImported"] is True
    assert already_there["include"] is False

    for description in ("TRADER JOES", "CON EDISON", "REFUND ADJUSTMENT"):
        assert rows[description]["alreadyImported"] is False
        assert rows[description]["include"] is True

    result = client.post("/api/import/chase/confirm", json=preview).json()
    assert result["importedCount"] == 3
    # -32.10 TRADER JOES -120.00 CON EDISON +15.00 REFUND ADJUSTMENT (WHOLE FOODS skipped)
    assert result["cashDelta"] == -137.10


def test_checking_export_confirms(
    client: TestClient, checking_csv: bytes, cash_account: Account, db: Session
) -> None:
    preview = upload(client, checking_csv, "chase_checking_2026-09.csv")
    assert preview["detectedMonthKey"] == "2026-09"

    result = client.post("/api/import/chase/confirm", json=preview).json()
    # 3350.00 income - 2252.00 expenses
    assert result["cashDelta"] == 1098.0
    assert cash_balance(db) == STARTING_CASH + Decimal("1098.00")
