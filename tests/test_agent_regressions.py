"""Regression tests cho routing, grounding và concurrent case turns."""

import asyncio

import pytest

from src.agents.graph import run_guidance
from src.agents.nodes import answer, identify
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
    monkeypatch.setattr(identify, "retrieve", lambda query: [weak])
    result = await identify.run({"rewritten_query": "mơ hồ"})
    assert "selected_procedure_id" not in result


@pytest.mark.asyncio
async def test_chunk_without_procedure_id_does_not_crash_identify(monkeypatch):
    monkeypatch.setattr(
        identify,
        "retrieve",
        lambda query: [RetrievedChunk(content="x", metadata={}, score=1.0)],
    )
    result = await identify.run({"rewritten_query": "x"})
    assert result["reply_kind"] == "fallback"


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
