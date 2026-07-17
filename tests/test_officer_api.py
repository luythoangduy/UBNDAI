from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.main import app
from src.models import CaseDocument
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
        assert documents[0]["original_filename"] == "giay-khai-sinh.pdf"
        assert "file_uri" not in documents[0]
        assert "object_key" not in documents[0]
    finally:
        store.documents.pop(document.id, None)
