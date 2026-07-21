from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ApiError
from app.schemas.ledger import TransactionInput, TransactionOut
from app.services import ledger

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _parse_id(transaction_id: str) -> int:
    # Ids are opaque strings in the contract; anything non-numeric simply does
    # not exist here.
    try:
        return int(transaction_id)
    except ValueError:
        raise ApiError("Transaction not found.", 404) from None


@router.put("/{transaction_id}", response_model=TransactionOut)
def update_transaction(
    transaction_id: str, payload: TransactionInput, db: Session = Depends(get_db)
):
    transaction = ledger.update_transaction(db, _parse_id(transaction_id), payload)
    return ledger.hydrate(transaction)


@router.delete("/{transaction_id}", status_code=204, response_class=Response)
def delete_transaction(transaction_id: str, db: Session = Depends(get_db)) -> Response:
    ledger.delete_transaction(db, _parse_id(transaction_id))
    return Response(status_code=204)
