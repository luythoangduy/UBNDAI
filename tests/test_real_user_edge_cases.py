"""Kịch bản người dùng thật với input oái oăm — grounding không được đoán bừa.

Nhóm 1: chat/routing với câu hỏi lệch chuẩn (không dấu, dân dã, nhiều ý, nhảm).
Nhóm 2: rule engine với dữ liệu bẩn (khoảng trắng lộn xộn, ngày không tồn tại).
Nhóm 3: API/store với thao tác trái luồng (version cũ, giấy tờ không khớp thủ tục).
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from src.agents.graph import run_guidance
from src.agents.nodes import identify, planner
from src.main import app
from src.models import Case, ChatRequest, ChecklistItem, ExtractedDocument, ExtractedField
from src.services.officer_store import OfficerStore
from src.services.validation import rule_engine

client = TestClient(app)


def _auth(username: str = "citizen.demo") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "ChangeMe123!"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


# --- Nhóm 1: chat với câu hỏi lệch chuẩn ---


@pytest.mark.asyncio
async def test_query_without_diacritics_still_finds_procedure():
    result = await identify.run({"rewritten_query": "toi muon lam giay khai sinh cho con"})
    assert result.get("selected_procedure_id") == "khai_sinh"


@pytest.mark.asyncio
async def test_colloquial_birth_story_does_not_guess_wrong_procedure():
    # "vợ tôi mới đẻ" không chứa cụm "khai sinh" — hệ thống được phép hỏi lại,
    # nhưng tuyệt đối không được gán bừa sang thủ tục khác (kết hôn, tạm trú...).
    result = await identify.run(
        {"rewritten_query": "vợ tôi mới đẻ xong, giờ cần làm giấy tờ gì cho cháu"}
    )
    assert result.get("selected_procedure_id") in (None, "khai_sinh")


@pytest.mark.asyncio
async def test_two_procedures_in_one_message_asks_instead_of_merging():
    # Hỏi 2 thủ tục cùng lúc: chọn một trong hai hoặc đưa danh sách cho người
    # dùng chọn — không được im lặng trộn checklist của cả hai.
    result = await identify.run(
        {"rewritten_query": "tôi muốn đăng ký khai sinh và đăng ký tạm trú cho con"}
    )
    selected = result.get("selected_procedure_id")
    assert selected in (None, "khai_sinh", "tam_tru")
    if selected is None:
        assert result.get("pending_action") == "select_procedure" or result[
            "reply_kind"
        ] in ("clarify", "fallback", "answer")


@pytest.mark.asyncio
async def test_emoji_gibberish_gets_graceful_fallback():
    result = await identify.run({"rewritten_query": "😅😅😅 alo alo ơ kìa"})
    assert result.get("selected_procedure_id") is None


@pytest.mark.asyncio
async def test_out_of_range_candidate_number_does_not_crash_planner():
    # Hệ thống đưa 1 lựa chọn, người dùng trả lời "số 5".
    result = await planner.run(
        {
            "messages": [HumanMessage(content="số 5")],
            "answers": {},
            "selected_procedure_id": None,
            "pending_action": "select_procedure",
            "pending_procedure_ids": ["khai_sinh"],
        }
    )
    assert result.get("selected_procedure_id") != "khai_sinh"


@pytest.mark.asyncio
async def test_full_guidance_turn_with_messy_message_returns_reply():
    response = await run_guidance(
        ChatRequest(message="  ĐĂNG KÝ khai   sinh cho CON tôi gấp!!! 😀  ")
    )
    assert response.reply
    assert response.case_id


# --- Nhóm 2: rule engine với dữ liệu bẩn ---


def _case_with(form_data: dict, procedure_id: str, answers: dict | None = None) -> Case:
    timestamp = datetime.now(UTC)
    return Case(
        id="edge-case",
        citizen_id="c1",
        procedure_id=procedure_id,
        answers=answers or {},
        checklist=[ChecklistItem(requirement_code="x", status="missing")],
        form_data=form_data,
        status="collecting",
        created_at=timestamp,
        updated_at=timestamp,
    )


def _document(doc_type: str, fields: dict[str, str]) -> ExtractedDocument:
    return ExtractedDocument(
        id="doc-1",
        case_id="edge-case",
        file_id="file-1",
        doc_type=doc_type,
        doc_type_confidence=0.99,
        ocr_engine="test",
        fields=[
            ExtractedField(key=key, value=value, confidence=0.99)
            for key, value in fields.items()
        ],
        needs_human_review=False,
        created_at=datetime.now(UTC),
    )


def test_name_match_tolerates_messy_whitespace_and_case():
    case = _case_with({}, "khai_sinh", answers={"sinh_tai_co_so_y_te": True})
    documents = [
        _document("giay_chung_sinh", {"ho_ten_me": "nguyễn   thị  ÁNH tuyết", "ngay_sinh": "01/01/2026"}),
        _document("cccd", {"ho_ten": "Nguyễn Thị Ánh Tuyết"}),
    ]
    report = rule_engine.run(case, documents)
    assert not any(issue.rule_id == "KS-R2" for issue in report.issues)


def test_nonexistent_calendar_date_fails_conservatively():
    # 30/02 không tồn tại — hệ thống phải báo "chưa xác minh được" (issue),
    # không được im lặng cho qua.
    case = _case_with({}, "khai_sinh", answers={"sinh_tai_co_so_y_te": True})
    documents = [
        _document("giay_chung_sinh", {"ho_ten_me": "A", "ngay_sinh": "30/02/2026"}),
    ]
    report = rule_engine.run(case, documents)
    assert any(issue.rule_id == "KS-R3" for issue in report.issues)


def test_marriage_form_with_only_one_side_filled_raises_errors():
    case = _case_with(
        {"ho_ten_nam": "Trần Văn B", "so_dinh_danh_nam": "0123456789"}, "ket_hon"
    )
    report = rule_engine.run(case, [])
    triggered = {issue.rule_id for issue in report.issues}
    assert {"KH-R1", "KH-R2"} <= triggered


def test_minor_tam_tru_without_guardian_consent_warns():
    case = _case_with(
        {"ho_ten": "Bé C", "so_dinh_danh": "0987654321", "dia_chi_tam_tru": "Số 1 phố X"},
        "tam_tru",
        answers={"nguoi_chua_thanh_nien": True},
    )
    report = rule_engine.run(case, [])
    warning = next(
        (issue for issue in report.issues if issue.rule_id == "TT-R4"), None
    )
    assert warning is not None
    assert warning.severity == "warning"


def test_online_can_cuoc_without_personal_id_warns():
    case = _case_with(
        {"ho_ten": "D", "ngay_sinh": "01/01/2010", "noi_cu_tru": "Phường Y"},
        "can_cuoc",
        answers={"nop_truc_tuyen": True},
    )
    report = rule_engine.run(case, [])
    assert any(issue.rule_id == "CC-R3" for issue in report.issues)


# --- Nhóm 3: API/store với thao tác trái luồng ---


def test_stale_version_update_is_rejected_with_conflict():
    headers = _auth()
    case = client.post(
        "/api/v1/citizen/cases",
        headers=headers,
        json={"procedure_id": "khai_sinh", "locality_code": "00001"},
    ).json()["data"]
    stale = client.patch(
        f"/api/v1/citizen/cases/{case['id']}",
        headers=headers,
        json={"expected_version": case["version"] + 41, "form_data": {"ho_ten_con": "A"}},
    )
    assert stale.status_code == 409
    assert "version_conflict" in stale.text


def test_vietnamese_names_with_emoji_roundtrip_intact():
    headers = _auth()
    case = client.post(
        "/api/v1/citizen/cases",
        headers=headers,
        json={"procedure_id": "khai_sinh", "locality_code": "00001"},
    ).json()["data"]
    tricky_name = "Nguyễn Thị Ánh Tuyết 🌸 (bé Bống)"
    updated = client.patch(
        f"/api/v1/citizen/cases/{case['id']}",
        headers=headers,
        json={"expected_version": case["version"], "form_data": {"ho_ten_con": tricky_name}},
    )
    assert updated.status_code == 200, updated.text
    fetched = client.get(f"/api/v1/citizen/cases/{case['id']}", headers=headers)
    assert fetched.json()["data"]["case"]["form_data"]["ho_ten_con"] == tricky_name


def test_document_not_matching_any_requirement_leaves_checklist_untouched():
    # Người dùng upload CCCD vào hồ sơ giấy phép xây dựng — thủ tục này không
    # có requirement nào nhận doc_type 'cccd' nên checklist phải giữ nguyên.
    store = OfficerStore(seed=False)
    case = store.create_citizen_case("citizen-demo", "giay_phep_xay_dung", "00001")
    before = dict(case.checklist)
    document = store.create_document(case.id, "citizen-demo", "cccd.png", "image/png", 1000)
    store.complete_document(document.id, "citizen-demo", "a" * 64, "cccd", False)
    after = store.get_citizen_case(case.id, "citizen-demo").checklist
    assert after == before
    assert all(status == "missing" for status in after.values())


def test_document_matching_one_requirement_ticks_only_that_item():
    store = OfficerStore(seed=False)
    case = store.create_citizen_case("citizen-demo", "khai_sinh", "00001")
    document = store.create_document(case.id, "citizen-demo", "cccd.png", "image/png", 1000)
    store.complete_document(document.id, "citizen-demo", "b" * 64, "cccd", False)
    checklist = store.get_citizen_case(case.id, "citizen-demo").checklist
    assert checklist["cccd_cha_me"] == "uploaded"
    assert checklist["giay_chung_sinh"] == "missing"
    assert checklist["to_khai_khai_sinh"] == "missing"
