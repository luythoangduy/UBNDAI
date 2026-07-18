from fastapi.testclient import TestClient

from src.config import settings
from src.main import app


client = TestClient(app)


def _token(username: str = "officer.demo") -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": settings.demo_password})
    return response.json()["data"]["access_token"]


def test_application_list_requires_authentication():
    assert client.get("/api/v1/applications").status_code == 401


def test_application_list_projects_status_and_masks_sensitive_fields():
    response = client.get("/api/v1/applications", headers={"Authorization": f"Bearer {_token()}"})
    assert response.status_code == 200
    item = response.json()["data"][0]
    assert item["application_status"] == "CAUTION_REVIEW_REQUIRED"
    assert item["citizen_id"] == "***"
    assert "form_data" not in item
    assert item["application_code"] == item["case_code"]
    assert item["anomaly_count"] >= 1


def test_application_detail_returns_frontend_management_dto():
    response = client.get("/api/v1/applications/case-demo-001", headers={"Authorization": f"Bearer {_token()}"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["application_code"] == "UBNDAI-2026-000001"
    assert data["anomalies"]
    assert data["citizen_id"] == "***"


def test_application_detail_is_tenant_scoped():
    response = client.get("/api/v1/applications/case-other-001", headers={"Authorization": f"Bearer {_token()}"})
    assert response.status_code == 404


def test_built_officer_spa_supports_nested_routes():
    response = client.get("/officer/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
