"""Tests endpoint POST /api/v1/validation/check (stateless MVP)."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def _payload(include_ai: bool = False) -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "case": {
            "id": "case_1",
            "citizen_id": "citizen_1",
            "procedure_id": "khai_sinh",
            "answers": {"sinh_tai_co_so_y_te": True},
            "checklist": [{"requirement_code": "giay_chung_sinh", "status": "missing"}],
            "form_data": {},
            "created_at": now,
            "updated_at": now,
        },
        "documents": [],
        "include_ai": include_ai,
    }


def test_check_returns_report_with_blocking_error():
    response = client.post("/api/v1/validation/check", json=_payload())

    assert response.status_code == 200
    report = response.json()
    assert report["case_id"] == "case_1"
    rule_ids = {i["rule_id"] for i in report["issues"]}
    assert "KS-R1" in rule_ids  # thiếu giấy chứng sinh khi sinh tại cơ sở y tế
    # 1 error (0.3) + 1 checklist missing (0.15)
    assert abs(report["readiness_score"] - 0.55) < 1e-6


def test_check_rejects_case_without_procedure():
    payload = _payload()
    payload["case"]["procedure_id"] = None

    response = client.post("/api/v1/validation/check", json=payload)

    assert response.status_code == 400
