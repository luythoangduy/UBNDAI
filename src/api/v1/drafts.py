"""API sinh bản nháp kết quả thủ tục theo template pháp lý của từng thủ tục."""

from fastapi import APIRouter, HTTPException, Response

from src.models import (
    DraftGenerateRequest,
    DraftHtmlExportRequest,
    DraftRevision,
    DraftReviseRequest,
    DraftTemplateImportRequest,
    DraftTemplateInfo,
    GeneratedDraft,
)
from src.services import drafts as draft_service
from src.services.drafts.template_importer import TemplateImportError, import_template

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.get("/templates/{procedure_id}", response_model=list[DraftTemplateInfo])
async def get_draft_templates(procedure_id: str) -> list[DraftTemplateInfo]:
    templates = draft_service.list_templates(procedure_id)
    if not templates:
        raise HTTPException(status_code=404, detail="Chưa tìm thấy template cho thủ tục")
    return [
        DraftTemplateInfo.model_validate(template, from_attributes=True)
        for template in templates
    ]


@router.post("/templates/import", response_model=DraftTemplateInfo)
async def import_searched_template(
    payload: DraftTemplateImportRequest,
) -> DraftTemplateInfo:
    try:
        template = await import_template(payload)
    except TemplateImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DraftTemplateInfo.model_validate(template, from_attributes=True)


@router.post("/generate", response_model=GeneratedDraft)
async def generate_draft(payload: DraftGenerateRequest) -> GeneratedDraft:
    try:
        return draft_service.generate(payload)
    except draft_service.DraftTemplateNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except draft_service.DraftDataError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "fields": exc.fields},
        ) from exc


@router.post("/revise", response_model=DraftRevision)
async def revise_draft(payload: DraftReviseRequest) -> DraftRevision:
    try:
        return await draft_service.revise(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/export.docx",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}
            },
            "description": "DOCX xuất từ HTML editor (WYSIWYG)",
        }
    },
)
async def export_draft_docx(payload: DraftHtmlExportRequest) -> Response:
    """Xuất DOCX đúng nội dung editor — cách làm của C2 (drafting.export_docx)."""
    content = draft_service.export_html_docx(payload)
    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{payload.filename}"',
            "X-Draft-Legal-Status": "review-only",
        },
    )


@router.post(
    "/generate.docx",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}
            },
            "description": "Bản nháp DOCX để rà soát thể thức",
        }
    },
)
async def generate_draft_docx(payload: DraftGenerateRequest) -> Response:
    try:
        document = draft_service.generate_docx(payload)
    except draft_service.DraftTemplateNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except draft_service.DraftDataError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "fields": exc.fields},
        ) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=document.content,
        media_type=document.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.filename}"',
            "X-Draft-Legal-Status": "review-only",
        },
    )
