"""Identify node — hybrid retrieval trên catalog → chọn thủ tục + độ tin cậy.

Deterministic (không LLM): điểm tin cậy từ rank retrieval, thông tin thủ tục
lấy từ catalog (AGENTS.md §5 — không lấy từ prompt).
"""

from __future__ import annotations

from typing import Any

from src.agents.state import GuidanceState
from src.config import settings
from src.services import catalog
from src.services.retrieval import (
    NO_SOURCE_WARNING,
    citations_from_chunks,
    retrieve_procedure_identity,
)
from src.services.retrieval.raw_procedures import get_document as get_raw_document


async def run(state: GuidanceState) -> dict[str, Any]:
    query = state.get("rewritten_query") or ""
    chunks = retrieve_procedure_identity(query)
    if not chunks:
        return {
            "reply": NO_SOURCE_WARNING,
            "reply_kind": "fallback",
            "citations": [],
            "retrieved_chunks": [],
            "pending_action": None,
            "pending_procedure_ids": [],
            "pending_question_keys": [],
        }

    scores: dict[str, float] = {}
    for rank, chunk in enumerate(chunks, start=1):
        if chunk.procedure_id:
            relevance = float(chunk.score or (1.0 / (60 + rank)))
            scores[chunk.procedure_id] = max(
                scores.get(chunk.procedure_id, float("-inf")), relevance
            )
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ranked:
        return {
            "reply": NO_SOURCE_WARNING,
            "reply_kind": "fallback",
            "citations": [],
            "retrieved_chunks": [],
            "pending_action": None,
            "pending_procedure_ids": [],
            "pending_question_keys": [],
        }
    candidates = [
        {"procedure_id": procedure_id, "score": round(score, 6)}
        for procedure_id, score in ranked
    ]
    top_id, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_score - second_score
    confidence = top_score / (top_score + second_score) if second_score > 0 else 1.0
    is_relevant = top_score >= settings.identify_min_relevance

    retrieved = [
        {"content": c.content, "metadata": c.metadata, "score": c.score} for c in chunks
    ]

    if not is_relevant:
        return {
            "identify_confidence": round(confidence, 4),
            "candidate_procedures": candidates,
            "reply": NO_SOURCE_WARNING,
            "reply_kind": "fallback",
            "citations": [],
            "retrieved_chunks": retrieved,
            "pending_action": None,
            "pending_procedure_ids": [],
            "pending_question_keys": [],
        }

    is_distinct = len(ranked) == 1 or margin >= settings.identify_min_margin
    if (
        is_relevant
        and is_distinct
        and confidence >= settings.identify_confidence_threshold
    ):
        procedure = catalog.get_procedure(top_id)
        if procedure is None:
            raw_document = get_raw_document(top_id)
            if raw_document is None:  # index lệch nguồn — không đoán
                return {
                    "reply": NO_SOURCE_WARNING,
                    "reply_kind": "fallback",
                    "citations": [],
                    "retrieved_chunks": retrieved,
                    "pending_action": None,
                    "pending_procedure_ids": [],
                    "pending_question_keys": [],
                }
            proc_chunks = [c for c in chunks if c.procedure_id == top_id]
            return {
                "selected_procedure_id": top_id,
                "identify_confidence": round(confidence, 4),
                "candidate_procedures": candidates,
                "pending_questions": [],
                "pending_action": None,
                "pending_procedure_ids": [],
                "pending_question_keys": [],
                "reply": (
                    f"Mình đã tìm thấy thủ tục {raw_document.procedure_name} từ nguồn chính thức. "
                    "Nội dung này dùng được cho hỏi đáp có trích dẫn; checklist, biểu mẫu và "
                    "validation chưa bật vì bản chuẩn hoá đang chờ kiểm duyệt."
                ),
                "reply_kind": "answer",
                "citations": [c.model_dump() for c in citations_from_chunks(proc_chunks)],
                "retrieved_chunks": retrieved,
            }
        questions = [question.text for question in procedure.clarifying_questions]
        reply = _procedure_intro(procedure)
        if questions:
            reply += "\n\nĐể lên checklist đúng trường hợp của bạn, cho mình hỏi thêm:"
        proc_chunks = [c for c in chunks if c.procedure_id == top_id]
        return {
            "selected_procedure_id": top_id,
            "identify_confidence": round(confidence, 4),
            "candidate_procedures": candidates,
            "pending_questions": questions,
            "pending_action": "answer_clarification" if questions else None,
            "pending_procedure_ids": [],
            "pending_question_keys": [
                question.key for question in procedure.clarifying_questions
            ],
            "reply": reply,
            "reply_kind": "clarify",
            "citations": [c.model_dump() for c in citations_from_chunks(proc_chunks)],
            "retrieved_chunks": retrieved,
        }

    # Chưa đủ tin cậy → liệt kê ứng viên cho người dân chọn
    lines = ["Mình tìm thấy vài thủ tục có thể phù hợp, bạn xác nhận giúp nhé:"]
    for index, (procedure_id, _) in enumerate(ranked[:3], start=1):
        procedure = catalog.get_procedure(procedure_id)
        if procedure:
            lines.append(f"{index}. {procedure.name} — {procedure.agency}")
        else:
            raw_document = get_raw_document(procedure_id)
            if raw_document:
                lines.append(f"{index}. {raw_document.procedure_name} — nguồn chính thức, chờ duyệt workflow")
    lines.append("Bạn đang cần làm thủ tục nào trong số trên?")
    return {
        "identify_confidence": round(confidence, 4),
        "candidate_procedures": candidates,
        "pending_questions": ["Bạn đang cần làm thủ tục nào trong số trên?"],
        "pending_action": "select_procedure",
        "pending_procedure_ids": [procedure_id for procedure_id, _ in ranked[:3]],
        "pending_question_keys": [],
        "reply": "\n".join(lines),
        "reply_kind": "clarify",
        "citations": [c.model_dump() for c in citations_from_chunks(chunks)],
        "retrieved_chunks": retrieved,
    }


def _procedure_intro(procedure: Any) -> str:
    lines = [f"Bạn cần làm thủ tục: {procedure.name}"]
    if procedure.national_code:
        lines[0] += f" (mã {procedure.national_code})"
    lines.append(f"- Cơ quan thực hiện: {procedure.agency}")
    if procedure.processing_days is not None:
        lines.append(f"- Thời hạn xử lý: {procedure.processing_days} ngày làm việc")
    if procedure.fee_vnd is not None:
        fee = "miễn phí" if procedure.fee_vnd == 0 else f"{procedure.fee_vnd:,}đ"
        lines.append(f"- Lệ phí: {fee}")
    if procedure.legal_basis:
        lines.append(f"- Căn cứ pháp lý: {'; '.join(procedure.legal_basis)}")
    return "\n".join(lines)
