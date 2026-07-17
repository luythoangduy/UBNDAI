"""Answer node — hỏi đáp thủ tục bằng RAG, bắt buộc kèm citation (AGENTS.md §5).

Không có nguồn → trả cảnh báo "chưa đủ căn cứ", không đoán.
LLM lỗi/chưa cấu hình → fallback deterministic: trả trích dẫn nguyên văn từ catalog.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.prompts import ANSWER_SYSTEM, answer_user_prompt
from src.agents.state import GuidanceState
from src.services import catalog
from src.services.llm import get_llm, llm_is_configured
from src.services.retrieval import (
    NO_SOURCE_WARNING,
    RetrievedChunk,
    citations_from_chunks,
    chunks_from_procedure,
    retrieve,
)

logger = logging.getLogger(__name__)


async def run(state: GuidanceState) -> dict[str, Any]:
    query = state.get("rewritten_query") or ""
    selected = state.get("selected_procedure_id")
    procedure = catalog.get_procedure(selected)
    chunks = retrieve(query, procedure_id=selected) if selected else retrieve(query)
    if procedure and not chunks:
        chunks = chunks_from_procedure(procedure)

    if not chunks:
        return {
            "reply": NO_SOURCE_WARNING,
            "reply_kind": "fallback",
            "citations": [],
            "retrieved_chunks": [],
        }

    deterministic = _structured_answer(query, procedure, chunks)
    if deterministic is not None:
        reply, chunks = deterministic
    else:
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
    if not llm_is_configured():
        return None
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
        if not text:
            return None
        indexes = _citation_indexes(text)
        if not indexes or any(index < 1 or index > len(chunks) for index in indexes):
            logger.warning("Answer LLM trả citation index không hợp lệ — dùng fallback")
            return None
        return text
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


def _structured_answer(
    query: str,
    procedure: Any,
    chunks: list[RetrievedChunk],
) -> tuple[str, list[RetrievedChunk]] | None:
    """Thông tin có cấu trúc đọc thẳng từ Procedure, không cần LLM."""
    if procedure is None:
        return None
    folded = query.casefold()
    overview = next(
        (chunk for chunk in chunks if chunk.metadata.get("section") == "tong_quan"),
        chunks_from_procedure(procedure)[0],
    )
    if any(term in folded for term in ("lệ phí", "le phi", "bao nhiêu tiền")):
        if procedure.fee_vnd is None:
            return None
        fee = "được miễn" if procedure.fee_vnd == 0 else f"là {procedure.fee_vnd:,} đồng"
        return f"Lệ phí thủ tục {procedure.name} {fee} [1].", [overview]
    if any(term in folded for term in ("thời hạn", "thoi han", "mấy ngày", "bao lâu")):
        if procedure.processing_days is None:
            return None
        return (
            f"Thời hạn xử lý thủ tục {procedure.name} là "
            f"{procedure.processing_days} ngày làm việc [1].",
            [overview],
        )
    if any(term in folded for term in ("cơ quan", "co quan", "nơi nộp", "noi nop")):
        return f"Cơ quan thực hiện thủ tục {procedure.name}: {procedure.agency} [1].", [overview]
    return None


def _citation_indexes(reply: str) -> set[int]:
    return {int(value) for value in re.findall(r"\[(\d+)\]", reply)}
