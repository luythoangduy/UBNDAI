"""Import a searched official image/PDF template through the OCR engine."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import date
from urllib.parse import urlparse

import httpx

from src.agents.prompts.ocr import VISION_TEMPLATE_ANALYSIS_TASK
from src.config import settings
from src.models import (
    DraftDocxStyle,
    DraftFieldSpec,
    DraftLayoutBlock,
    DraftLegalSource,
    DraftTemplate,
    DraftTemplateImportRequest,
)
from src.services.drafts import registry
from src.services.ocr.engine import OcrEngineError, OcrField, VisionLlmEngine, get_engine
from src.services.ocr.pdf import rasterize_pdf
from src.services.ocr.preprocessing import preprocess_document_image

_ALLOWED_MEDIA_TYPES = {"application/pdf", "image/png", "image/jpeg"}
_MAX_TEMPLATE_BYTES = 10 * 1024 * 1024


class TemplateImportError(ValueError):
    pass


async def import_template(payload: DraftTemplateImportRequest) -> DraftTemplate:
    source_url = str(payload.source_url)
    _validate_source_url(source_url)
    template_id = _template_id(payload.procedure_id, source_url)
    try:
        return registry.get_template(payload.procedure_id, template_id)
    except registry.DraftTemplateNotFound:
        pass

    content, media_type = await _download(source_url)
    try:
        pages = (
            await asyncio.to_thread(rasterize_pdf, content)
            if media_type == "application/pdf"
            else [content]
        )
        engine = get_engine()
    except (ValueError, OcrEngineError) as exc:
        raise TemplateImportError(str(exc)) from exc
    if not isinstance(engine, VisionLlmEngine):
        raise TemplateImportError(
            "Template analysis requires OCR_ENGINE=vision_llm"
        )

    extracted: list[OcrField] = []
    try:
        for page in pages:
            prepared = await asyncio.to_thread(preprocess_document_image, page)
            image = prepared.content if prepared.mime_type else page
            result = await asyncio.to_thread(
                engine.extract, image, None, VISION_TEMPLATE_ANALYSIS_TASK
            )
            extracted.extend(result.fields)
    except OcrEngineError as exc:
        raise TemplateImportError("OCR could not analyze the searched template") from exc
    fields = _field_specs(extracted)
    if not fields:
        raise TemplateImportError(
            "OCR did not identify any fillable fields in the searched template"
        )

    parsed = urlparse(source_url)
    template = DraftTemplate(
        id=template_id,
        procedure_id=payload.procedure_id,
        output_name=payload.title,
        version=f"ocr-{hashlib.sha256(content).hexdigest()[:12]}",
        is_default=not registry.list_templates(payload.procedure_id),
        source_checked_on=date.today(),
        legal_sources=[
            DraftLegalSource(
                document_number="Nguồn mẫu trực tuyến",
                title=payload.title,
                issuing_authority=parsed.hostname or "Cơ quan công bố",
                role="output_template",
                source_url=payload.source_url,
                applicability_note=(
                    "Cấu trúc trường được OCR từ tệp nguồn; phải đối chiếu lại "
                    "với bản gốc trước khi sử dụng."
                ),
            )
        ],
        fields=fields,
        layout=[
            DraftLayoutBlock(kind="title", text=payload.title.upper()),
            *[
                DraftLayoutBlock(kind="field", field=field.key)
                for field in fields
            ],
        ],
        docx_style=_default_docx_style(template_id),
        disclaimer=(
            "Bản nháp được dựng từ template tìm thấy trên nguồn trực tuyến và schema OCR; "
            "không thay thế biểu mẫu gốc. Người dùng và cơ quan tiếp nhận phải đối chiếu "
            "bố cục, nội dung, phiên bản và dữ liệu trước khi sử dụng."
        ),
    )
    return registry.register_template(template)


def _validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    official = bool(
        host.endswith(".gov.vn")
        or host in {
            "dichvucong.gov.vn",
            "thutuc.dichvucong.gov.vn",
            "vanban.chinhphu.vn",
            "vbpl.vn",
        }
        or host.endswith(".moj.gov.vn")
    )
    if (
        parsed.scheme != "https"
        or not official
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise TemplateImportError(
            "Automatic template import is limited to trusted official HTTPS sources"
        )


async def _download(url: str) -> tuple[bytes, str]:
    try:
        async with httpx.AsyncClient(
            timeout=settings.official_source_timeout_s,
            follow_redirects=False,
        ) as client, client.stream(
            "GET", url, headers={"User-Agent": "TTHC-Assist/0.1 template-import"}
        ) as response:
            response.raise_for_status()
            media_type = response.headers.get("content-type", "").split(";", 1)[0]
            if media_type not in _ALLOWED_MEDIA_TYPES:
                raise TemplateImportError(
                    "Searched template must be a JPEG, PNG or PDF file"
                )
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > _MAX_TEMPLATE_BYTES:
                    raise TemplateImportError("Searched template exceeds 10 MB")
                chunks.append(chunk)
    except TemplateImportError:
        raise
    except httpx.HTTPError as exc:
        raise TemplateImportError("Could not download the searched template") from exc
    content = b"".join(chunks)
    if not content:
        raise TemplateImportError("Searched template is empty")
    signatures = {
        "application/pdf": (b"%PDF-",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/jpeg": (b"\xff\xd8\xff",),
    }
    if not any(content.startswith(signature) for signature in signatures[media_type]):
        raise TemplateImportError(
            "Searched template content does not match its declared file type"
        )
    return content, media_type


def _field_specs(fields: list[OcrField]) -> list[DraftFieldSpec]:
    result: list[DraftFieldSpec] = []
    seen: set[str] = set()
    for field in fields:
        if not field.key or field.key in seen:
            continue
        seen.add(field.key)
        marker = field.value.strip()
        allowed: list[str] = []
        input_type = "text"
        if marker == "__DATE__":
            input_type = "date"
        elif marker == "__YEAR__":
            input_type = "year"
        elif marker.startswith("__OPTION__:"):
            allowed = [item.strip() for item in marker.split(":", 1)[1].split("|") if item.strip()]
        result.append(
            DraftFieldSpec(
                key=field.key,
                label=field.note.strip() or field.key.replace("_", " ").capitalize(),
                input_type=input_type,
                required=False,
                allowed_values=allowed,
                description=(
                    f"OCR template field; label confidence {field.confidence:.0%}. "
                    "Verify against the linked source."
                ),
            )
        )
    return result


def _template_id(procedure_id: str, source_url: str) -> str:
    digest = hashlib.sha256(source_url.encode()).hexdigest()[:12]
    safe_procedure = "".join(
        character if character.isalnum() or character in "_.-" else "-"
        for character in procedure_id
    )
    return f"remote.{safe_procedure}.{digest}"


def _default_docx_style(template_id: str) -> DraftDocxStyle:
    safe_name = template_id.replace(".", "-")[:90]
    return DraftDocxStyle(
        filename=f"{safe_name}.docx",
        page_width_mm=210,
        page_height_mm=297,
        margin_top_mm=20,
        margin_right_mm=20,
        margin_bottom_mm=20,
        margin_left_mm=20,
        body_font="Times New Roman",
        body_size_pt=13,
        line_spacing_pt=20,
        title_size_pt=18,
        title_color_hex="000000",
        notes_font_size_pt=10,
        notes_table_width_mm=170,
        notes_table_height_mm=30,
    )
