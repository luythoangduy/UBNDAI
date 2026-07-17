"""Kiểm tra hồ sơ trước nộp (pre-submission checking). Owner: Dev B.

Stateless trong MVP: client gửi Case + ExtractedDocument lên, nhận ValidationReport.
TODO(B) khi DB của Dev C sẵn sàng: nhận case_id, tự load case/documents và persist report.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.models import Case, ExtractedDocument, ValidationIssue, ValidationReport
from src.services.validation import ai_checker, rule_engine
from src.services.validation.rule_engine import RuleFileError

router = APIRouter(prefix="/validation", tags=["validation"])


class ValidationCheckRequest(BaseModel):
    case: Case
    documents: list[ExtractedDocument] = Field(default_factory=list)
    include_ai: bool = Field(
        default=True, description="Chạy thêm AI cross-check (chỉ sinh warning/info)"
    )


@router.post("/check", response_model=ValidationReport)
async def check_case(payload: ValidationCheckRequest) -> ValidationReport:
    """Rule engine (error/warning) + AI checker (warning/info) → ValidationReport."""
    try:
        report = rule_engine.run(payload.case, payload.documents)
    except RuleFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.include_ai:
        ai_issues: list[ValidationIssue] = await ai_checker.run(
            payload.case, payload.documents
        )
        if ai_issues:
            # readiness_score giữ deterministic: AI chỉ thêm warning/info,
            # tính lại điểm với tổng warning mới.
            issues = report.issues + ai_issues
            report = ValidationReport(
                case_id=report.case_id,
                issues=issues,
                readiness_score=rule_engine.compute_readiness_score(
                    n_error=sum(1 for i in issues if i.severity == "error"),
                    n_warning=sum(1 for i in issues if i.severity == "warning"),
                    n_checklist_missing=sum(
                        1 for item in payload.case.checklist if item.status == "missing"
                    ),
                ),
                checked_at=report.checked_at,
            )
    return report
