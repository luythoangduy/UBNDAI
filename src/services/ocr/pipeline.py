"""Pipeline OCR đầy đủ: file → doc_type → fields → ExtractedDocument. Owner: Dev B.

Bước:
1. Tiền xử lý ảnh (EXIF, làm phẳng/deskew, chính diện/perspective, CLAHE) — ``preprocessing.py``.
2. ``engine.extract`` (chạy trong thread — engine sync theo Protocol).
3. doc_type: hint từ engine (vision LLM tự nhận diện) cross-check với
   ``classifier.classify(raw_text)`` (keyword matching): khớp nhau → tin cậy hơn;
   lệch nhau khi classifier chắc chắn → needs_human_review.
4. needs_human_review=True khi: trường/doc_type dưới ngưỡng OCR_CONFIDENCE_THRESHOLD,
   HOẶC có vùng [ILLEGIBLE], HOẶC ocr_confidence tổng thể dưới ngưỡng
   (AGENTS §5: confidence thấp bắt buộc needs_human_review, không im lặng điền form).
5. TODO(B) Sprint 1: lưu file qua upload_storage (port từ C2) → file_id thật.
6. TODO(B) Sprint 2: form_filler.autofill(case) + cập nhật ChecklistItem khớp
   accepted_doc_types → status='uploaded'.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from src.config import settings
from src.models import ExtractedDocument, ExtractedField
from src.services.ocr.classifier import classify
from src.services.ocr.engine import OcrField, OcrResult, VisionLlmEngine, get_engine
from src.services.ocr.pdf import rasterize_pdf
from src.services.ocr.preprocessing import preprocess_document_image

_CLASSIFIER_STRONG_CONFIDENCE = 0.8
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

# Cache OcrResult theo hash ảnh đã tiền xử lý — upload lại cùng ảnh (công dân bấm
# lại, refresh, retry) không tốn thêm API call. OcrResult là frozen dataclass nên
# chia sẻ an toàn; ExtractedDocument vẫn được build mới cho từng lần gọi.
_ocr_cache: OrderedDict[str, OcrResult] = OrderedDict()


def _cache_key(image_bytes: bytes, field_keys: list[str] | None) -> str:
    digest = hashlib.sha256(image_bytes).hexdigest()
    config_sig = (
        f"{settings.ocr_llm_provider}|{settings.ocr_llm_model}"
        f"|{getattr(settings, 'ocr_llm_reasoning_effort', '')}"
        f"|{','.join(field_keys or [])}"
    )
    return f"{digest}|{config_sig}"


def _cache_get(key: str) -> OcrResult | None:
    if settings.ocr_cache_size <= 0:
        return None
    result = _ocr_cache.get(key)
    if result is not None:
        _ocr_cache.move_to_end(key)
    return result


def _cache_put(key: str, result: OcrResult) -> None:
    if settings.ocr_cache_size <= 0:
        return
    _ocr_cache[key] = result
    _ocr_cache.move_to_end(key)
    while len(_ocr_cache) > settings.ocr_cache_size:
        _ocr_cache.popitem(last=False)


def _resolve_doc_type(result: OcrResult) -> tuple[str, float, bool]:
    """Cross-check doc_type giữa engine hint và keyword classifier.

    Trả (doc_type, confidence, conflicting). Hai nguồn khớp nhau → lấy confidence
    cao hơn; engine không biết → dùng classifier; lệch nhau khi classifier chắc
    chắn → giữ hint của engine nhưng đánh dấu conflicting để bắt human review.
    """
    cls_type, cls_confidence = classify(result.raw_text)
    engine_type = result.doc_type_hint

    if engine_type == "unknown":
        return cls_type, cls_confidence, False
    if cls_type == "unknown" or cls_type == engine_type:
        return engine_type, max(result.doc_type_confidence, cls_confidence), False
    if cls_confidence >= _CLASSIFIER_STRONG_CONFIDENCE:
        return engine_type, result.doc_type_confidence, True
    return engine_type, result.doc_type_confidence, False


def _merge_page_results(results: list[OcrResult]) -> OcrResult:
    """Merge multi-page OCR conservatively and flag cross-page conflicts."""
    if len(results) == 1:
        return results[0]

    selected_fields: dict[str, OcrField] = {}
    seen_values: dict[str, set[str]] = {}
    for result in results:
        for field in result.fields:
            normalized = field.value.strip().casefold()
            if normalized:
                seen_values.setdefault(field.key, set()).add(normalized)
            current = selected_fields.get(field.key)
            if current is None or (
                bool(field.value.strip()), field.confidence
            ) > (bool(current.value.strip()), current.confidence):
                selected_fields[field.key] = field

    conflicts = sorted(key for key, values in seen_values.items() if len(values) > 1)
    known_types = {
        result.doc_type_hint
        for result in results
        if result.doc_type_hint != "unknown"
    }
    best_type = max(
        results,
        key=lambda item: (
            item.doc_type_hint != "unknown", item.doc_type_confidence
        ),
    )
    issues = [
        f"Trang {index}: {issue}"
        for index, result in enumerate(results, start=1)
        for issue in result.quality_issues
    ]
    if conflicts:
        issues.append("Giá trị khác nhau giữa các trang: " + ", ".join(conflicts))
    if len(known_types) > 1:
        issues.append("Các trang được nhận dạng thành nhiều loại tài liệu")

    forced_review = bool(conflicts) or len(known_types) > 1
    return OcrResult(
        raw_text="\n\n".join(
            f"--- Trang {index} ---\n{result.raw_text}"
            for index, result in enumerate(results, start=1)
        ),
        fields=list(selected_fields.values()),
        doc_type_hint=best_type.doc_type_hint,
        doc_type_confidence=(
            0.0 if len(known_types) > 1 else best_type.doc_type_confidence
        ),
        engine=best_type.engine,
        handwriting_notes=[
            note for result in results for note in result.handwriting_notes
        ],
        illegible_regions=[
            f"trang {index}: {region}"
            for index, result in enumerate(results, start=1)
            for region in result.illegible_regions
        ],
        ocr_confidence=(
            0.0
            if forced_review
            else min(result.ocr_confidence for result in results)
        ),
        handwriting_confidence=min(
            result.handwriting_confidence for result in results
        ),
        quality_issues=issues,
    )


async def process(
    case_id: str,
    filename: str,
    content: bytes,
    field_keys: list[str] | None = None,
) -> ExtractedDocument:
    """Chạy OCR một file ảnh giấy tờ và trả ExtractedDocument (chưa persist).

    ``field_keys``: danh sách trường chuẩn hoá cần trích (vd từ FormField.ocr_sources
    của thủ tục) — hiện chỉ VisionLlmEngine tận dụng được.
    """
    if len(content) > _MAX_UPLOAD_BYTES:
        raise ValueError("File too large; maximum is 10 MB")
    if Path(filename).suffix.casefold() not in _ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported document extension")

    extension = Path(filename).suffix.casefold()
    if extension == ".pdf":
        rasterized_pages = await asyncio.to_thread(rasterize_pdf, content)
        image_pages = []
        for page in rasterized_pages:
            preprocessed = preprocess_document_image(page)
            image_pages.append(
                preprocessed.content if preprocessed.mime_type else page
            )
    else:
        preprocessed = preprocess_document_image(content)
        image_pages = [preprocessed.content if preprocessed.mime_type else content]

    engine = None
    page_results: list[OcrResult] = []
    for image_bytes in image_pages:
        cache_key = _cache_key(image_bytes, field_keys)
        page_result = _cache_get(cache_key)
        if page_result is None:
            engine = engine or get_engine()
            if isinstance(engine, VisionLlmEngine):
                page_result = await asyncio.to_thread(
                    engine.extract, image_bytes, field_keys
                )
            else:
                page_result = await asyncio.to_thread(engine.extract, image_bytes)
            _cache_put(cache_key, page_result)
        page_results.append(page_result)
    result = _merge_page_results(page_results)

    doc_type, doc_type_confidence, conflicting = _resolve_doc_type(result)

    threshold = settings.ocr_confidence_threshold
    fields = [
        ExtractedField(key=f.key, value=f.value, confidence=f.confidence, bbox=f.bbox)
        for f in result.fields
    ]
    needs_human_review = (
        conflicting
        or doc_type == "unknown"
        or doc_type_confidence < threshold
        or any(f.confidence < threshold for f in fields)
        or bool(result.illegible_regions)
        or result.ocr_confidence < threshold
    )

    return ExtractedDocument(
        id=f"doc_{uuid4().hex}",
        case_id=case_id,
        file_id=f"file_{uuid4().hex}",  # TODO(B) Sprint 1: id thật từ upload_storage
        doc_type=doc_type,
        doc_type_confidence=doc_type_confidence,
        fields=fields,
        raw_text=result.raw_text or None,
        needs_human_review=needs_human_review,
        ocr_engine=result.engine or settings.ocr_engine,
        created_at=datetime.now(UTC),
    )
