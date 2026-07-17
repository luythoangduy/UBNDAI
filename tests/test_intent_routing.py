"""Ma trận intent: nghiệp vụ, mixed intent và các use case ngoài lề."""

import pytest
from langchain_core.messages import HumanMessage

from src.agents.nodes import answer, planner
from src.agents.nodes.planner import PlannerDecision
from src.services.intent import detect_intents


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("xin chào", "greeting"),
        ("cảm ơn bạn", "thanks"),
        ("bạn làm được gì", "capabilities"),
        ("hồ sơ của tôi đến đâu rồi", "status_tracking"),
        ("tôi muốn upload giấy tờ", "document_upload"),
        ("dự báo thời tiết ngày mai", "out_of_scope"),
        ("đăng ký kết hôn", "procedure_discovery"),
    ],
)
def test_primary_intent_matrix(message, expected):
    result = detect_intents(message, has_selected_procedure=False)
    assert result.primary == expected


def test_detects_multiple_information_intents():
    result = detect_intents(
        "Lệ phí bao nhiêu, mất mấy ngày và nộp ở đâu?",
        has_selected_procedure=True,
    )
    assert {"fee", "processing_time", "agency"} <= set(result.intents)


def test_negated_intent_is_not_included():
    result = detect_intents(
        "Không hỏi lệ phí, tôi chỉ muốn biết mất mấy ngày",
        has_selected_procedure=True,
    )
    assert "fee" not in result.intents
    assert "processing_time" in result.intents


@pytest.mark.asyncio
async def test_fee_without_procedure_asks_which_procedure():
    result = await planner.run(
        {
            "messages": [HumanMessage(content="Lệ phí bao nhiêu?")],
            "answers": {},
            "selected_procedure_id": None,
        }
    )
    assert result["route"] == "clarify"
    assert result["primary_intent"] == "fee"


@pytest.mark.asyncio
async def test_social_and_out_of_scope_bypass_procedure_rag():
    greeting = await answer.run(
        {
            "rewritten_query": "xin chào",
            "selected_procedure_id": "khai_sinh",
            "detected_intents": ["greeting"],
        }
    )
    outside = await answer.run(
        {
            "rewritten_query": "dự báo thời tiết",
            "selected_procedure_id": "khai_sinh",
            "detected_intents": ["out_of_scope"],
        }
    )
    assert greeting["reply_kind"] == "answer"
    assert greeting["citations"] == []
    assert outside["reply_kind"] == "fallback"
    assert outside["citations"] == []


@pytest.mark.asyncio
async def test_mixed_fee_time_agency_and_checklist_are_answered_together():
    state = {
        "rewritten_query": (
            "Lệ phí bao nhiêu, mất mấy ngày, nộp ở đâu và cần giấy tờ gì?"
        ),
        "selected_procedure_id": "khai_sinh",
        "answers": {"ket_hon": True, "sinh_tai_co_so_y_te": True},
        "detected_intents": [
            "fee",
            "processing_time",
            "agency",
            "checklist",
        ],
    }
    result = await answer.run(state)
    assert result["reply_kind"] == "answer"
    assert "Lệ phí" in result["reply"]
    assert "Thời hạn" in result["reply"]
    assert "UBND cấp xã" in result["reply"]
    assert "Checklist" in result["reply"]
    assert result["citations"]


@pytest.mark.asyncio
async def test_llm_intent_supplements_unknown_deterministic_wording(monkeypatch):
    async def semantic_decision(*args, **kwargs):
        return PlannerDecision(
            route="answer",
            rewritten_query="lệ phí đăng ký khai sinh",
            primary_intent="fee",
            detected_intents=["fee"],
        )

    monkeypatch.setattr(planner, "llm_is_configured", lambda: True)
    monkeypatch.setattr(planner, "_llm_decision", semantic_decision)
    result = await planner.run(
        {
            "messages": [
                HumanMessage(
                    content="Bé sinh được 5 ngày, khoản phải đóng thế nào?"
                )
            ],
            "answers": {"ket_hon": True, "sinh_tai_co_so_y_te": True},
            "selected_procedure_id": "khai_sinh",
        }
    )
    assert result["route"] == "answer"
    assert result["primary_intent"] == "fee"
    assert result["answers"]["so_ngay_tu_khi_sinh"] == 5
