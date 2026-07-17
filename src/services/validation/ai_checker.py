"""AI cross-check mâu thuẫn ngữ nghĩa giữa các giấy tờ. Owner: Dev B.

Chỉ sinh warning/info — ValidationIssue tự chặn error từ source='ai'.
Input: field_map các giấy tờ + form_data. Output structured (JSON schema) → ValidationIssue.
Ví dụ bắt được: tên khác dấu giữa CCCD và giấy chứng sinh, địa chỉ không nhất quán.
LLM lỗi/timeout → trả [] (validation không được chết vì AI checker).

Dùng bộ LLM_* của chatbot (Anthropic Haiku — rẻ, đủ cho so khớp ngữ nghĩa),
KHÔNG dùng bộ OCR_LLM_* — hai bên tách riêng theo quyết định team.
"""

from __future__ import annotations

import json
import logging

import anthropic

from src.agents.prompts.validation import (
    AI_CHECKER_OUTPUT_SCHEMA,
    AI_CHECKER_SYSTEM_PROMPT,
)
from src.config import settings
from src.models import Case, ExtractedDocument, ValidationIssue

logger = logging.getLogger(__name__)


def _build_dossier_text(case: Case, documents: list[ExtractedDocument]) -> str:
    lines: list[str] = ["## Trường trích xuất từ giấy tờ (OCR)"]
    for doc in documents:
        lines.append(f"### {doc.doc_type}")
        for extracted in doc.fields:
            lines.append(f"- {extracted.key}: {extracted.value!r}")
    lines.append("## Dữ liệu biểu mẫu người dân đã điền")
    for key, value in case.form_data.items():
        lines.append(f"- {key}: {value!r}")
    if case.answers:
        lines.append("## Câu trả lời làm rõ")
        for key, value in case.answers.items():
            lines.append(f"- {key}: {value!r}")
    return "\n".join(lines)


async def run(
    case: Case,
    documents: list[ExtractedDocument],
    client: anthropic.AsyncAnthropic | None = None,
) -> list[ValidationIssue]:
    if not documents and not case.form_data:
        return []
    if client is None:
        if not settings.llm_api_key:
            logger.warning("AI checker bỏ qua: LLM_API_KEY chưa cấu hình")
            return []
        client = anthropic.AsyncAnthropic(api_key=settings.llm_api_key, timeout=45.0)

    try:
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=4096,
            system=AI_CHECKER_SYSTEM_PROMPT,
            output_config={
                "format": {"type": "json_schema", "schema": AI_CHECKER_OUTPUT_SCHEMA}
            },
            messages=[{"role": "user", "content": _build_dossier_text(case, documents)}],
        )
        if response.stop_reason == "refusal":
            return []
        text = "".join(b.text for b in response.content if b.type == "text")
        parsed = json.loads(text)
    except Exception:  # AGENTS §5: validation không được chết vì AI checker
        logger.exception("AI checker failed — returning no issues")
        return []

    issues: list[ValidationIssue] = []
    for item in parsed.get("issues") or []:
        try:
            severity = item.get("severity")
            issues.append(
                ValidationIssue(
                    rule_id=f"ai.{item.get('kind') or 'finding'}",
                    severity=severity if severity in ("warning", "info") else "warning",
                    message=str(item.get("message") or ""),
                    field_keys=[str(k) for k in (item.get("field_keys") or [])],
                    suggestion=str(item.get("suggestion") or "") or None,
                    source="ai",
                )
            )
        except Exception:
            logger.warning("AI checker: bỏ qua issue không hợp lệ: %r", item)
    return [i for i in issues if i.message.strip()]
