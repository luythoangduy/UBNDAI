"""Upload giấy tờ + OCR. Owner: Dev B."""

from fastapi import APIRouter, HTTPException, UploadFile

from src.models import ExtractedDocument
from src.services.ocr import pipeline
from src.services.ocr.engine import OcrEngineError

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=ExtractedDocument)
async def upload_and_extract(case_id: str, file: UploadFile) -> ExtractedDocument:
    """Tiền xử lý ảnh → OCR → trích trường. TODO(B): persist + cập nhật checklist."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File rỗng")
    try:
        return await pipeline.process(case_id, file.filename or "", content)
    except OcrEngineError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.patch("/{document_id}/fields", response_model=ExtractedDocument)
async def correct_fields(document_id: str, fields: dict[str, str]) -> ExtractedDocument:
    """Người dân sửa tay giá trị OCR — set edited_by_user=True, re-trigger autofill."""
    raise NotImplementedError  # TODO(B)
