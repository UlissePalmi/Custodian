"""Account mapping: what the ledger thinks, what the bank says, and the gap.

Both balances are kept deliberately. The ledger's is the running total of
everything Custodian recorded; the bank's is the truth. Neither alone reveals
a missed or double-counted transaction — the difference between them does.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Holding, PlaidItem, Transaction
from app.services import networth, reconcile
from app.services.crypto import encrypt_token


@pytest.fixture
def plaid_item(db: Session) -> PlaidItem:
    item = PlaidItem(
        item_id="item-1",
        access_token_encrypted=encrypt_token("access-1"),
        institution_name="Chase",
    )
    db.add(item)
    db.commit()
    return item


def _patch_balances(monkeypatch, accounts: list[dict]) -> None:
    monkeypatch.setattr(reconcile, "_plaid_accounts", lambda item: accounts)


@pytest.fixture(autouse=True)
def _no_price_feed(monkeypatch):
    """Keep valuations off the network. With no quote, a holding falls back to
    its cost basis, so the figures here are whatever the test set."""
    monkeypatch.setattr(networth, "get_quotes", lambda db, tickers: {})


# ---------------------------------------------------------------------------
# Net worth
# ---------------------------------------------------------------------------


def test_credit_balance_is_subtracted_from_cash(db: Session) -> None:
    """Net worth means assets minus debts. A card holds what is owed, so it
    nets against cash rather than counting as something you have."""
    cash = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    cash.balance = Decimal("1000.00")
    db.add(Account(name="Card", type="credit", balance=Decimal("150.00"), currency="usd"))
    db.commit()

    _, breakdown = networth.compute_totals(db)

    assert breakdown["cash"] == Decimal("850.00")


def test_brokerage_cash_and_holdings_are_added_not_swapped(monkeypatch, db: Session) -> None:
    """A stocks account's balance is only its uninvested cash; the positions
    are holdings. Both count, or the account reads short."""
    brokerage = db.scalar(select(Account).where(Account.type == "stocks"))
    brokerage.balance = Decimal("198.55")
    db.add(
        Holding(
            ticker="STLA",
            name="Stellantis",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("5.00"),
            account_id=brokerage.id,
            source="plaid",
        )
    )
    db.commit()

    _, breakdown = networth.compute_totals(db)

    # No quote is cached in tests, so a holding falls back to its cost basis.
    assert breakdown["stocks"] == Decimal("698.55")


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def test_a_mapped_balance_is_taken_from_the_bank(
    monkeypatch, db: Session, plaid_item: PlaidItem
) -> None:
    """A locally accumulated balance cannot track the account it names — card
    spending lands on it and transfers are excluded — so the bank's figure
    replaces whatever was there."""
    cash = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    cash.balance = Decimal("4023.94")
    cash.plaid_account_id = "plaid-checking"
    db.commit()

    _patch_balances(
        monkeypatch,
        [{"account_id": "plaid-checking", "balances": {"current": 2729.61, "available": 2729.61}}],
    )
    reconcile.refresh_balances(db)

    db.refresh(cash)
    assert cash.balance == Decimal("2729.61")
    assert cash.plaid_balance == Decimal("2729.61")


def test_transactions_do_not_move_a_mapped_balance(
    monkeypatch, db: Session, plaid_item: PlaidItem
) -> None:
    """Nudging a bank-owned balance would double-count: the transaction is
    already reflected in the figure the bank reported."""
    cash = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    cash.balance = Decimal("2729.61")
    cash.plaid_account_id = "plaid-checking"
    db.commit()

    networth.apply_cash_effect(db, Decimal("-100.00"))
    db.commit()

    db.refresh(cash)
    assert cash.balance == Decimal("2729.61")


def test_transactions_still_move_an_unmapped_balance(db: Session) -> None:
    """Where Plaid cannot see the account, the ledger is the only record of
    the movement and must still keep it."""
    cash = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    cash.balance = Decimal("500.00")
    cash.plaid_account_id = None
    db.commit()

    networth.apply_cash_effect(db, Decimal("-100.00"))
    db.commit()

    db.refresh(cash)
    assert cash.balance == Decimal("400.00")


def test_a_single_checkpoint_cannot_drift(db: Session) -> None:
    """The offset's value is meaningless — only a change in it is a signal —
    so nothing can be said until there are two observations."""
    reconcile.checkpoint(db)

    assert reconcile.drifts(db) == []
    assert reconcile.drift_summary(db) is None


def test_recorded_spending_keeps_the_offset_steady(db: Session) -> None:
    """Money leaving with a matching entry is exactly what should *not* alarm."""
    cash = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    cash.plaid_account_id = "plaid-checking"
    cash.balance = Decimal("1000.00")
    db.commit()
    reconcile.checkpoint(db)

    # $40 spent, and the ledger knows about it.
    cash.balance = Decimal("960.00")
    db.add(
        Transaction(
            date=date(2026, 8, 3),
            amount=Decimal("40.00"),
            description="Groceries",
            category_id="cat-groceries",
            source="plaid",
        )
    )
    db.commit()
    reconcile.checkpoint(db)

    assert reconcile.drifts(db) == []


def test_unrecorded_movement_is_reported(db: Session) -> None:
    """Money that left with no entry behind it is the whole point of the check."""
    cash = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    cash.plaid_account_id = "plaid-checking"
    cash.balance = Decimal("1000.00")
    db.commit()
    reconcile.checkpoint(db)

    cash.balance = Decimal("960.00")  # $40 gone, ledger says nothing
    db.commit()
    reconcile.checkpoint(db)

    rows = reconcile.drifts(db)
    assert len(rows) == 1
    assert rows[0]["unexplained"] == Decimal("-40.00")
    assert rows[0]["tracked_change"] == Decimal("-40.00")
    assert rows[0]["ledger_change"] == Decimal("0.00")
    assert "unexplained" in reconcile.drift_summary(db)


def test_buying_a_position_is_not_unexplained(db: Session) -> None:
    """Cash becoming holdings at the same cost is not money moving; valuing
    positions at cost rather than market is what keeps this quiet."""
    brokerage = db.scalar(select(Account).where(Account.type == "stocks"))
    brokerage.plaid_account_id = "plaid-brokerage"
    brokerage.balance = Decimal("1000.00")
    db.commit()
    reconcile.checkpoint(db)

    brokerage.balance = Decimal("500.00")
    db.add(
        Holding(
            ticker="STLA",
            name="Stellantis",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("5.00"),
            account_id=brokerage.id,
            source="plaid",
        )
    )
    db.commit()
    reconcile.checkpoint(db)

    assert reconcile.drifts(db) == []


def test_unconnected_accounts_are_outside_the_check(db: Session) -> None:
    """Nothing observes them independently, so they cannot corroborate
    anything — changing one must not look like unexplained movement."""
    bonds = db.scalar(select(Account).where(Account.type == "bonds"))
    bonds.balance = Decimal("100.00")
    db.commit()
    reconcile.checkpoint(db)

    bonds.balance = Decimal("999.00")
    db.commit()
    reconcile.checkpoint(db)

    assert reconcile.drifts(db) == []


def test_a_brokerage_reconciles_whole_not_by_cash_alone(
    monkeypatch, db: Session, plaid_item: PlaidItem
) -> None:
    """The bank reports the account's total, so comparing it against the
    uninvested cash alone would report drift on a perfectly correct account."""
    brokerage = db.scalar(select(Account).where(Account.type == "stocks"))
    brokerage.plaid_account_id = "plaid-brokerage"
    db.add(
        Holding(
            ticker="STLA",
            name="Stellantis",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("5.00"),
            account_id=brokerage.id,
            source="plaid",
        )
    )
    db.commit()

    _patch_balances(
        monkeypatch,
        [{"account_id": "plaid-brokerage", "balances": {"current": 698.55, "available": 198.55}}],
    )
    reconcile.refresh_balances(db)

    db.refresh(brokerage)
    assert brokerage.balance == Decimal("198.55")  # cash taken from the bank
    assert reconcile.drifts(db) == []  # 198.55 cash + 500.00 positions == 698.55


def test_card_balance_comes_from_the_bank(
    monkeypatch, db: Session, plaid_item: PlaidItem
) -> None:
    """Nothing in the ledger accumulates what is owed, so there is no local
    figure to preserve — the bank's is taken directly."""
    card = Account(name="Card", type="credit", balance=Decimal("0"), currency="usd",
                   plaid_account_id="plaid-card")
    db.add(card)
    db.commit()

    _patch_balances(monkeypatch, [{"account_id": "plaid-card", "balances": {"current": 123.63}}])
    reconcile.refresh_balances(db)

    db.refresh(card)
    assert card.balance == Decimal("123.63")
    assert reconcile.drifts(db) == []


def test_unmapped_accounts_are_left_alone(
    monkeypatch, db: Session, plaid_item: PlaidItem
) -> None:
    """An account Plaid cannot see — a foreign bank, say — must never be
    touched by a refresh."""
    bonds = db.scalar(select(Account).where(Account.type == "bonds"))
    bonds.balance = Decimal("343.75")
    db.commit()

    _patch_balances(monkeypatch, [{"account_id": "someone-else", "balances": {"current": 1.0}}])
    reconcile.refresh_balances(db)

    db.refresh(bonds)
    assert bonds.balance == Decimal("343.75")
    assert bonds.plaid_balance is None


# ---------------------------------------------------------------------------
# Per-account breakdown
# ---------------------------------------------------------------------------


def test_breakdown_sums_to_net_worth(db: Session) -> None:
    """The page and the dashboard read the same numbers from different shapes;
    if these ever disagree one of them is lying."""
    cash = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    cash.balance = Decimal("2729.61")
    brokerage = db.scalar(select(Account).where(Account.type == "stocks"))
    brokerage.balance = Decimal("198.55")
    db.add(Account(name="Card", type="credit", balance=Decimal("123.63"), currency="usd"))
    db.add(
        Holding(
            ticker="STLA",
            name="Stellantis",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("5.00"),
            account_id=brokerage.id,
            source="plaid",
        )
    )
    db.commit()

    rows = networth.accounts_breakdown(db)
    total, _ = networth.compute_totals(db)

    assert sum(r["value"] for r in rows) == total


def test_breakdown_signs_and_holdings(db: Session) -> None:
    brokerage = db.scalar(select(Account).where(Account.type == "stocks"))
    brokerage.balance = Decimal("198.55")
    db.add(Account(name="Card", type="credit", balance=Decimal("123.63"), currency="usd"))
    db.add(
        Holding(
            ticker="STLA",
            name="Stellantis",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("5.00"),
            account_id=brokerage.id,
            source="plaid",
        )
    )
    db.commit()

    rows = {r["name"]: r for r in networth.accounts_breakdown(db)}

    # A card holds what is owed, so it counts against net worth.
    assert rows["Card"]["value"] == Decimal("-123.63")
    # A brokerage is its uninvested cash plus its positions, not one or other.
    assert rows["Brokerage"]["value"] == Decimal("698.55")
    assert [h["ticker"] for h in rows["Brokerage"]["holdings"]] == ["STLA"]


def test_breakdown_marks_unconnected_accounts(db: Session) -> None:
    cash = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    cash.plaid_account_id = "plaid-checking"
    db.commit()

    rows = {r["name"]: r for r in networth.accounts_breakdown(db)}

    assert rows[cash.name]["is_connected"] is True
    assert rows["Bonds"]["is_connected"] is False
