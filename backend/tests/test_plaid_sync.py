"""Plaid sync: applies bank transactions straight to the ledger, no confirm step.

Mirrors `test_import_confirm.py`'s conventions. What's worth pinning down here
is different from the Chase upload path, though: there's no human review, so
idempotency (re-running a sync must never double-count) and cross-path dedup
(a Plaid-synced transaction and a manually entered or Chase-uploaded one must
recognise each other) matter more than category-mapping UX.

The Plaid SDK boundary (`get_plaid_client`) is monkeypatched with a small fake
per test — no real network, same approach the rest of the suite takes for
external feeds.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, PlaidItem, Transaction
from app.services import plaid_link, plaid_sync
from app.services.crypto import encrypt_token

STARTING_CASH = 10000


@pytest.fixture
def cash_account(client: TestClient, db: Session) -> Account:
    account = db.scalar(select(Account).where(Account.type == "cash"))
    client.put(f"/api/accounts/{account.id}", json={"balance": STARTING_CASH})
    # The PUT above runs in the client's own session; expire so `db` (used
    # directly by several tests here, unlike the HTTP-only Chase import
    # tests) re-reads the balance it just set instead of its stale cache.
    db.expire_all()
    return account


def cash_balance(db: Session) -> Decimal:
    db.expire_all()
    return db.scalar(select(Account.balance).where(Account.type == "cash"))


@pytest.fixture
def plaid_item(db: Session) -> PlaidItem:
    item = PlaidItem(
        item_id="item-1",
        access_token_encrypted=encrypt_token("access-sandbox-1"),
        institution_name="Chase",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Fakes for the Plaid SDK boundary
# ---------------------------------------------------------------------------


class FakePFC:
    def __init__(self, primary: str) -> None:
        self.primary = primary


class FakeTxn:
    def __init__(
        self,
        transaction_id: str,
        txn_date: date,
        name: str,
        amount: float,
        *,
        pending: bool = False,
        category: str | None = None,
    ) -> None:
        self.transaction_id = transaction_id
        self.date = txn_date
        self.name = name
        self.amount = amount
        self.pending = pending
        self.personal_finance_category = FakePFC(category) if category else None


class FakeSyncResponse:
    def __init__(self, added: list[FakeTxn], next_cursor: str, has_more: bool = False) -> None:
        self.added = added
        self.next_cursor = next_cursor
        self.has_more = has_more


class FakePlaidClient:
    """Returns one canned page per `transactions_sync` call, in order."""

    def __init__(self, pages: list[FakeSyncResponse]) -> None:
        self._pages = list(pages)
        self.calls = 0

    def transactions_sync(self, request):  # noqa: ANN001 - test double
        response = self._pages[min(self.calls, len(self._pages) - 1)]
        self.calls += 1
        return response


class FakeExchangeResponse:
    def __init__(self, access_token: str, item_id: str) -> None:
        self.access_token = access_token
        self.item_id = item_id


class FakeLinkTokenResponse:
    def __init__(self, link_token: str) -> None:
        self.link_token = link_token


class FakeLinkClient:
    def __init__(self, link_token="link-sandbox-abc", item_id="item-99", access_token="access-99") -> None:
        self.link_token = link_token
        self.item_id = item_id
        self.access_token = access_token
        self.removed: list[str] = []

    def link_token_create(self, request):  # noqa: ANN001 - test double
        return FakeLinkTokenResponse(self.link_token)

    def item_public_token_exchange(self, request):  # noqa: ANN001 - test double
        return FakeExchangeResponse(self.access_token, self.item_id)

    def item_remove(self, request) -> None:  # noqa: ANN001 - test double
        self.removed.append(request.access_token)


def _patch_sync_client(monkeypatch, pages: list[FakeSyncResponse]) -> FakePlaidClient:
    fake = FakePlaidClient(pages)
    monkeypatch.setattr(plaid_sync, "get_plaid_client", lambda: fake)
    return fake


# ---------------------------------------------------------------------------
# Core sync behaviour
# ---------------------------------------------------------------------------


def test_sync_applies_new_transactions_and_rolls_cash_forward(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    FakeTxn("p-1", date(2026, 8, 3), "WHOLE FOODS MARKET", 54.32, category="FOOD_AND_DRINK"),
                    FakeTxn("p-2", date(2026, 8, 5), "ACME CORP PAYROLL", -3200.00, category="INCOME"),
                ],
                next_cursor="cursor-1",
            )
        ],
    )

    result = plaid_sync.sync_item(db, plaid_item)

    assert result is not None
    assert result.imported_count == 2
    assert result.cash_delta == Decimal("3145.68")  # +3200 income - 54.32 expense
    assert cash_balance(db) == STARTING_CASH + Decimal("3145.68")

    db.refresh(plaid_item)
    assert plaid_item.cursor == "cursor-1"
    assert plaid_item.status == "active"

    transactions = list(db.scalars(select(Transaction)).unique())
    assert {t.plaid_transaction_id for t in transactions} == {"p-1", "p-2"}
    assert all(t.source == "plaid" for t in transactions)


def test_sync_is_idempotent_on_rerun(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    _patch_sync_client(
        monkeypatch,
        [FakeSyncResponse(added=[FakeTxn("p-1", date(2026, 8, 3), "COFFEE", 5.00)], next_cursor="cursor-1")],
    )
    plaid_sync.sync_item(db, plaid_item)
    after_first = cash_balance(db)

    _patch_sync_client(monkeypatch, [FakeSyncResponse(added=[], next_cursor="cursor-2")])
    result = plaid_sync.sync_item(db, plaid_item)

    assert result is None
    assert cash_balance(db) == after_first
    db.refresh(plaid_item)
    assert plaid_item.cursor == "cursor-2"
    assert len(list(db.scalars(select(Transaction)).unique())) == 1


def test_sync_skips_pending_transactions(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[FakeTxn("p-1", date(2026, 8, 3), "PENDING CHARGE", 20.00, pending=True)],
                next_cursor="cursor-1",
            )
        ],
    )
    result = plaid_sync.sync_item(db, plaid_item)

    assert result is None
    assert cash_balance(db) == STARTING_CASH
    db.refresh(plaid_item)
    assert plaid_item.cursor == "cursor-1"


def test_cross_path_dedup_against_manual_entry(
    client: TestClient, monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    client.post(
        "/api/months/2026-08/transactions",
        json={
            "date": "2026-08-03",
            "amount": 54.32,
            "description": "WHOLE FOODS MARKET",
            "categoryId": "cat-groceries",
        },
    )
    after_manual = cash_balance(db)

    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[FakeTxn("p-1", date(2026, 8, 3), "WHOLE FOODS MARKET", 54.32, category="FOOD_AND_DRINK")],
                next_cursor="cursor-1",
            )
        ],
    )
    result = plaid_sync.sync_item(db, plaid_item)

    assert result is None
    assert cash_balance(db) == after_manual
    assert len(list(db.scalars(select(Transaction)).unique())) == 1


def test_plaid_sourced_transaction_blocks_a_later_chase_upload(
    client: TestClient, monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[FakeTxn("p-1", date(2026, 8, 3), "WHOLE FOODS MARKET", 54.32, category="FOOD_AND_DRINK")],
                next_cursor="cursor-1",
            )
        ],
    )
    plaid_sync.sync_item(db, plaid_item)

    csv_content = (
        b"Transaction Date,Description,Category,Amount\n"
        b"08/03/2026,WHOLE FOODS MARKET,Groceries,-54.32\n"
    )
    response = client.post("/api/import/chase", files={"file": ("chase.csv", csv_content, "text/csv")})
    row = response.json()["transactions"][0]

    assert row["alreadyImported"] is True
    assert row["include"] is False


def test_unmapped_plaid_category_falls_back_to_other(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[FakeTxn("p-1", date(2026, 8, 3), "SOME SHOP", 20.00, category="MYSTERY_CATEGORY")],
                next_cursor="cursor-1",
            )
        ],
    )
    plaid_sync.sync_item(db, plaid_item)

    txn = db.scalar(select(Transaction).where(Transaction.plaid_transaction_id == "p-1"))
    assert txn.category_id == "cat-other"


def test_income_sign_convention(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """Plaid: positive amount = money out (expense), negative = money in (income) —
    the opposite of Custodian's own always-positive-amount convention."""
    _patch_sync_client(
        monkeypatch,
        [FakeSyncResponse(added=[FakeTxn("p-1", date(2026, 8, 3), "REFUND", -15.00)], next_cursor="cursor-1")],
    )
    plaid_sync.sync_item(db, plaid_item)

    txn = db.scalar(select(Transaction).where(Transaction.plaid_transaction_id == "p-1"))
    assert txn.category.kind == "income"
    assert txn.amount == Decimal("15.00")
    assert cash_balance(db) == STARTING_CASH + Decimal("15.00")


def test_reversal_via_delete_batch(
    client: TestClient, monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    _patch_sync_client(
        monkeypatch,
        [FakeSyncResponse(added=[FakeTxn("p-1", date(2026, 8, 3), "COFFEE", 5.00)], next_cursor="cursor-1")],
    )
    result = plaid_sync.sync_item(db, plaid_item)

    response = client.delete(f"/api/import/batches/{result.batch_id}")

    assert response.status_code == 204
    assert cash_balance(db) == STARTING_CASH
    assert db.scalar(select(Transaction).limit(1)) is None


# ---------------------------------------------------------------------------
# Router endpoints
# ---------------------------------------------------------------------------


def test_router_link_token(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(plaid_link, "get_plaid_client", lambda: FakeLinkClient(link_token="link-xyz"))

    response = client.post("/api/plaid/link-token")

    assert response.status_code == 200
    assert response.json()["linkToken"] == "link-xyz"


def test_router_exchange_token_runs_initial_sync(
    client: TestClient, monkeypatch, cash_account: Account
) -> None:
    monkeypatch.setattr(
        plaid_link, "get_plaid_client", lambda: FakeLinkClient(item_id="item-42", access_token="access-42")
    )
    monkeypatch.setattr(
        plaid_sync,
        "get_plaid_client",
        lambda: FakePlaidClient([FakeSyncResponse(added=[FakeTxn("p-1", date(2026, 8, 3), "COFFEE", 5.00)], next_cursor="cursor-1")]),
    )

    response = client.post(
        "/api/plaid/exchange-token", json={"publicToken": "public-sandbox-token", "institutionName": "Chase"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["itemId"] == "item-42"
    assert body["institutionName"] == "Chase"
    assert body["status"] == "active"
    assert body["lastSyncedAt"] is not None


def test_router_sync_now_and_status(
    client: TestClient, monkeypatch, cash_account: Account, plaid_item: PlaidItem
) -> None:
    monkeypatch.setattr(
        plaid_sync,
        "get_plaid_client",
        lambda: FakePlaidClient([FakeSyncResponse(added=[FakeTxn("p-1", date(2026, 8, 3), "COFFEE", 5.00)], next_cursor="cursor-1")]),
    )

    sync_response = client.post("/api/plaid/sync-now")
    assert sync_response.status_code == 200
    assert len(sync_response.json()) == 1

    status_response = client.get("/api/plaid/status")
    assert status_response.status_code == 200
    assert status_response.json()[0]["itemId"] == plaid_item.item_id


def test_router_disconnect_removes_item_but_keeps_transactions(
    client: TestClient, monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    _patch_sync_client(
        monkeypatch,
        [FakeSyncResponse(added=[FakeTxn("p-1", date(2026, 8, 3), "COFFEE", 5.00)], next_cursor="cursor-1")],
    )
    plaid_sync.sync_item(db, plaid_item)

    fake_link = FakeLinkClient()
    monkeypatch.setattr(plaid_link, "get_plaid_client", lambda: fake_link)

    response = client.delete(f"/api/plaid/items/{plaid_item.item_id}")

    assert response.status_code == 204
    assert fake_link.removed  # item_remove was called, best-effort
    assert db.scalar(select(PlaidItem).where(PlaidItem.item_id == plaid_item.item_id)) is None
    # Unlinking is not reversing — past transactions stay in the ledger.
    assert db.scalar(select(Transaction).limit(1)) is not None


def test_disconnecting_an_unknown_item_is_404(client: TestClient) -> None:
    assert client.delete("/api/plaid/items/nope").status_code == 404
