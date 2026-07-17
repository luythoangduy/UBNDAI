"""Answer node — hỏi đáp thủ tục bằng RAG, bắt buộc kèm citation (AGENTS.md §5).

Không có nguồn → trả cảnh báo "chưa đủ căn cứ", không đoán.
LLM lỗi/chưa cấu hình → fallback deterministic: trả trích dẫn nguyên văn từ catalog.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.prompts import ANSWER_SYSTEM, answer_user_prompt
from src.agents.state import GuidanceState
from src.services.llm import get_llm
from src.services.retrieval import (
    NO_SOURCE_WARNING,
    RetrievedChunk,
    citations_from_chunks,
    retrieve,
)

logger = logging.getLogger(__name__)


async def run(state: GuidanceState) -> dict[str, Any]:
    query = state.get("rewritten_query") or ""
    chunks = retrieve(query)

    # Ưu tiên chunks của thủ tục đã chọn (câu hỏi follow-up thường về nó)
    selected = state.get("selected_procedure_id")
    if selected:
        chunks = sorted(
            chunks, key=lambda c: 0 if c.procedure_id == selected else 1
        )

    if not chunks:
        return {
            "reply": NO_SOURCE_WARNING,
            "reply_kind": "fallback",
            "citations": [],
            "retrieved_chunks": [],
        }

    reply = await _llm_answer(query, chunks)
    if reply is None:
        reply = _extractive_answer(chunks)

    return {
        "reply": reply,
        "reply_kind": "answer",
        "citations": [c.model_dump() for c in citations_from_chunks(chunks)],
        "retrieved_chunks": [
            {"content": c.content, "metadata": c.metadata, "score": c.score}
            for c in chunks
        ],
    }


async def _llm_answer(query: str, chunks: list[RetrievedChunk]) -> str | None:
    try:
        sources_block = "\n\n".join(
            f"[{index}] ({chunk.metadata.get('procedure_name', '')} — "
            f"{chunk.metadata.get('section', '')})\n{chunk.content}"
            for index, chunk in enumerate(chunks, start=1)
        )
        llm = get_llm()
        response = await llm.ainvoke(
            [
                SystemMessage(content=ANSWER_SYSTEM),
                HumanMessage(
                    content=answer_user_prompt(
                        question=query, sources_block=sources_block
                    )
                ),
            ]
        )
        text = str(getattr(response, "content", "")).strip()
        return text or None
    except Exception:
        logger.warning("Answer LLM lỗi — fallback trích dẫn nguyên văn", exc_info=True)
        return None


def _extractive_answer(chunks: list[RetrievedChunk]) -> str:
    """Không tổng hợp được bằng LLM → trả nguyên văn đoạn catalog liên quan nhất."""
    lines = [
        "Mình chưa thể tổng hợp câu trả lời tự động lúc này. "
        "Dưới đây là thông tin chính thức liên quan từ catalog thủ tục:"
    ]
    for index, chunk in enumerate(chunks[:3], start=1):
        lines.append(f"[{index}] {chunk.excerpt()}")
    return "\n\n".join(lines)
