"""Sửa bản nháp bằng LLM và lọc HTML trước khi trả về UI duyệt diff."""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.prompts.draft_revision import (
    DRAFT_REVISION_SYSTEM,
    draft_revision_user_prompt,
)
from src.config import settings
from src.models import DraftRevision, DraftReviseRequest
from src.services.llm import get_llm, llm_is_configured

_FORBIDDEN_BLOCKS = re.compile(
    r"<(script|style|iframe|object|embed|svg|math)\b[^>]*>[\s\S]*?</\1>",
    re.IGNORECASE,
)
_FORBIDDEN_SINGLE = re.compile(
    r"<(script|style|iframe|object|embed|svg|math)\b[^>]*?/?>",
    re.IGNORECASE,
)
_ALLOWED_TAG = re.compile(
    r"</?(?:h[1-3]|p|strong|em|u|ul|ol|li|br)\b[^>]*>", re.IGNORECASE
)
_ANY_TAG = re.compile(r"<[^>]+>")


def _sanitize_html(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^```(?:html)?\s*|\s*```$", "", value, flags=re.IGNORECASE)
    value = _FORBIDDEN_BLOCKS.sub("", value)
    value = _FORBIDDEN_SINGLE.sub("", value)

    allowed: list[str] = []
    cursor = 0
    for match in _ANY_TAG.finditer(value):
        allowed.append(value[cursor : match.start()])
        tag = match.group(0)
        if _ALLOWED_TAG.fullmatch(tag):
            # Bỏ toàn bộ attribute để response không mang event/style/URL vào editor.
            closing = tag.startswith("</")
            name_match = re.match(r"</?([a-z0-9]+)", tag, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).lower()
                allowed.append(f"</{name}>" if closing else ("<br>" if name == "br" else f"<{name}>"))
        cursor = match.end()
    allowed.append(value[cursor:])
    return "".join(allowed).strip()


async def revise(payload: DraftReviseRequest) -> DraftRevision:
    if not llm_is_configured():
        raise RuntimeError("Chưa cấu hình mô hình AI để sửa bản nháp.")

    try:
        llm = get_llm(temperature=0.0)
        response = await llm.ainvoke(
            [
                SystemMessage(content=DRAFT_REVISION_SYSTEM),
                HumanMessage(
                    content=draft_revision_user_prompt(
                        html=payload.html,
                        instruction=payload.instruction,
                        selected_text=payload.selected_text,
                    )
                ),
            ]
        )
    except Exception as exc:
        raise RuntimeError("Mô hình AI chưa thể sửa bản nháp lúc này.") from exc
    revised = _sanitize_html(str(getattr(response, "content", "")))
    if not revised:
        raise RuntimeError("Mô hình không trả về nội dung có thể sử dụng.")
    return DraftRevision(
        revised_html=revised,
        summary=f'Đã xử lý yêu cầu: "{payload.instruction.strip()}"',
        model_used=settings.llm_model,
        warnings=["Hãy duyệt phần thêm/xóa trước khi áp dụng vào bản nháp."],
    )
