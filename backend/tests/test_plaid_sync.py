"""Plaid sync: applies bank transactions straight to the ledger, no confirm step.

Nothing reviews these before they land, so what matters most is that a sync
can't double-count: re-running one, a transaction already entered by hand, and
the two halves of a transfer between linked accounts all have to be
recognised.

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

from app.models import Account, ImportBatch, PlaidItem, Transaction
from app.services import batches, plaid_link, plaid_sync
from app.services.crypto import encrypt_token

STARTING_CASH = 10000


@pytest.fixture
def cash_account(client: TestClient, db: Session) -> Account:
    account = db.scalar(select(Account).where(Account.type == "cash"))
    client.put(f"/api/accounts/{account.id}", json={"balance": STARTING_CASH})
    # The PUT above runs in the client's own session; expire so `db`, which
    # most tests here use directly, re-reads the balance it just set instead
    # of serving its stale cache.
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
        account_id: str = "acct-checking",
        authorized_date: date | None = None,
    ) -> None:
        self.transaction_id = transaction_id
        self.account_id = account_id
        #: Plaid's posted date.
        self.date = txn_date
        #: When the purchase actually happened; absent for anything not
        #: separately authorised, like a direct deposit.
        self.authorized_date = authorized_date
        self.name = name
        self.amount = amount
        self.pending = pending
        self.personal_finance_category = FakePFC(category) if category else None


class FakeSyncResponse:
    def __init__(self, added: list[FakeTxn], next_cursor: str, has_more: bool = False) -> None:
        self.added = added
        self.next_cursor = next_cursor
        self.has_more = has_more


class FakeInvestmentTxn:
    def __init__(self, txn_date: date, amount: float) -> None:
        self.date = txn_date
        self.amount = amount


class FakeInvestmentsTxnResponse:
    def __init__(self, txns: list[FakeInvestmentTxn]) -> None:
        self.investment_transactions = txns


class FakePlaidClient:
    """Returns one canned page per `transactions_sync` call, in order.

    `investment_transactions` defaults to empty, which is what an item without
    investments consent effectively looks like.
    """

    def __init__(
        self,
        pages: list[FakeSyncResponse],
        investment_transactions: list[FakeInvestmentTxn] | None = None,
    ) -> None:
        self._pages = list(pages)
        self._investments = investment_transactions or []
        self.calls = 0

    def transactions_sync(self, request):  # noqa: ANN001 - test double
        response = self._pages[min(self.calls, len(self._pages) - 1)]
        self.calls += 1
        return response

    def investments_transactions_get(self, request):  # noqa: ANN001 - test double
        return FakeInvestmentsTxnResponse(self._investments)


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


def _patch_sync_client(
    monkeypatch,
    pages: list[FakeSyncResponse],
    investment_transactions: list[FakeInvestmentTxn] | None = None,
) -> FakePlaidClient:
    fake = FakePlaidClient(pages, investment_transactions)
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


def test_purchase_is_dated_when_it_was_authorized(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """A card purchase posts a few days after it happens. Dating it by the
    posted date drags an end-of-month purchase into the next month's ledger,
    which is the month the spending did not occur in."""
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    FakeTxn(
                        "p-1",
                        date(2026, 8, 3),  # posted
                        "RENT",
                        823.99,
                        category="RENT_AND_UTILITIES",
                        authorized_date=date(2026, 7, 30),
                    )
                ],
                next_cursor="cursor-1",
            )
        ],
    )

    result = plaid_sync.sync_item(db, plaid_item)

    txn = db.scalar(select(Transaction).where(Transaction.plaid_transaction_id == "p-1"))
    assert txn.date == date(2026, 7, 30)
    assert result.month_key == "2026-07"


def test_falls_back_to_posted_date_when_never_authorized(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """Direct deposits and transfers carry no authorised date — posted is the
    only date there is."""
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[FakeTxn("p-1", date(2026, 8, 3), "PAYROLL", -3200.00, category="INCOME")],
                next_cursor="cursor-1",
            )
        ],
    )

    plaid_sync.sync_item(db, plaid_item)

    txn = db.scalar(select(Transaction).where(Transaction.plaid_transaction_id == "p-1"))
    assert txn.date == date(2026, 8, 3)


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


def test_matched_transfer_pair_is_dropped(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """A card payment seen from both linked accounts is one real event, and
    counting it twice inflates income and expenses by the same amount while
    the itemised card purchases are already in the ledger."""
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    # Real shape, straight from a production sync: the funding
                    # side is LOAN_PAYMENTS, the card side LOAN_DISBURSEMENTS.
                    FakeTxn("p-1", date(2026, 8, 3), "Payment to Chase card", 54.14, category="LOAN_PAYMENTS"),
                    FakeTxn(
                        "p-2",
                        date(2026, 8, 3),
                        "Payment Thank You-Mobile",
                        -54.14,
                        category="LOAN_DISBURSEMENTS",
                        account_id="acct-card",
                    ),
                    FakeTxn("p-3", date(2026, 8, 3), "Food Lion", 17.30, category="FOOD_AND_DRINK"),
                ],
                next_cursor="cursor-1",
            )
        ],
    )

    result = plaid_sync.sync_item(db, plaid_item)

    assert result.imported_count == 1
    assert result.cash_delta == Decimal("-17.30")
    assert {t.plaid_transaction_id for t in db.scalars(select(Transaction)).unique()} == {"p-3"}


def test_transfer_into_a_brokerage_is_not_an_expense(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """Money moved into a brokerage is still yours, sitting in an account whose
    value Custodian already tracks through holdings. The receiving side is
    investment activity, so it never appears in the transaction stream and the
    outgoing half would otherwise look like spending."""
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    FakeTxn("p-1", date(2026, 8, 4), "Manual DB-Bkrg", 1000.00, category="TRANSFER_OUT"),
                    FakeTxn("p-2", date(2026, 8, 4), "Food Lion", 17.30, category="FOOD_AND_DRINK"),
                ],
                next_cursor="cursor-1",
            )
        ],
        investment_transactions=[FakeInvestmentTxn(date(2026, 8, 4), 1000.00)],
    )

    result = plaid_sync.sync_item(db, plaid_item)

    assert result.imported_count == 1
    assert result.cash_delta == Decimal("-17.30")
    assert {t.plaid_transaction_id for t in db.scalars(select(Transaction)).unique()} == {"p-2"}


def test_ordinary_spending_is_not_paired_against_a_trade(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """A purchase that happens to match a trade's value is not a transfer —
    only transfer-category rows are eligible to pair."""
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[FakeTxn("p-1", date(2026, 8, 4), "NIKE.COM", 288.80, category="GENERAL_MERCHANDISE")],
                next_cursor="cursor-1",
            )
        ],
        investment_transactions=[FakeInvestmentTxn(date(2026, 8, 4), 288.80)],
    )

    result = plaid_sync.sync_item(db, plaid_item)

    assert result.imported_count == 1
    assert result.cash_delta == Decimal("-288.80")


def test_unpaired_transfers_are_kept(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """Only *matched* pairs are double entries. A payment to a card that was
    never linked is the sole record of that spending, and an incoming transfer
    with no matching outgoing is real money arriving — both must survive."""
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    # Amex isn't linked, so its purchases are invisible and
                    # this payment is the only record of that spending.
                    FakeTxn("p-1", date(2026, 8, 3), "AMERICAN EXPRESS ACH PMT", 41.25, category="LOAN_PAYMENTS"),
                    FakeTxn("p-2", date(2026, 8, 4), "REAL TIME TRANSFER RECD", -397.41, category="TRANSFER_IN"),
                ],
                next_cursor="cursor-1",
            )
        ],
    )

    result = plaid_sync.sync_item(db, plaid_item)

    assert result.imported_count == 2
    assert result.cash_delta == Decimal("356.16")  # 397.41 in - 41.25 out


def test_equal_amounts_in_the_same_direction_are_not_paired(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """Two like-sized purchases are not a transfer — pairing needs opposite
    directions, not merely a coincidental amount match."""
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    FakeTxn("p-1", date(2026, 8, 3), "Transfer out A", 25.00, category="TRANSFER_OUT"),
                    FakeTxn("p-2", date(2026, 8, 3), "Transfer out B", 25.00, category="TRANSFER_OUT"),
                ],
                next_cursor="cursor-1",
            )
        ],
    )

    result = plaid_sync.sync_item(db, plaid_item)

    assert result.imported_count == 2


def test_non_transfer_categories_are_never_paired(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """A refund that happens to match a purchase's amount is not a transfer."""
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    FakeTxn("p-1", date(2026, 8, 3), "Coffee", 4.50, category="FOOD_AND_DRINK"),
                    FakeTxn("p-2", date(2026, 8, 3), "Coffee refund", -4.50, category="FOOD_AND_DRINK"),
                ],
                next_cursor="cursor-1",
            )
        ],
    )

    result = plaid_sync.sync_item(db, plaid_item)

    assert result.imported_count == 2


def test_transfer_pair_outside_the_window_is_kept(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    FakeTxn("p-1", date(2026, 8, 1), "Payment to card", 60.00, category="LOAN_PAYMENTS"),
                    FakeTxn(
                        "p-2",
                        date(2026, 8, 20),
                        "Payment Thank You",
                        -60.00,
                        category="LOAN_DISBURSEMENTS",
                        account_id="acct-card",
                    ),
                ],
                next_cursor="cursor-1",
            )
        ],
    )

    result = plaid_sync.sync_item(db, plaid_item)

    assert result.imported_count == 2


def test_offsetting_amounts_within_one_account_are_not_paired(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """A transfer moves money *between* accounts. Two offsetting entries on the
    same account are something else and must not be silently dropped."""
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    FakeTxn("p-1", date(2026, 8, 3), "Transfer out", 25.00, category="TRANSFER_OUT"),
                    FakeTxn("p-2", date(2026, 8, 3), "Transfer reversed", -25.00, category="TRANSFER_IN"),
                ],
                next_cursor="cursor-1",
            )
        ],
    )

    result = plaid_sync.sync_item(db, plaid_item)

    assert result.imported_count == 2


def test_transfer_pairs_against_a_transfer_already_in_the_ledger(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """The two halves of a card payment arrive in separate syncs when the card
    is a different linked institution — and linking one replays its whole
    history at once, so its credits land well after the payments were stored.
    The stored half has to be removed retroactively."""
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    FakeTxn("p-1", date(2026, 8, 3), "AMEX ACH PMT", 41.25, category="LOAN_PAYMENTS"),
                ],
                next_cursor="cursor-1",
            )
        ],
    )
    first = plaid_sync.sync_item(db, plaid_item)
    assert first.imported_count == 1
    after_first = cash_balance(db)

    # A second institution (the card) syncs later and brings the other half.
    second_item = PlaidItem(
        item_id="item-amex",
        access_token_encrypted=encrypt_token("access-amex"),
        institution_name="Amex",
    )
    db.add(second_item)
    db.commit()

    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    FakeTxn(
                        "p-2",
                        date(2026, 8, 4),
                        "Payment received - thank you",
                        -41.25,
                        category="LOAN_DISBURSEMENTS",
                        account_id="acct-amex",
                    ),
                ],
                next_cursor="cursor-amex-1",
            )
        ],
    )
    result = plaid_sync.sync_item(db, second_item)

    # Neither half survives, and the cash the stored one moved is given back.
    assert result is None
    assert db.scalar(select(Transaction).limit(1)) is None
    assert cash_balance(db) == after_first + Decimal("41.25") == STARTING_CASH


def test_unwinding_keeps_the_earlier_batch_reversible(
    monkeypatch, db: Session, cash_account: Account, plaid_item: PlaidItem
) -> None:
    """Removing a transaction from an already-stored batch has to correct that
    batch's cash_delta, or a later `delete_batch` reverses an amount that no
    longer matches the transactions it deletes."""
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    FakeTxn("p-1", date(2026, 8, 3), "AMEX ACH PMT", 41.25, category="LOAN_PAYMENTS"),
                    FakeTxn("p-2", date(2026, 8, 3), "Food Lion", 17.30, category="FOOD_AND_DRINK"),
                ],
                next_cursor="cursor-1",
            )
        ],
    )
    first = plaid_sync.sync_item(db, plaid_item)
    assert first.cash_delta == Decimal("-58.55")

    second_item = PlaidItem(
        item_id="item-amex",
        access_token_encrypted=encrypt_token("access-amex"),
        institution_name="Amex",
    )
    db.add(second_item)
    db.commit()
    _patch_sync_client(
        monkeypatch,
        [
            FakeSyncResponse(
                added=[
                    FakeTxn(
                        "p-3",
                        date(2026, 8, 3),
                        "Payment received",
                        -41.25,
                        category="LOAN_DISBURSEMENTS",
                        account_id="acct-amex",
                    ),
                ],
                next_cursor="cursor-amex-1",
            )
        ],
    )
    plaid_sync.sync_item(db, second_item)

    batch = db.get(ImportBatch, first.batch_id)
    assert batch.cash_delta == Decimal("-17.30")  # corrected, was -58.55
    assert batch.imported_count == 1

    # The corrected delta is what makes the undo land exactly back at the start.
    batches.delete_batch(db, first.batch_id)
    assert cash_balance(db) == STARTING_CASH


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
