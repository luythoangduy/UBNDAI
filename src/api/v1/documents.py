"""Upload, OCR and user correction endpoints for the legacy guidance flow."""

from fastapi import APIRouter, HTTPException, UploadFile

from src.models import ExtractedDocument
from src.services.ocr import pipeline
from src.services.ocr.engine import OcrEngineError

router = APIRouter(prefix="/documents", tags=["documents"])
_extracted_documents: dict[str, ExtractedDocument] = {}


@router.post("/upload", response_model=ExtractedDocument)
async def upload_and_extract(case_id: str, file: UploadFile) -> ExtractedDocument:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File rỗng")
    try:
        document = await pipeline.process(case_id, file.filename or "", content)
    except (OcrEngineError, ValueError) as exc:
        code = 502 if isinstance(exc, OcrEngineError) else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    _extracted_documents[document.id] = document
    return document


@router.patch("/{document_id}/fields", response_model=ExtractedDocument)
async def correct_fields(document_id: str, fields: dict[str, str]) -> ExtractedDocument:
    document = _extracted_documents.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Extracted document not found")
    unknown = set(fields) - {field.key for field in document.fields}
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown fields: {', '.join(sorted(unknown))}")
    updated_fields = [
        field.model_copy(update={"value": fields[field.key], "edited_by_user": True})
        if field.key in fields else field
        for field in document.fields
    ]
    updated = document.model_copy(update={"fields": updated_fields})
    _extracted_documents[document_id] = updated
    return updated
