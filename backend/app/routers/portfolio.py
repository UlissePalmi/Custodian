"""Net worth, holdings and accounts.

The GET endpoints back the dashboard. The write endpoints have no UI yet — they
exist so positions and balances can be recorded from the command line.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ApiError
from app.models import Account, Holding
from app.money import round_cents
from app.schemas.portfolio import (
    AccountInput,
    AccountOut,
    HoldingInput,
    HoldingOut,
    NetWorthSummaryOut,
)
from app.services import networth

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.get("/networth", response_model=NetWorthSummaryOut)
def get_net_worth(db: Session = Depends(get_db)):
    return networth.read_net_worth(db)


@router.get("/holdings", response_model=list[HoldingOut])
def get_holdings(db: Session = Depends(get_db)):
    return networth.read_holdings(db)


# --------------------------------------------------------------------------
# Holdings admin
# --------------------------------------------------------------------------


def _stocks_account(db: Session) -> Account:
    account = db.scalar(select(Account).where(Account.type == "stocks").order_by(Account.id))
    if account is None:
        account = Account(name="Brokerage", type="stocks", balance=0)
        db.add(account)
        db.flush()
    return account


@router.post("/holdings", response_model=HoldingOut, status_code=201)
def create_holding(payload: HoldingInput, db: Session = Depends(get_db)):
    if payload.quantity <= 0:
        raise ApiError("Quantity must be greater than zero.", 422)

    account_id = payload.account_id or _stocks_account(db).id
    holding = Holding(
        ticker=payload.ticker.strip().upper(),
        name=(payload.name or payload.ticker).strip(),
        quantity=Decimal(str(payload.quantity)),
        cost_basis_per_share=round_cents(Decimal(str(payload.cost_basis_per_share))),
        purchase_date=payload.purchase_date,
        account_id=account_id,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return next(h for h in networth.read_holdings(db) if h["id"] == holding.id)


@router.put("/holdings/{holding_id}", response_model=HoldingOut)
def update_holding(holding_id: int, payload: HoldingInput, db: Session = Depends(get_db)):
    holding = db.get(Holding, holding_id)
    if holding is None:
        raise ApiError("Holding not found.", 404)

    holding.ticker = payload.ticker.strip().upper()
    if payload.name:
        holding.name = payload.name.strip()
    holding.quantity = Decimal(str(payload.quantity))
    holding.cost_basis_per_share = round_cents(Decimal(str(payload.cost_basis_per_share)))
    if payload.purchase_date is not None:
        holding.purchase_date = payload.purchase_date
    db.commit()
    return next(h for h in networth.read_holdings(db) if h["id"] == holding_id)


@router.delete("/holdings/{holding_id}", status_code=204, response_class=Response)
def delete_holding(holding_id: int, db: Session = Depends(get_db)) -> Response:
    holding = db.get(Holding, holding_id)
    if holding is None:
        raise ApiError("Holding not found.", 404)
    db.delete(holding)
    db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------
# Accounts admin
# --------------------------------------------------------------------------


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return list(db.scalars(select(Account).order_by(Account.id)))


@router.put("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: int, payload: AccountInput, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if account is None:
        raise ApiError("Account not found.", 404)
    if payload.name is not None:
        account.name = payload.name.strip()
    if payload.type is not None:
        account.type = payload.type.strip()
    if payload.balance is not None:
        account.balance = round_cents(Decimal(str(payload.balance)))
    db.commit()
    db.refresh(account)
    return account
