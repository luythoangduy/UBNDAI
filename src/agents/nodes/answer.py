"""Answer node — hỏi đáp thủ tục bằng RAG, bắt buộc kèm citation (AGENTS.md §5).

Không có nguồn → trả cảnh báo "chưa đủ căn cứ", không đoán.
LLM lỗi/chưa cấu hình → fallback deterministic: trả trích dẫn nguyên văn từ catalog.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.prompts import ANSWER_SYSTEM, answer_user_prompt
from src.agents.state import GuidanceState
from src.models import ChecklistItem
from src.services import catalog
from src.services import checklist as checklist_service
from src.services.clarification import unresolved_questions
from src.services.intent import detect_intents
from src.services.llm import get_llm, llm_is_configured
from src.services.retrieval import (
    NO_SOURCE_WARNING,
    RetrievedChunk,
    citations_from_chunks,
    chunks_from_procedure,
    retrieve,
)
from src.services.retrieval.legal import retrieve_legal

logger = logging.getLogger(__name__)


@dataclass
class StructuredAnswerResult:
    reply: str
    chunks: list[RetrievedChunk]
    checklist: list[ChecklistItem] = field(default_factory=list)
    pending_questions: list[str] = field(default_factory=list)


async def run(state: GuidanceState) -> dict[str, Any]:
    query = state.get("rewritten_query") or ""
    selected = state.get("selected_procedure_id")
    procedure = catalog.get_procedure(selected)
    intents = state.get("detected_intents") or detect_intents(
        query, has_selected_procedure=procedure is not None
    ).intents

    special = _special_intent_answer(intents)
    if special is not None:
        reply, kind = special
        return {
            "reply": reply,
            "reply_kind": kind,
            "citations": [],
            "retrieved_chunks": [],
        }

    if selected:
        chunks = retrieve(query, procedure_id=selected)
    elif not selected:
        # Không có workflow catalog vẫn tra cứu corpus VBPL. Catalog chỉ bật
        # checklist/form đã duyệt, không phải allow-list giới hạn hỏi đáp.
        chunks = retrieve_legal(query)
    else:
        chunks = retrieve(query)
    if procedure and not chunks:
        chunks = chunks_from_procedure(procedure)

    if not chunks:
        return {
            "reply": NO_SOURCE_WARNING,
            "reply_kind": "fallback",
            "citations": [],
            "retrieved_chunks": [],
        }

    deterministic = _structured_answer(state, query, procedure, chunks, intents)
    if deterministic is not None:
        reply, chunks = deterministic.reply, deterministic.chunks
    else:
        reply = await _llm_answer(query, chunks)
    if reply is None:
        reply = _extractive_answer(chunks)
    if _uses_legal_corpus(chunks):
        reply += (
            "\n\nLưu ý: đây là thông tin tra cứu từ corpus VBPL; hãy đối chiếu "
            "văn bản gốc tại liên kết trích dẫn và quy định còn hiệu lực trước khi thực hiện."
        )

    result = {
        "reply": reply,
        "reply_kind": "answer",
        "citations": [c.model_dump() for c in citations_from_chunks(chunks)],
        "retrieved_chunks": [
            {"content": c.content, "metadata": c.metadata, "score": c.score}
            for c in chunks
        ],
    }
    if deterministic is not None and deterministic.checklist:
        result.update(
            {
                "checklist": [item.model_dump() for item in deterministic.checklist],
                "pending_questions": deterministic.pending_questions,
                "pending_action": (
                    "answer_clarification"
                    if deterministic.pending_questions
                    else None
                ),
                "pending_question_keys": [
                    question.key
                    for question in unresolved_questions(
                        procedure, state.get("answers") or {}
                    )
                ],
            }
        )
    return result


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
    """Không tổng hợp được bằng LLM → trả nguyên văn các đoạn nguồn liên quan nhất."""
    legal = _uses_legal_corpus(chunks)
    lines = [
        "Mình chưa thể tổng hợp câu trả lời tự động lúc này. "
        + (
            "Dưới đây là các đoạn văn bản pháp luật liên quan:"
            if legal
            else "Dưới đây là thông tin chính thức liên quan từ catalog thủ tục:"
        )
    ]
    for index, chunk in enumerate(chunks[:3], start=1):
        lines.append(f"[{index}] {chunk.excerpt()}")
    return "\n\n".join(lines)


def _uses_legal_corpus(chunks: list[RetrievedChunk]) -> bool:
    return any(
        chunk.metadata.get("source_type") in {"huggingface_dataset", "legal_corpus"}
        or chunk.metadata.get("source_scope") == "public_vbpl"
        for chunk in chunks
    )


def _structured_answer(
    state: GuidanceState,
    query: str,
    procedure: Any,
    chunks: list[RetrievedChunk],
    intents: list[str],
) -> StructuredAnswerResult | None:
    """Trả một hoặc nhiều intent có cấu trúc trực tiếp từ Procedure."""
    if procedure is None:
        return None
    overview = next(
        (chunk for chunk in chunks if chunk.metadata.get("section") == "tong_quan"),
        chunks_from_procedure(procedure)[0],
    )
    requested = set(intents)
    if not requested:
        requested = set(
            detect_intents(query, has_selected_procedure=True).intents
        )
    lines: list[str] = []
    used_chunks: list[RetrievedChunk] = []
    checklist_items: list[ChecklistItem] = []
    pending_questions: list[str] = []

    def cite(chunk: RetrievedChunk) -> int:
        if chunk not in used_chunks:
            used_chunks.append(chunk)
        return used_chunks.index(chunk) + 1

    if "fee" in requested and procedure.fee_vnd is not None:
        fee = "được miễn" if procedure.fee_vnd == 0 else f"là {procedure.fee_vnd:,} đồng"
        lines.append(f"Lệ phí thủ tục {procedure.name} {fee} [{cite(overview)}].")
    if "processing_time" in requested and procedure.processing_days is not None:
        lines.append(
            f"Thời hạn xử lý thủ tục {procedure.name} là "
            f"{procedure.processing_days} ngày làm việc [{cite(overview)}]."
        )
    if "agency" in requested:
        lines.append(
            f"Cơ quan thực hiện thủ tục {procedure.name}: "
            f"{procedure.agency} [{cite(overview)}]."
        )
    if "legal_basis" in requested and procedure.legal_basis:
        lines.append(
            f"Căn cứ pháp lý: {'; '.join(procedure.legal_basis)} [{cite(overview)}]."
        )
    if "forms" in requested and procedure.form_templates:
        form_chunk = next(
            (chunk for chunk in chunks if chunk.metadata.get("section") == "bieu_mau"),
            chunks_from_procedure(procedure)[-1],
        )
        names = "; ".join(
            f"{template.name} ({template.id})" for template in procedure.form_templates
        )
        lines.append(f"Biểu mẫu: {names} [{cite(form_chunk)}].")
    if "checklist" in requested:
        requirement_chunk = next(
            (
                chunk
                for chunk in chunks
                if chunk.metadata.get("section") == "thanh_phan_ho_so"
            ),
            chunks_from_procedure(procedure)[1],
        )
        checklist_items = checklist_service.build_checklist(
            procedure, state.get("answers") or {}
        )
        names = []
        answers = state.get("answers") or {}
        for item in checklist_items:
            if item.status == "not_applicable":
                continue
            requirement = checklist_service.requirement_by_code(
                procedure, item.requirement_code
            )
            if requirement and checklist_service.eval_condition(
                requirement.condition, answers
            ) is True:
                names.append(requirement.name)
        unanswered = unresolved_questions(procedure, answers)
        pending_questions = [question.text for question in unanswered]
        heading = "Checklist tạm thời" if pending_questions else "Checklist"
        lines.append(
            f"{heading}: " + "; ".join(names) + f" [{cite(requirement_chunk)}]."
        )
        if pending_questions:
            lines.append(
                "Để xác định chính xác các giấy tờ theo trường hợp của bạn, "
                "vui lòng trả lời các câu hỏi làm rõ bên dưới."
            )
    return (
        StructuredAnswerResult(
            reply="\n".join(lines),
            chunks=used_chunks,
            checklist=checklist_items,
            pending_questions=pending_questions,
        )
        if lines
        else None
    )


def _special_intent_answer(
    intents: list[str],
) -> tuple[str, str] | None:
    intent_set = set(intents)
    if "greeting" in intent_set:
        return (
            "Chào bạn! Mình hỗ trợ hướng dẫn thủ tục hành chính, xác định thủ tục "
            "và lập checklist hồ sơ theo catalog hiện có.",
            "answer",
        )
    if "thanks" in intent_set:
        return "Rất vui được hỗ trợ bạn.", "answer"
    if "switch_confirmation" in intent_set:
        return "Đã giữ nguyên thủ tục và dữ liệu hiện tại của case.", "answer"
    if "capabilities" in intent_set:
        return (
            "Mình có thể nhận diện thủ tục trong catalog, hỏi thông tin làm rõ, "
            "lập checklist và trả lời về lệ phí, thời hạn, nơi nộp, căn cứ pháp lý, biểu mẫu.",
            "answer",
        )
    if "status_tracking" in intent_set:
        return (
            "Chat hiện chưa được nối với hệ thống tra cứu trạng thái hồ sơ. "
            "Bạn cần dùng mã hồ sơ trên Cổng Dịch vụ công hoặc liên hệ cơ quan tiếp nhận.",
            "fallback",
        )
    if "submission" in intent_set or "document_upload" in intent_set:
        return (
            "Chat hiện chỉ hướng dẫn chuẩn bị hồ sơ; chức năng upload hoặc nộp hồ sơ "
            "chưa được kích hoạt tại endpoint này.",
            "fallback",
        )
    if "out_of_scope" in intent_set:
        return (
            "Yêu cầu này nằm ngoài phạm vi trợ lý thủ tục hành chính. "
            "Bạn có thể mô tả thủ tục hoặc hồ sơ hành chính cần hỗ trợ.",
            "fallback",
        )
    if "unknown" in intent_set:
        return (
            "Mình chưa hiểu rõ yêu cầu. Bạn hãy nêu tên thủ tục hoặc việc hành chính "
            "cần làm, cùng nội dung muốn hỏi như hồ sơ, lệ phí hoặc nơi nộp.",
            "fallback",
        )
    return None


def _citation_indexes(reply: str) -> set[int]:
    return {int(value) for value in re.findall(r"\[(\d+)\]", reply)}
