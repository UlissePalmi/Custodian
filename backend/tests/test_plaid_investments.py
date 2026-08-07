"""Plaid investments sync: brokerage positions are replaced, manual ones aren't.

Holdings are state rather than a stream of events — Plaid says what the
account contains now — so the sync replaces what it owns instead of appending.
The behaviour worth pinning down is the ownership split: a position Plaid can
see is its to overwrite and delete, and a position it cannot see (a Treasury
bought direct) must survive untouched, or the two would double the holding.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Holding, PlaidItem
from app.services import plaid_investments
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
    db.refresh(item)
    return item


@pytest.fixture
def manual_bond(db: Session) -> Holding:
    """A Treasury held where Plaid cannot see it — the reason `source` exists."""
    bonds = db.scalar(select(Account).where(Account.type == "bonds"))
    holding = Holding(
        ticker="US912810SN90",
        name="US Treasury",
        quantity=Decimal("1210"),
        cost_basis_per_share=Decimal("50.19"),
        account_id=bonds.id,
        source="manual",
    )
    db.add(holding)
    db.commit()
    return holding


class FakeSecurity:
    def __init__(self, security_id, ticker, name, sec_type):
        self.security_id = security_id
        self.ticker_symbol = ticker
        self.name = name
        self.type = sec_type


class FakeHolding:
    def __init__(self, security_id, quantity, cost_basis=None):
        self.security_id = security_id
        self.quantity = quantity
        self.cost_basis = cost_basis


class FakeHoldingsResponse:
    def __init__(self, holdings, securities):
        self.holdings = holdings
        self.securities = securities


class FakeInvestmentsClient:
    def __init__(self, response):
        self._response = response

    def investments_holdings_get(self, request):  # noqa: ANN001 - test double
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _patch(monkeypatch, holdings, securities):
    client = FakeInvestmentsClient(FakeHoldingsResponse(holdings, securities))
    monkeypatch.setattr(plaid_investments, "get_plaid_client", lambda: client)


def plaid_rows(db: Session) -> list[Holding]:
    return list(db.scalars(select(Holding).where(Holding.source == "plaid")))


def test_sync_creates_positions(monkeypatch, db: Session, plaid_item: PlaidItem) -> None:
    _patch(
        monkeypatch,
        [FakeHolding("sec-1", 150.0, 857.05), FakeHolding("sec-2", 10.0, 1009.40)],
        [
            FakeSecurity("sec-1", "STLA", "Stellantis NV", "equity"),
            FakeSecurity("sec-2", "DUOL", "Duolingo Inc", "equity"),
        ],
    )

    assert plaid_investments.sync_holdings(db, plaid_item) == 2

    rows = {h.ticker: h for h in plaid_rows(db)}
    assert set(rows) == {"STLA", "DUOL"}
    # Plaid gives basis for the whole position; Custodian stores it per share.
    assert rows["DUOL"].cost_basis_per_share == Decimal("100.9400")
    assert rows["STLA"].quantity == Decimal("150")


def test_sync_skips_cash_positions(monkeypatch, db: Session, plaid_item: PlaidItem) -> None:
    """A sweep fund and an unsettled negative balance are money in the account,
    not securities, and have no ticker the price feed could quote."""
    _patch(
        monkeypatch,
        [
            FakeHolding("sec-1", 150.0, 857.05),
            FakeHolding("sec-cash", 766.8),
            FakeHolding("sec-usd", -568.25),
        ],
        [
            FakeSecurity("sec-1", "STLA", "Stellantis NV", "equity"),
            FakeSecurity("sec-cash", "QACDS", "Sweep Fund", "cash"),
            FakeSecurity("sec-usd", None, "US Dollar", "cash"),
        ],
    )

    assert plaid_investments.sync_holdings(db, plaid_item) == 1
    assert [h.ticker for h in plaid_rows(db)] == ["STLA"]


def test_manual_holdings_are_never_touched(
    monkeypatch, db: Session, plaid_item: PlaidItem, manual_bond: Holding
) -> None:
    _patch(
        monkeypatch,
        [FakeHolding("sec-1", 150.0, 857.05)],
        [FakeSecurity("sec-1", "STLA", "Stellantis NV", "equity")],
    )

    plaid_investments.sync_holdings(db, plaid_item)

    manual = db.scalars(select(Holding).where(Holding.source == "manual")).all()
    assert [h.ticker for h in manual] == ["US912810SN90"]
    assert manual[0].quantity == Decimal("1210")


def test_resync_updates_quantity_rather_than_duplicating(
    monkeypatch, db: Session, plaid_item: PlaidItem
) -> None:
    _patch(
        monkeypatch,
        [FakeHolding("sec-1", 150.0, 857.05)],
        [FakeSecurity("sec-1", "STLA", "Stellantis NV", "equity")],
    )
    plaid_investments.sync_holdings(db, plaid_item)

    _patch(
        monkeypatch,
        [FakeHolding("sec-1", 200.0, 1140.0)],
        [FakeSecurity("sec-1", "STLA", "Stellantis NV", "equity")],
    )
    plaid_investments.sync_holdings(db, plaid_item)

    rows = plaid_rows(db)
    assert len(rows) == 1
    assert rows[0].quantity == Decimal("200")


def test_sold_position_disappears(monkeypatch, db: Session, plaid_item: PlaidItem) -> None:
    _patch(
        monkeypatch,
        [FakeHolding("sec-1", 150.0), FakeHolding("sec-2", 10.0)],
        [
            FakeSecurity("sec-1", "STLA", "Stellantis NV", "equity"),
            FakeSecurity("sec-2", "DUOL", "Duolingo Inc", "equity"),
        ],
    )
    plaid_investments.sync_holdings(db, plaid_item)

    # STLA sold: Plaid stops reporting it.
    _patch(
        monkeypatch,
        [FakeHolding("sec-2", 10.0)],
        [FakeSecurity("sec-2", "DUOL", "Duolingo Inc", "equity")],
    )
    plaid_investments.sync_holdings(db, plaid_item)

    assert [h.ticker for h in plaid_rows(db)] == ["DUOL"]


def test_missing_investments_consent_is_not_an_error(
    monkeypatch, db: Session, plaid_item: PlaidItem
) -> None:
    """An item linked without investments consent is a healthy connection with
    nothing to report — flagging it would leave a permanent error badge."""

    class Denied(Exception):
        body = '{"error_code": "ADDITIONAL_CONSENT_REQUIRED"}'

    monkeypatch.setattr(
        plaid_investments, "get_plaid_client", lambda: FakeInvestmentsClient(Denied())
    )

    assert plaid_investments.sync_all_holdings(db) == 0

    db.refresh(plaid_item)
    assert plaid_item.status == "active"
    assert plaid_item.last_error is None


def test_a_real_failure_is_recorded(monkeypatch, db: Session, plaid_item: PlaidItem) -> None:
    class Boom(Exception):
        body = '{"error_code": "INTERNAL_SERVER_ERROR"}'

    monkeypatch.setattr(
        plaid_investments, "get_plaid_client", lambda: FakeInvestmentsClient(Boom())
    )

    plaid_investments.sync_all_holdings(db)

    db.refresh(plaid_item)
    assert plaid_item.status == "error"
    assert plaid_item.last_error is not None


def test_a_refresh_is_requested_before_reading(monkeypatch, db: Session, plaid_item: PlaidItem) -> None:
    """Holdings are not pulled on demand the way transactions are, so without
    asking Plaid to re-fetch, a trade made today is silently absent."""
    calls: list[str] = []

    class Recording(FakeInvestmentsClient):
        def investments_refresh(self, request):  # noqa: ANN001 - test double
            calls.append("refresh")

        def investments_holdings_get(self, request):  # noqa: ANN001 - test double
            calls.append("get")
            return super().investments_holdings_get(request)

    client = Recording(
        FakeHoldingsResponse(
            [FakeHolding("sec-1", 200.0, 1136.30)],
            [FakeSecurity("sec-1", "STLA", "Stellantis NV", "equity")],
        )
    )
    monkeypatch.setattr(plaid_investments, "get_plaid_client", lambda: client)

    plaid_investments.sync_holdings(db, plaid_item)

    assert calls == ["refresh", "get"]
    assert plaid_rows(db)[0].quantity == Decimal("200")


def test_an_unsupported_refresh_does_not_fail_the_sync(
    monkeypatch, db: Session, plaid_item: PlaidItem
) -> None:
    """Not every institution supports it; positions must still sync."""

    class Refusing(FakeInvestmentsClient):
        def investments_refresh(self, request):  # noqa: ANN001 - test double
            raise RuntimeError("not supported here")

    client = Refusing(
        FakeHoldingsResponse(
            [FakeHolding("sec-1", 150.0)],
            [FakeSecurity("sec-1", "STLA", "Stellantis NV", "equity")],
        )
    )
    monkeypatch.setattr(plaid_investments, "get_plaid_client", lambda: client)

    assert plaid_investments.sync_holdings(db, plaid_item) == 1
