"""Luồng chat end-to-end qua API (LLM tắt → rule fallback, BM25 in-memory).

identify → clarify → checklist → answer, mọi reply về thủ tục đều kèm citation.
"""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def _post(payload: dict) -> dict:
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_full_guidance_flow_with_citations():
    # Lượt 1: nhận diện thủ tục → giới thiệu + câu hỏi làm rõ, có citation
    first = _post({"message": "tôi muốn đăng ký khai sinh cho con mới sinh"})
    assert first["case_id"]
    assert first["kind"] == "clarify"
    assert "Đăng ký khai sinh" in first["reply"]
    assert first["clarifying_questions"], "phải kèm câu hỏi làm rõ từ catalog"
    assert first["citations"] and first["citations"][0]["procedure_id"] == "khai_sinh"

    case_id = first["case_id"]

    # Lượt 2: hỏi giấy tờ → checklist sinh từ catalog, trace được nguồn
    second = _post({"case_id": case_id, "message": "cần chuẩn bị giấy tờ gì?"})
    assert second["kind"] == "checklist"
    assert "Giấy chứng sinh" in second["reply"]
    assert "Tờ khai" in second["reply"]
    citation = second["citations"][0]
    assert citation["procedure_id"] == "khai_sinh"
    assert citation["source_url"].startswith("https://")

    # Lượt 3: hỏi đáp chung → answer kèm citation (LLM tắt → extractive fallback)
    third = _post({"case_id": case_id, "message": "lệ phí bao nhiêu tiền?"})
    assert third["kind"] == "answer"
    assert third["citations"], "câu trả lời về thủ tục phải kèm nguồn (AGENTS.md §5)"


def test_gibberish_returns_grounding_fallback():
    result = _post({"message": "xyzt qwerty lorem ipsum"})
    assert result["kind"] == "fallback"
    assert result["citations"] == []
    assert "Chưa đủ căn cứ" in result["reply"]


def test_unknown_case_id_returns_404():
    response = client.post(
        "/api/v1/chat", json={"case_id": "khong-ton-tai", "message": "hello"}
    )
    assert response.status_code == 404


def test_case_persists_procedure_and_status_after_checklist():
    from src.services import cases as cases_service
    import asyncio

    first = _post({"message": "đăng ký khai sinh cho bé"})
    case_id = first["case_id"]
    _post({"case_id": case_id, "message": "hồ sơ gồm những gì?"})

    case = asyncio.run(cases_service.get(case_id))
    assert case.procedure_id == "khai_sinh"
    assert case.status == "collecting"
    assert case.checklist, "checklist phải được persist về Case"
