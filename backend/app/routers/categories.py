from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.ledger import CategoryCreate, CategoryOut, CategoryUpdate
from app.services import ledger

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(include_archived: bool = False, db: Session = Depends(get_db)):
    return ledger.list_categories(db, include_archived=include_archived)


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    return ledger.create_category(db, payload.name, payload.kind, payload.sort_order)


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(category_id: str, payload: CategoryUpdate, db: Session = Depends(get_db)):
    return ledger.update_category(
        db,
        category_id,
        name=payload.name,
        sort_order=payload.sort_order,
        archived=payload.archived,
    )


@router.post("/{category_id}/archive", response_model=CategoryOut)
def archive_category(category_id: str, db: Session = Depends(get_db)):
    return ledger.update_category(db, category_id, archived=True)
