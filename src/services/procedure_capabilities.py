"""Derive capabilities from whichever procedure/template assets are available."""

from pathlib import Path

from src.models import FormField, Procedure, ProcedureCapabilities, ProcedureFormSchema
from src.services import catalog
from src.services.drafts import registry as draft_registry

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"


def capabilities(procedure: Procedure) -> ProcedureCapabilities:
    reviewed = procedure.status in {"approved", "published"}
    fields = [field for template in procedure.form_templates for field in template.fields]
    draft_templates = draft_registry.list_templates(procedure.id)
    has_form = bool(fields or draft_templates)
    return ProcedureCapabilities(
        chat=True,
        checklist=bool(procedure.requirements),
        dynamic_form=has_form,
        ocr_autofill=has_form,
        legal_validation=(RULES_DIR / f"{procedure.id}.yaml").is_file(),
        official_draft=bool(draft_templates),
        requires_human_review=not reviewed,
    )


def capabilities_for(procedure_id: str) -> ProcedureCapabilities:
    """Resolve capabilities without requiring a catalog record.

    A searched/raw procedure can become draftable as soon as a source-backed
    template manifest exists. Such procedures remain marked for human review.
    """
    procedure = catalog.get_procedure(procedure_id)
    if procedure is not None:
        return capabilities(procedure)
    templates = draft_registry.list_templates(procedure_id)
    return ProcedureCapabilities(
        chat=True,
        dynamic_form=bool(templates),
        ocr_autofill=bool(templates),
        official_draft=bool(templates),
        requires_human_review=True,
    )


def form_schema(procedure: Procedure) -> ProcedureFormSchema | None:
    if procedure.form_templates:
        template = procedure.form_templates[0]
        return ProcedureFormSchema(
            procedure_id=procedure.id,
            template_id=template.id,
            title=template.name,
            fields=template.fields,
            clarifying_questions=procedure.clarifying_questions,
        )
    return form_schema_for(procedure.id)


def form_schema_for(
    procedure_id: str, template_id: str | None = None
) -> ProcedureFormSchema | None:
    """Build a dynamic form from catalog fields or a draft template manifest."""
    procedure = catalog.get_procedure(procedure_id)
    if procedure and procedure.form_templates and template_id is None:
        return form_schema(procedure)
    try:
        template = draft_registry.get_template(procedure_id, template_id)
    except draft_registry.DraftTemplateNotFound:
        return None
    fields = [
        FormField(
            key=field.key,
            label=field.label,
            type=(
                "date"
                if field.input_type == "date"
                else "number"
                if field.input_type == "year"
                else "select"
                if field.allowed_values
                else "text"
            ),
            required=field.required,
            options=field.allowed_values,
            ocr_sources=[f"unknown.{field.key}"],
        )
        for field in template.fields
    ]
    return ProcedureFormSchema(
        procedure_id=procedure_id,
        template_id=template.id,
        title=template.output_name,
        fields=fields,
        clarifying_questions=(procedure.clarifying_questions if procedure else []),
    )


def ocr_field_keys_for(procedure_id: str) -> list[str] | None:
    """Collect OCR targets from all available forms/templates for a procedure."""
    keys: list[str] = []
    procedure = catalog.get_procedure(procedure_id)
    if procedure:
        keys.extend(
            source.rsplit(".", 1)[-1]
            for template in procedure.form_templates
            for field in template.fields
            for source in (field.ocr_sources or [field.key])
        )
    keys.extend(
        field.key
        for template in draft_registry.list_templates(procedure_id)
        for field in template.fields
    )
    unique = list(dict.fromkeys(key for key in keys if key))
    return unique or None
