"""Citizen intake, private upload and explicit submission routes."""

import asyncio
import base64
import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from src.config import settings
from src.models import (
    CitizenCaseCreate,
    CitizenCaseUpdate,
    CitizenSubmitRequest,
    TokenClaims,
    UploadCompleteRequest,
    UploadIntentRequest,
)
from src.services.auth import require_role
from src.services.procedure_capabilities import capabilities_for, ocr_field_keys_for
from src.services.ocr.pdf import rasterize_pdf
from src.services.ocr.pipeline import process as process_ocr
from src.services.ocr.preprocessing import preprocess_document_image
from src.services.officer_store import store
from src.services.storage import StorageError, storage, validate_magic

router = APIRouter(prefix="/citizen", tags=["citizen"])


@router.get("/me")
async def me(claims: TokenClaims = Depends(require_role("citizen"))):
    return {"success": True, "data": {"user_id": claims.user_id, "roles": sorted(claims.roles)}}


@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_case(payload: CitizenCaseCreate, claims: TokenClaims = Depends(require_role("citizen"))):
    if not capabilities_for(payload.procedure_id).dynamic_form:
        raise HTTPException(
            status_code=409,
            detail="Thủ tục chưa có template để soạn hồ sơ",
        )
    case = store.create_citizen_case(claims.user_id, payload.procedure_id, payload.locality_code)
    return {"success": True, "data": case.model_dump(mode="json")}


@router.get("/cases")
async def list_cases(claims: TokenClaims = Depends(require_role("citizen"))):
    cases = store.list_citizen_cases(claims.user_id)
    return {"success": True, "data": [case.model_dump(mode="json") for case in cases]}


@router.get("/cases/{case_id}")
async def get_case(case_id: str, claims: TokenClaims = Depends(require_role("citizen"))):
    case = store.get_citizen_case(case_id, claims.user_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    documents = [document.model_dump(mode="json") for document in store.documents.values() if document.case_id == case_id]
    return {"success": True, "data": {"case": case.model_dump(mode="json"), "documents": documents}}


@router.patch("/cases/{case_id}")
async def update_case(case_id: str, payload: CitizenCaseUpdate, claims: TokenClaims = Depends(require_role("citizen"))):
    try:
        case = store.update_citizen_case(case_id, claims.user_id, payload.expected_version, payload.answers, payload.form_data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except ValueError as exc:
        code = 409 if str(exc) == "version_conflict" else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return {"success": True, "data": case.model_dump(mode="json")}


@router.get("/cases/{case_id}/timeline")
async def timeline(case_id: str, claims: TokenClaims = Depends(require_role("citizen"))):
    case = store.get_citizen_case(case_id, claims.user_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    events = [event.model_dump(mode="json") for event in store.audit if event.case_id == case_id]
    return {"success": True, "data": events}


@router.post("/cases/{case_id}/documents/upload-intents", status_code=status.HTTP_201_CREATED)
async def create_upload_intent(case_id: str, payload: UploadIntentRequest, claims: TokenClaims = Depends(require_role("citizen"))):
    try:
        document = store.create_document(case_id, claims.user_id, payload.filename, payload.content_type, payload.size_bytes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "data": {"document_id": document.id, "upload_url": f"/api/v1/citizen/uploads/{document.id}", "expires_in": 900}}


@router.put("/uploads/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def upload(document_id: str, request: Request, claims: TokenClaims = Depends(require_role("citizen"))):
    document = store.get_citizen_document(document_id, claims.user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    content = await request.body()
    if len(content) != document.size_bytes or len(content) > settings.upload_max_bytes:
        raise HTTPException(status_code=422, detail="Uploaded size does not match intent")
    storage.put(document.object_key or "", content)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/{document_id}/preprocess")
async def preprocess_document(document_id: str, claims: TokenClaims = Depends(require_role("citizen"))):
    """Chạy riêng tiền xử lý ảnh và trả snapshot từng bước cho FE minh hoạ pipeline."""
    document = store.get_citizen_document(document_id, claims.user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        content = storage.get(document.object_key or "")
        if document.content_type == "application/pdf":
            pages = await asyncio.to_thread(rasterize_pdf, content)
            content = pages[0]
    except (StorageError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await asyncio.to_thread(preprocess_document_image, content, capture_steps=True)
    steps = [
        {
            "name": snapshot.name,
            "image": f"data:{snapshot.mime_type};base64,{base64.b64encode(snapshot.content).decode('ascii')}",
        }
        for snapshot in result.step_snapshots
    ]
    return {"success": True, "data": {"applied_steps": result.applied_steps, "steps": steps}}


@router.post("/documents/{document_id}/complete")
async def complete_upload(document_id: str, payload: UploadCompleteRequest, claims: TokenClaims = Depends(require_role("citizen"))):
    document = store.get_citizen_document(document_id, claims.user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        content = storage.get(document.object_key or "")
        if hashlib.sha256(content).hexdigest() != payload.sha256:
            raise StorageError("Checksum mismatch")
        validate_magic(document.content_type or "", content)
        case = store.get_citizen_case(document.case_id, claims.user_id)
        field_keys = ocr_field_keys_for(case.procedure_id) if case else None
        ocr = await process_ocr(
            document.case_id,
            document.original_filename or "document.bin",
            content,
            field_keys=field_keys,
        )
    except (StorageError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    completed = store.complete_document(
        document_id,
        claims.user_id,
        payload.sha256,
        ocr.doc_type,
        ocr.needs_human_review,
        [field.model_dump() for field in ocr.fields],
        ocr.ocr_engine,
    )
    # Alias sang shape ExtractedFieldRecord mà FE hiển thị (field_key/raw_value/bounding_box)
    fields_resp = [
        {
            **field.model_dump(),
            "id": f"{completed.id}_f{index}",
            "field_key": field.key,
            "raw_value": field.value,
            "bounding_box": field.bbox,
            "review_status": (
                "needs_human_review"
                if field.confidence < settings.ocr_confidence_threshold
                else "unreviewed"
            ),
        }
        for index, field in enumerate(ocr.fields)
    ]
    return {"success": True, "data": {"document": completed.model_dump(mode="json"), "fields": fields_resp}}


@router.post("/cases/{case_id}/submit")
async def submit_case(
    case_id: str,
    payload: CitizenSubmitRequest,
    idempotency_key: str = Header(min_length=8, max_length=200, alias="Idempotency-Key"),
    claims: TokenClaims = Depends(require_role("citizen")),
):
    if not payload.consent_accepted:
        raise HTTPException(status_code=422, detail="Consent is required")
    try:
        result = store.submit_citizen_case(case_id, claims.user_id, payload.expected_version, payload.consent_version, idempotency_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except ValueError as exc:
        code = 409 if str(exc) == "version_conflict" else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return {"success": True, "data": result}
