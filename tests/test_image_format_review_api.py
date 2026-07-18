import io

from fastapi.testclient import TestClient
from PIL import Image

from src.main import app


client = TestClient(app)


def _citizen_headers() -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "citizen.demo", "password": "ChangeMe123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _png(width: int = 1400, height: int = 1800) -> bytes:
    image = Image.new("RGB", (width, height), "#d0d0d0")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_image_format_review_returns_non_persistent_quality_checks():
    response = client.post(
        "/api/v1/citizen/format-review",
        headers=_citizen_headers(),
        files={"file": ("document.png", _png(), "image/png")},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["media_type"] == "image/png"
    assert payload["width"] == 1400
    assert payload["height"] == 1800
    assert {check["code"] for check in payload["checks"]} >= {
        "supported_image",
        "lighting_ok",
    }


def test_image_format_review_rejects_non_image_uploads():
    response = client.post(
        "/api/v1/citizen/format-review",
        headers=_citizen_headers(),
        files={"file": ("document.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert response.status_code == 422
