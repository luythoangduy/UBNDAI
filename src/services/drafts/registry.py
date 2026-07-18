"""Load registry mẫu kết quả thủ tục từ ``data/draft_templates/*.json``."""

from __future__ import annotations

import json
from pathlib import Path

from src.models import DraftTemplate

DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "data" / "draft_templates"

_CACHE: dict[str, dict[str, DraftTemplate]] = {}
_RUNTIME_TEMPLATES: dict[str, DraftTemplate] = {}


class DraftTemplateNotFound(LookupError):
    pass


def load_templates(
    template_dir: Path | str | None = None,
) -> dict[str, DraftTemplate]:
    directory = Path(template_dir) if template_dir else DEFAULT_TEMPLATE_DIR
    cache_key = str(directory.resolve())
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    templates: dict[str, DraftTemplate] = {}
    defaults: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        template = DraftTemplate.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
        if template.id in templates:
            raise ValueError(f"Duplicate draft template id {template.id!r}")
        if template.is_default and template.procedure_id in defaults:
            raise ValueError(
                f"Procedure {template.procedure_id!r} có nhiều default draft template"
            )
        templates[template.id] = template
        if template.is_default:
            defaults.add(template.procedure_id)
    for template in _RUNTIME_TEMPLATES.values():
        if template.id in templates:
            continue
        if template.is_default and template.procedure_id in defaults:
            template = template.model_copy(update={"is_default": False})
        templates[template.id] = template
        if template.is_default:
            defaults.add(template.procedure_id)
    _CACHE[cache_key] = templates
    return templates


def list_templates(procedure_id: str) -> list[DraftTemplate]:
    return [
        template
        for template in load_templates().values()
        if template.procedure_id == procedure_id
    ]


def get_template(procedure_id: str, template_id: str | None = None) -> DraftTemplate:
    candidates = list_templates(procedure_id)
    if template_id:
        for template in candidates:
            if template.id == template_id:
                return template
        raise DraftTemplateNotFound(
            f"Không có template {template_id!r} cho procedure {procedure_id!r}"
        )
    for template in candidates:
        if template.is_default:
            return template
    raise DraftTemplateNotFound(
        f"Chưa cấu hình template kết quả cho procedure {procedure_id!r}"
    )


def register_template(template: DraftTemplate) -> DraftTemplate:
    """Register a source-derived template for the lifetime of this process."""
    existing = _RUNTIME_TEMPLATES.get(template.id)
    if existing is not None:
        return existing
    _RUNTIME_TEMPLATES[template.id] = template
    _CACHE.clear()
    return template


def clear_cache(*, clear_runtime: bool = True) -> None:
    _CACHE.clear()
    if clear_runtime:
        _RUNTIME_TEMPLATES.clear()
