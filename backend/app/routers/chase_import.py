from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.chase import ImportPreview, ImportResult
from app.services import importer

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/chase", response_model=ImportPreview)
async def upload_chase_file(
    file: UploadFile = File(...),
    hint_month_key: str | None = Form(default=None, alias="hintMonthKey"),
    db: Session = Depends(get_db),
):
    """Parses an export and proposes categories. Writes nothing."""
    content = await file.read()
    return importer.build_preview(db, content, file.filename or "upload.csv", hint_month_key)


@router.post("/chase/confirm", response_model=ImportResult)
def confirm_import(preview: ImportPreview, db: Session = Depends(get_db)):
    return importer.confirm_import(db, preview)


@router.delete("/batches/{batch_id}", status_code=204, response_class=Response)
def delete_batch(batch_id: str, db: Session = Depends(get_db)) -> Response:
    importer.delete_batch(db, batch_id)
    return Response(status_code=204)
