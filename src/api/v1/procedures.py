"""Public, capability-driven procedure catalog API."""

from fastapi import APIRouter, HTTPException

from src.models import (
    Procedure,
    ProcedureCapabilities,
    ProcedureFormSchema,
    ProcedureSummary,
)
from src.services import catalog
from src.services.procedure_capabilities import capabilities_for, form_schema_for

router = APIRouter(prefix="/procedures", tags=["procedures"])


def _published() -> list[Procedure]:
    return [
        procedure
        for procedure in catalog.load_catalog().values()
        if procedure.status in {"approved", "published"}
    ]


@router.get("", response_model=list[ProcedureSummary])
async def list_procedures() -> list[ProcedureSummary]:
    return [ProcedureSummary.model_validate(item.model_dump()) for item in _published()]


@router.get("/{procedure_id}", response_model=Procedure)
async def get_procedure(procedure_id: str) -> Procedure:
    procedure = catalog.get_procedure(procedure_id)
    if procedure is None or procedure.status not in {"approved", "published"}:
        raise HTTPException(status_code=404, detail="Không tìm thấy thủ tục đã công bố")
    return procedure


@router.get("/{procedure_id}/capabilities", response_model=ProcedureCapabilities)
async def get_capabilities(procedure_id: str) -> ProcedureCapabilities:
    return capabilities_for(procedure_id)


@router.get("/{procedure_id}/form-schema", response_model=ProcedureFormSchema)
async def get_form_schema(procedure_id: str) -> ProcedureFormSchema:
    schema = form_schema_for(procedure_id)
    if schema is None:
        raise HTTPException(
            status_code=409,
            detail="Chưa tìm thấy cấu trúc biểu mẫu cho thủ tục",
        )
    return schema
