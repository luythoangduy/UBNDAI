"""Derive UI/workflow capabilities from approved catalog assets."""

from pathlib import Path

from src.models import Procedure, ProcedureCapabilities, ProcedureFormSchema
from src.services.drafts import registry as draft_registry

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"


def capabilities(procedure: Procedure) -> ProcedureCapabilities:
    reviewed = procedure.status in {"approved", "published"}
    fields = [field for template in procedure.form_templates for field in template.fields]
    has_form = reviewed and bool(fields)
    return ProcedureCapabilities(
        chat=True,
        checklist=reviewed and bool(procedure.requirements),
        dynamic_form=has_form,
        ocr_autofill=has_form and any(field.ocr_sources for field in fields),
        legal_validation=reviewed and (RULES_DIR / f"{procedure.id}.yaml").is_file(),
        official_draft=reviewed and bool(draft_registry.list_templates(procedure.id)),
        requires_human_review=not reviewed,
    )


def form_schema(procedure: Procedure) -> ProcedureFormSchema | None:
    if not capabilities(procedure).dynamic_form:
        return None
    template = procedure.form_templates[0]
    return ProcedureFormSchema(
        procedure_id=procedure.id,
        template_id=template.id,
        title=template.name,
        fields=template.fields,
    )
