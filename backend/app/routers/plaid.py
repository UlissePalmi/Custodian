from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.imports import ImportResult
from app.schemas.plaid import (
    BalanceDriftOut,
    ExchangeTokenRequest,
    LinkTokenResponse,
    PlaidConnection,
)
from app.services import plaid_investments, plaid_link, plaid_sync, reconcile

router = APIRouter(prefix="/api/plaid", tags=["plaid"])


@router.post("/link-token", response_model=LinkTokenResponse)
def create_link_token(db: Session = Depends(get_db)):
    return {"link_token": plaid_link.create_link_token(db)}


@router.post("/exchange-token", response_model=PlaidConnection)
def exchange_token(body: ExchangeTokenRequest, db: Session = Depends(get_db)):
    return plaid_link.exchange_public_token(db, body.public_token, body.institution_name)


@router.post("/sync-now", response_model=list[ImportResult])
def sync_now(db: Session = Depends(get_db)):
    results = plaid_sync.sync_all_items(db)
    # Positions are refreshed too, but have no batch to report: Plaid states
    # what the account holds now, so there is nothing incremental to return.
    plaid_investments.sync_all_holdings(db)
    reconcile.refresh_balances(db)
    reconcile.checkpoint(db)
    return results


@router.get("/reconciliation", response_model=list[BalanceDriftOut])
def reconciliation(db: Session = Depends(get_db)):
    """Mapped accounts whose ledger balance disagrees with the bank's."""
    return reconcile.drifts(db)


@router.get("/status", response_model=list[PlaidConnection])
def status(db: Session = Depends(get_db)):
    return plaid_link.list_connections(db)


@router.delete("/items/{item_id}", status_code=204, response_class=Response)
def disconnect(item_id: str, db: Session = Depends(get_db)) -> Response:
    plaid_link.disconnect_item(db, item_id)
    return Response(status_code=204)
