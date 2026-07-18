from fastapi.testclient import TestClient

from src.config import settings
from src.main import app

client = TestClient(app)


def _headers(username: str = "officer.demo") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": settings.demo_password})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_application_filters_and_stale_assignment():
    headers = _headers()
    response = client.get("/api/v1/applications?procedure_id=khai_sinh&has_anomaly=true&severity=error", headers=headers)
    assert response.status_code == 200
    assert response.json()["pagination"]["total"] >= 1
    conflict = client.patch("/api/v1/applications/case-demo-001/assignment", headers=headers, json={"assigned_to": "officer-demo", "expected_version": 999})
    assert conflict.status_code == 409


def test_management_endpoints_are_tenant_scoped_and_protected():
    assert client.get("/api/v1/officer-dashboard/summary").status_code == 401
    assert client.get("/api/v1/applications/case-other-001/events", headers=_headers()).status_code == 404


def test_dashboard_zero_fills_and_validates_range_timezone():
    headers = _headers()
    response = client.get("/api/v1/officer-dashboard/timeseries?from=2026-01-01&to=2026-01-03&timezone=Asia/Bangkok", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"] == [
        {"period": "2026-01-01", "count": 0},
        {"period": "2026-01-02", "count": 0},
        {"period": "2026-01-03", "count": 0},
    ]
    assert client.get("/api/v1/officer-dashboard/summary?timezone=No/Such_Zone", headers=headers).status_code == 422
    assert client.get("/api/v1/officer-dashboard/summary?from=2026-02-01&to=2026-01-01", headers=headers).status_code == 422


def test_all_dashboard_distributions_return_envelopes():
    headers = _headers()
    for endpoint in ("summary", "status-distribution", "application-types", "anomalies"):
        response = client.get(f"/api/v1/officer-dashboard/{endpoint}", headers=headers)
        assert response.status_code == 200
        assert response.json()["success"] is True
