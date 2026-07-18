from fastapi.testclient import TestClient

from src.main import app


def test_procedure_api_drives_catalog_form_and_capabilities():
    client = TestClient(app)

    procedures = client.get("/api/v1/procedures")
    assert procedures.status_code == 200
    birth = next(item for item in procedures.json() if item["id"] == "khai_sinh")
    assert birth["name"] == "Đăng ký khai sinh"

    schema = client.get("/api/v1/procedures/khai_sinh/form-schema")
    assert schema.status_code == 200
    assert schema.json()["fields"]
    assert any(field["required"] for field in schema.json()["fields"])
    assert schema.json()["clarifying_questions"]

    identity_schema = client.get("/api/v1/procedures/can_cuoc/form-schema")
    assert identity_schema.status_code == 200
    gender = next(field for field in identity_schema.json()["fields"] if field["key"] == "gioi_tinh")
    assert gender["type"] == "select"
    assert gender["options"] == ["Nam", "Nữ"]

    capabilities = client.get("/api/v1/procedures/khai_sinh/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json() == {
        "chat": True,
        "checklist": True,
        "dynamic_form": True,
        "ocr_autofill": True,
        "legal_validation": True,
        "official_draft": True,
        "requires_human_review": False,
    }


def test_unknown_procedure_has_no_form_schema():
    response = TestClient(app).get("/api/v1/procedures/not-found/form-schema")
    assert response.status_code == 409
