"""Regression tests cho routing, grounding và concurrent case turns."""

import asyncio

import pytest
from langchain_core.messages import HumanMessage

from src.agents.graph import run_guidance
from src.agents.nodes import answer, identify, planner
from src.agents.nodes.planner import PlannerDecision
from src.models import ChatRequest
from src.services import cases
from src.services.retrieval.common import RetrievedChunk


@pytest.mark.asyncio
async def test_answer_retrieval_is_scoped_to_selected_procedure(monkeypatch):
    calls = []

    def fake_retrieve(query, *, procedure_id=None, top_k=None):
        calls.append(procedure_id)
        return [
            RetrievedChunk(
                content="Lệ phí: miễn phí",
                metadata={
                    "procedure_id": "khai_sinh",
                    "procedure_name": "Đăng ký khai sinh",
                    "chunk_id": "khai_sinh::tong_quan",
                    "section": "tong_quan",
                },
                score=1.0,
            )
        ]

    monkeypatch.setattr(answer, "retrieve", fake_retrieve)
    result = await answer.run(
        {
            "selected_procedure_id": "khai_sinh",
            "rewritten_query": "lệ phí bao nhiêu?",
        }
    )
    assert calls == ["khai_sinh"]
    assert {item["procedure_id"] for item in result["citations"]} == {"khai_sinh"}


@pytest.mark.asyncio
async def test_mixed_clarification_and_agency_question_returns_agency_answer():
    result = await answer.run(
        {
            "selected_procedure_id": "khai_sinh",
            "rewritten_query": "Bé sinh ở bệnh viện, nộp ở đâu?",
        }
    )
    assert result["reply_kind"] == "answer"
    assert "UBND cấp xã" in result["reply"]


@pytest.mark.asyncio
async def test_weak_single_retrieval_result_is_not_auto_selected(monkeypatch):
    weak = RetrievedChunk(
        content="Thủ tục: Đăng ký khai sinh",
        metadata={
            "procedure_id": "khai_sinh",
            "procedure_name": "Đăng ký khai sinh",
            "chunk_id": "khai_sinh::tong_quan",
            "section": "tong_quan",
        },
        score=0.001,
    )
    monkeypatch.setattr(identify, "retrieve_procedure_identity", lambda query: [weak])
    result = await identify.run({"rewritten_query": "mơ hồ"})
    assert "selected_procedure_id" not in result


@pytest.mark.asyncio
async def test_chunk_without_procedure_id_does_not_crash_identify(monkeypatch):
    monkeypatch.setattr(
        identify,
        "retrieve_procedure_identity",
        lambda query: [RetrievedChunk(content="x", metadata={}, score=1.0)],
    )
    result = await identify.run({"rewritten_query": "x"})
    assert result["reply_kind"] == "fallback"


@pytest.mark.parametrize(
    "query",
    [
        "đăng ký kết hôn",
        "làm căn cước công dân",
        "xin giấy phép xây dựng",
        "thủ tục đất đai",
    ],
)
@pytest.mark.asyncio
async def test_unrelated_query_does_not_select_birth_registration(query):
    result = await identify.run({"rewritten_query": query})
    assert result.get("selected_procedure_id") is None
    assert result["reply_kind"] == "fallback"


@pytest.mark.asyncio
async def test_student_query_does_not_select_birth_registration():
    for query in (
        "tôi là sinh viên cần giấy xác nhận",
        "xin xác nhận sinh viên",
    ):
        result = await identify.run({"rewritten_query": query})
        assert result.get("selected_procedure_id") is None
        assert result["reply_kind"] == "fallback"


@pytest.mark.asyncio
async def test_negative_context_does_not_block_explicit_positive_procedure():
    result = await identify.run(
        {
            "rewritten_query": (
                "không phải đăng ký kết hôn, tôi muốn đăng ký khai sinh cho con"
            )
        }
    )
    assert result["selected_procedure_id"] == "khai_sinh"


@pytest.mark.asyncio
async def test_planner_forces_identify_when_llm_returns_clarify_without_procedure(
    monkeypatch,
):
    async def wrong_llm_route(*args, **kwargs):
        return PlannerDecision(route="clarify", rewritten_query="đăng ký khai sinh")

    monkeypatch.setattr(planner, "_llm_decision", wrong_llm_route)
    result = await planner.run(
        {
            "messages": [HumanMessage(content="Tôi muốn đăng ký khai sinh cho con")],
            "answers": {},
            "selected_procedure_id": None,
        }
    )
    assert result["route"] == "identify"


@pytest.mark.parametrize(
    ("message", "expected_route"),
    [
        ("Bé sinh được 5 ngày, lệ phí bao nhiêu?", "answer"),
        ("Bé sinh ở bệnh viện, nộp ở đâu?", "answer"),
    ],
)
@pytest.mark.asyncio
async def test_extracted_answer_does_not_override_explicit_intent(
    message, expected_route
):
    result = await planner.run(
        {
            "messages": [HumanMessage(content=message)],
            "answers": {"ket_hon": True},
            "selected_procedure_id": "khai_sinh",
        }
    )
    assert result["route"] == expected_route
    assert result["answers"]


@pytest.mark.asyncio
async def test_pending_candidate_can_be_selected_by_number():
    result = await planner.run(
        {
            "messages": [HumanMessage(content="số 1")],
            "answers": {},
            "selected_procedure_id": None,
            "pending_action": "select_procedure",
            "pending_procedure_ids": ["khai_sinh"],
        }
    )
    assert result["selected_procedure_id"] == "khai_sinh"
    assert result["route"] == "clarify"


@pytest.mark.asyncio
async def test_switch_with_uploaded_document_requires_confirmation():
    result = await planner.run(
        {
            "messages": [HumanMessage(content="đổi sang đăng ký kết hôn")],
            "answers": {"ket_hon": True},
            "selected_procedure_id": "khai_sinh",
            "checklist": [
                {
                    "requirement_code": "cccd_cha_me",
                    "status": "uploaded",
                    "document_id": "doc-1",
                }
            ],
        }
    )
    assert result["route"] == "clarify"
    assert result["pending_action"] == "confirm_switch_procedure"
    assert result.get("reset_procedure") is not True


@pytest.mark.asyncio
async def test_invalid_llm_citation_index_falls_back(monkeypatch):
    class Response:
        content = "Thông tin không hợp lệ [9]."

    class FakeLlm:
        async def ainvoke(self, messages):
            return Response()

    chunk = RetrievedChunk(
        content="nguồn",
        metadata={"procedure_id": "p", "chunk_id": "p::x", "section": "x"},
    )
    monkeypatch.setattr(answer, "llm_is_configured", lambda: True)
    monkeypatch.setattr(answer, "get_llm", lambda: FakeLlm())
    assert await answer._llm_answer("hỏi", [chunk]) is None


@pytest.mark.asyncio
async def test_concurrent_messages_do_not_overwrite_case_answers():
    first = await run_guidance(ChatRequest(message="đăng ký khai sinh cho con"))
    await asyncio.gather(
        run_guidance(ChatRequest(case_id=first.case_id, message="đã kết hôn")),
        run_guidance(ChatRequest(case_id=first.case_id, message="bé sinh ở bệnh viện")),
    )
    case = await cases.get(first.case_id)
    assert case.answers["ket_hon"] is True
    assert case.answers["sinh_tai_co_so_y_te"] is True
