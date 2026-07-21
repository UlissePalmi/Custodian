from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.ledger import MonthInfoOut, MonthLedgerOut, TransactionInput, TransactionOut
from app.services import ledger

router = APIRouter(prefix="/api/months", tags=["months"])


@router.get("", response_model=list[MonthInfoOut])
def list_months(db: Session = Depends(get_db)):
    return ledger.read_months(db)


@router.get("/{month_key}", response_model=MonthLedgerOut)
def get_month(month_key: str, db: Session = Depends(get_db)):
    ledger.validate_month_key(month_key)
    return ledger.read_month_ledger(db, month_key)


@router.post("/{month_key}/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(month_key: str, payload: TransactionInput, db: Session = Depends(get_db)):
    ledger.validate_month_key(month_key)
    transaction = ledger.create_transaction(db, month_key, payload)
    return ledger.hydrate(transaction)
