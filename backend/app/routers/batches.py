from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import batches

# Path kept as /api/import/batches: it is the documented undo command (see
# DEPLOY.md) and predates syncing being the only thing that creates batches.
router = APIRouter(prefix="/api/import", tags=["batches"])


@router.delete("/batches/{batch_id}", status_code=204, response_class=Response)
def delete_batch(batch_id: str, db: Session = Depends(get_db)) -> Response:
    batches.delete_batch(db, batch_id)
    return Response(status_code=204)
