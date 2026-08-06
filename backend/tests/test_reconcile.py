"""Account mapping: what the ledger thinks, what the bank says, and the gap.

Both balances are kept deliberately. The ledger's is the running total of
everything Custodian recorded; the bank's is the truth. Neither alone reveals
a missed or double-counted transaction — the difference between them does.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Holding, PlaidItem
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


def test_bank_balance_is_recorded_without_overwriting_the_ledger(
    monkeypatch, db: Session, plaid_item: PlaidItem
) -> None:
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
    assert cash.plaid_balance == Decimal("2729.61")
    assert cash.balance == Decimal("4023.94")  # untouched on purpose


def test_drift_is_reported(monkeypatch, db: Session, plaid_item: PlaidItem) -> None:
    cash = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    cash.balance = Decimal("4023.94")
    cash.plaid_account_id = "plaid-checking"
    db.commit()
    _patch_balances(
        monkeypatch, [{"account_id": "plaid-checking", "balances": {"current": 2729.61}}]
    )
    reconcile.refresh_balances(db)

    rows = reconcile.drifts(db)

    assert len(rows) == 1
    assert rows[0]["difference"] == Decimal("1294.33")

    summary = reconcile.drift_summary(db)
    assert cash.name in summary
    assert "4023.94" in summary and "2729.61" in summary


def test_agreeing_balances_do_not_drift(monkeypatch, db: Session, plaid_item: PlaidItem) -> None:
    cash = db.scalar(select(Account).where(Account.type == "cash").order_by(Account.id))
    cash.balance = Decimal("2729.61")
    cash.plaid_account_id = "plaid-checking"
    db.commit()
    _patch_balances(
        monkeypatch, [{"account_id": "plaid-checking", "balances": {"current": 2729.61}}]
    )
    reconcile.refresh_balances(db)

    assert reconcile.drifts(db) == []
    assert reconcile.drift_summary(db) is None


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
