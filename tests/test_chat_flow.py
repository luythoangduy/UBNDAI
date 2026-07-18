"""Luồng chat end-to-end qua API (LLM tắt → rule fallback, BM25 in-memory).

identify → clarify → checklist → answer, mọi reply về thủ tục đều kèm citation.
"""

import pytest
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
    assert "Tờ khai" in second["reply"]
    assert "Giấy chứng sinh" not in second["reply"]
    assert second["clarifying_questions"]
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


@pytest.mark.parametrize(
    ("message", "procedure_id", "procedure_name"),
    [
        ("tôi muốn đăng ký kết hôn", "ket_hon", "Đăng ký kết hôn"),
        ("tôi cần đăng ký tạm trú", "tam_tru", "Đăng ký tạm trú"),
        ("tôi muốn làm căn cước công dân", "can_cuoc", "Cấp thẻ căn cước"),
    ],
)
def test_common_procedures_are_not_routed_to_fallback(
    message, procedure_id, procedure_name
):
    result = _post({"message": message})

    assert result["kind"] != "fallback"
    assert result["procedure_id"] == procedure_id
    assert procedure_name in result["reply"]
    assert result["citations"]
    assert result["citations"][0]["procedure_id"] == procedure_id


def test_unlisted_procedure_continues_to_open_legal_rag(monkeypatch):
    from src.agents.nodes import answer
    from src.services.retrieval.common import RetrievedChunk

    monkeypatch.setattr(
        answer,
        "retrieve_legal",
        lambda query: [
            RetrievedChunk(
                content="Quy định về điều kiện kinh doanh dịch vụ karaoke.",
                metadata={
                    "procedure_id": "legal:karaoke",
                    "procedure_name": "Văn bản về dịch vụ karaoke",
                    "chunk_id": "legal:karaoke::1",
                    "section": "điều kiện",
                    "source_type": "legal_corpus",
                    "source_url": "https://vbpl.vn/example",
                },
                score=1.0,
            )
        ],
    )

    result = _post({"message": "tôi muốn xin giấy phép hoạt động karaoke"})

    assert result["kind"] == "answer"
    assert result["procedure_id"] is None
    assert result["citations"][0]["procedure_id"] == "legal:karaoke"


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


def test_authenticated_chat_case_is_available_in_citizen_portal():
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "citizen.demo", "password": "ChangeMe123!"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    chat = client.post(
        "/api/v1/chat",
        json={"message": "tôi muốn đăng ký khai sinh cho con"},
        headers=headers,
    )
    assert chat.status_code == 200

    portal = client.get(
        f"/api/v1/citizen/cases/{chat.json()['case_id']}",
        headers=headers,
    )
    assert portal.status_code == 200
    case = portal.json()["data"]["case"]
    assert case["procedure_id"] == "khai_sinh"
    assert case["source_channel"] == "ai_guidance"


def test_clarification_answer_is_extracted_and_persisted():
    from src.services import cases as cases_service
    import asyncio

    first = _post({"message": "Tôi muốn đăng ký khai sinh cho con"})
    _post({"case_id": first["case_id"], "message": "có"})
    _post({"case_id": first["case_id"], "message": "có"})
    second = _post({"case_id": first["case_id"], "message": "5"})

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
        {"case_id": first["case_id"], "message": "có"}
    )

    assert second["kind"] == "clarify"
    assert second["primary_intent"] == "clarification_answer"
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


def test_user_can_correct_previous_answer_and_regenerate_checklist():
    from src.services import cases as cases_service
    import asyncio

    first = _post({"message": "đăng ký khai sinh cho con"})
    _post({"case_id": first["case_id"], "message": "có"})
    _post({"case_id": first["case_id"], "message": "có"})
    _post({"case_id": first["case_id"], "message": "5"})
    corrected = _post(
        {
            "case_id": first["case_id"],
            "message": "thực ra: không",
        }
    )
    case = asyncio.run(cases_service.get(first["case_id"]))
    assert case.answers["ket_hon"] is False
    assert corrected["kind"] == "checklist"
    marriage_item = next(
        item for item in case.checklist if item.requirement_code == "giay_dang_ky_ket_hon"
    )
    assert marriage_item.status == "not_applicable"


def test_user_can_switch_away_from_selected_procedure():
    from src.services import cases as cases_service
    import asyncio

    first = _post({"message": "đăng ký khai sinh cho con"})
    switched = _post(
        {
            "case_id": first["case_id"],
            "message": "Tôi muốn đổi sang đăng ký kết hôn",
        }
    )
    case = asyncio.run(cases_service.get(first["case_id"]))
    assert switched["kind"] != "fallback"
    assert switched["procedure_id"] == "ket_hon"
    assert case.procedure_id == "ket_hon"
    assert case.answers == {}
    assert "đăng ký kết hôn" in switched["reply"].casefold()


def test_mixed_checklist_persists_and_returns_pending_questions():
    from src.services import cases as cases_service
    import asyncio

    first = _post({"message": "đăng ký khai sinh cho con"})
    mixed = _post(
        {
            "case_id": first["case_id"],
            "message": "Lệ phí bao nhiêu và cần giấy tờ gì?",
        }
    )
    case = asyncio.run(cases_service.get(first["case_id"]))
    assert mixed["kind"] == "answer"
    assert mixed["clarifying_questions"]
    assert case.checklist
    assert case.status == "collecting"
    assert "Giấy chứng sinh" not in mixed["reply"]
    assert "Văn bản xác nhận" not in mixed["reply"]
