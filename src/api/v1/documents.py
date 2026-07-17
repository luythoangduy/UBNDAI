"""Upload giấy tờ + OCR. Owner: Dev B."""

from fastapi import APIRouter, UploadFile

from src.models import ExtractedDocument

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=ExtractedDocument)
async def upload_and_extract(case_id: str, file: UploadFile) -> ExtractedDocument:
    """Lưu file → phân loại doc_type → trích trường → cập nhật checklist item tương ứng."""
    # TODO(B): services.ocr.pipeline.process(case_id, file)
    raise NotImplementedError


@router.patch("/{document_id}/fields", response_model=ExtractedDocument)
async def correct_fields(document_id: str, fields: dict[str, str]) -> ExtractedDocument:
    """Người dân sửa tay giá trị OCR — set edited_by_user=True, re-trigger autofill."""
    raise NotImplementedError  # TODO(B)
