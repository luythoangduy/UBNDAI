from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.main import app
from src.models import CaseDocument, ExtractedFieldRecord
from src.services.officer_store import store


client = TestClient(app)


def login(username: str = "officer.demo", password: str = "ChangeMe123!") -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


def test_login_and_queue_are_scoped_to_officer_role():
    token = login()
    response = client.get("/api/v1/officer/cases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]


def test_unauthenticated_officer_route_is_rejected():
    response = client.get("/api/v1/officer/cases")
    assert response.status_code == 401


def test_claim_and_finding_decision_are_audited():
    token = login()
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/officer/cases", headers=headers).json()["data"]
    case_id = cases[0]["id"]
    claim = client.post(f"/api/v1/officer/cases/{case_id}/claim", headers=headers)
    assert claim.status_code in (200, 409)
    if claim.status_code == 200:
        assert claim.json()["data"]["citizen_id"] == "***"
        assert "form_data" not in claim.json()["data"]
    detail = client.get(f"/api/v1/officer/cases/{case_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["timeline"]


def test_cross_organization_case_is_not_visible():
    token = login("officer.other", "ChangeMe123!")
    response = client.get("/api/v1/officer/cases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert all(item["organization_id"] == "org-other" for item in response.json()["data"])
    assert not any(item["id"] == "case-demo-001" for item in response.json()["data"])


def test_blocking_finding_prevents_ready_and_supplement_moves_case_to_update():
    token = login()
    headers = {"Authorization": f"Bearer {token}"}
    blocked = client.post("/api/v1/officer/cases/case-demo-001/transition", headers=headers, json={"target_status": "precheck_ready"})
    assert blocked.status_code == 422
    accepted = client.post("/api/v1/officer/findings/finding-demo-001/accept", headers=headers)
    assert accepted.status_code == 200
    still_blocked = client.post("/api/v1/officer/cases/case-demo-001/transition", headers=headers, json={"target_status": "precheck_ready"})
    assert still_blocked.status_code == 422
    request = client.post("/api/v1/officer/cases/case-demo-001/supplement-requests", headers=headers, json={"public_message": "Vui lòng bổ sung giấy tờ.", "finding_ids": ["finding-demo-001"]})
    assert request.status_code == 200
    assert request.json()["data"]["status"] == "sent"


def test_dashboard_returns_server_side_summary():
    token = login()
    response = client.get("/api/v1/officer/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["data"]["total"] >= 1
    assert "document_total" in response.json()["data"]
    assert "document_ready" in response.json()["data"]
    assert "document_manual_review" in response.json()["data"]


def test_officer_detail_contains_authorized_case_documents():
    document = CaseDocument(
        id="document-officer-workspace",
        case_id="case-demo-001",
        submission_version_id="submission-demo-001",
        document_type="birth_certificate",
        file_uri="private://case-demo-001/document-officer-workspace",
        original_filename="giay-khai-sinh.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        ocr_status="ready",
        uploaded_at=datetime.now(timezone.utc),
    )
    store.documents[document.id] = document
    try:
        token = login()
        response = client.get(
            "/api/v1/officer/cases/case-demo-001",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        documents = response.json()["data"]["documents"]
        uploaded = next(item for item in documents if item["id"] == document.id)
        assert uploaded["original_filename"] == "giay-khai-sinh.pdf"
        assert "file_uri" not in uploaded
        assert "object_key" not in uploaded
    finally:
        store.documents.pop(document.id, None)


def test_queue_supports_search_status_and_sort_parameters():
    token = login()
    response = client.get(
        "/api/v1/officer/cases?q=UBNDAI-2026-000001&status=awaiting_officer_review&sort=newest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["pagination"]["page_size"] == 20
    assert all(item["id"] == "case-demo-001" for item in response.json()["data"])


def test_officer_can_read_and_edit_extracted_field_then_rerun_validation():
    document = CaseDocument(
        id="document-field-review",
        case_id="case-demo-001",
        submission_version_id="submission-demo-001",
        document_type="giay_chung_sinh",
        file_uri="private://case-demo-001/document-field-review",
        original_filename="giay-chung-sinh.png",
        content_type="image/png",
        size_bytes=1024,
        ocr_status="manual_review_required",
        uploaded_at=datetime.now(timezone.utc),
    )
    field = ExtractedFieldRecord(
        id="field-review-name",
        document_id=document.id,
        field_key="ho_ten_con",
        raw_value="Nguyen An",
        normalized_value="Nguyen An",
        confidence=0.62,
        page=1,
        review_status="needs_human_review",
    )
    store.documents[document.id] = document
    store.extracted_fields[field.id] = field
    try:
        token = login()
        headers = {"Authorization": f"Bearer {token}"}
        listed = client.get(f"/api/v1/officer/documents/{document.id}/fields", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["data"][0]["review_status"] == "needs_human_review"

        edited = client.patch(
            f"/api/v1/officer/extracted-fields/{field.id}",
            headers=headers,
            json={"normalized_value": "Nguyễn An", "reason": "Đối chiếu bản gốc"},
        )
        assert edited.status_code == 200
        assert edited.json()["data"]["previous_value"] == "Nguyen An"
        assert edited.json()["data"]["review_status"] == "edited"

        rerun = client.post("/api/v1/officer/cases/case-demo-001/rerun-validation", headers=headers)
        assert rerun.status_code == 200
        assert all(
            item["type"] != "ocr_human_review" or field.field_key not in item["field_keys"]
            for item in rerun.json()["data"]
        )
        assert any(event.event_type == "ocr_field_edited" for event in store.audit)
    finally:
        store.documents.pop(document.id, None)
        store.extracted_fields.pop(field.id, None)
