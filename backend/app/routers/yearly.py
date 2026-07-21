from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.ledger import YearlyTableOut
from app.services import yearly

router = APIRouter(prefix="/api/yearly-table", tags=["yearly"])


@router.get("", response_model=YearlyTableOut)
def get_yearly_table(year: int, db: Session = Depends(get_db)):
    return yearly.read_yearly_table(db, year)
