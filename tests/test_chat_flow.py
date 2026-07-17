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
    assert first["primary_intent"] == "procedure_discovery"
    assert "procedure_discovery" in first["detected_intents"]
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
    assert "chưa hiểu rõ yêu cầu" in result["reply"].casefold()


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


def test_clarification_answer_is_extracted_and_persisted():
    from src.services import cases as cases_service
    import asyncio

    first = _post({"message": "Tôi muốn đăng ký khai sinh cho con"})
    second = _post(
        {
            "case_id": first["case_id"],
            "message": (
                "Cha mẹ đã kết hôn, bé sinh ở bệnh viện, "
                "bé sinh được 5 ngày"
            ),
        }
    )

    assert second["kind"] == "checklist"
    case = asyncio.run(cases_service.get(first["case_id"]))
    assert case.answers == {
        "ket_hon": True,
        "sinh_tai_co_so_y_te": True,
        "so_ngay_tu_khi_sinh": 5,
    }


def test_only_unanswered_questions_are_returned():
    first = _post({"message": "Tôi muốn đăng ký khai sinh cho con"})
    second = _post(
        {"case_id": first["case_id"], "message": "Cha mẹ đã kết hôn"}
    )

    assert second["kind"] == "clarify"
    assert "kết hôn" not in " ".join(second["clarifying_questions"]).casefold()
    assert len(second["clarifying_questions"]) == 2


def test_empty_message_rejected():
    response = client.post("/api/v1/chat", json={"message": "   "})
    assert response.status_code == 422


def test_concurrent_case_conflict_returns_409(monkeypatch):
    from src.api.v1 import chat as chat_module
    from src.services.cases import ConcurrentCaseUpdateError

    async def conflict(payload):
        raise ConcurrentCaseUpdateError("case-conflict")

    monkeypatch.setattr(chat_module, "run_guidance", conflict)
    response = client.post("/api/v1/chat", json={"message": "xin chào"})
    assert response.status_code == 409
