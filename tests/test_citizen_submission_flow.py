import hashlib

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def auth(username: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "ChangeMe123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_citizen_submit_appears_in_officer_queue():
    citizen_headers = auth("citizen.demo")
    created = client.post(
        "/api/v1/citizen/cases",
        headers=citizen_headers,
        json={"procedure_id": "khai_sinh", "locality_code": "00001"},
    )
    assert created.status_code == 201, created.text
    case = created.json()["data"]

    content = b"\x89PNG\r\n\x1a\nCCCD Nguyen Van A"
    intent = client.post(
        f"/api/v1/citizen/cases/{case['id']}/documents/upload-intents",
        headers=citizen_headers,
        json={"filename": "cccd.png", "content_type": "image/png", "size_bytes": len(content)},
    )
    assert intent.status_code == 201, intent.text
    document = intent.json()["data"]

    uploaded = client.put(document["upload_url"], headers={**citizen_headers, "Content-Type": "application/octet-stream"}, content=content)
    assert uploaded.status_code == 204, uploaded.text

    completed = client.post(
        f"/api/v1/citizen/documents/{document['document_id']}/complete",
        headers=citizen_headers,
        json={"sha256": hashlib.sha256(content).hexdigest()},
    )
    assert completed.status_code == 200, completed.text

    submitted = client.post(
        f"/api/v1/citizen/cases/{case['id']}/submit",
        headers={**citizen_headers, "Idempotency-Key": f"submit-{case['id']}"},
        json={"expected_version": case["version"], "consent_version": "privacy-v1", "consent_accepted": True},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "awaiting_officer_review"

    repeated = client.post(
        f"/api/v1/citizen/cases/{case['id']}/submit",
        headers={**citizen_headers, "Idempotency-Key": f"submit-{case['id']}"},
        json={"expected_version": case["version"], "consent_version": "privacy-v1", "consent_accepted": True},
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["submission_version"] == submitted.json()["data"]["submission_version"]

    officer_headers = auth("officer.demo")
    queue = client.get("/api/v1/officer/cases", headers=officer_headers)
    assert queue.status_code == 200
    assert any(item["id"] == case["id"] for item in queue.json()["data"])


def test_citizen_cannot_access_another_citizens_case():
    first = auth("citizen.demo")
    second = auth("citizen.other")
    created = client.post("/api/v1/citizen/cases", headers=first, json={"procedure_id": "khai_sinh", "locality_code": "00001"})
    case_id = created.json()["data"]["id"]
    assert client.get(f"/api/v1/citizen/cases/{case_id}", headers=second).status_code == 404


def test_upload_policy_rejects_invalid_type_and_oversized_file():
    headers = auth("citizen.demo")
    case = client.post("/api/v1/citizen/cases", headers=headers, json={"procedure_id": "khai_sinh", "locality_code": "00001"}).json()["data"]
    invalid = client.post(
        f"/api/v1/citizen/cases/{case['id']}/documents/upload-intents",
        headers=headers,
        json={"filename": "malware.exe", "content_type": "application/octet-stream", "size_bytes": 100},
    )
    assert invalid.status_code == 422
    too_large = client.post(
        f"/api/v1/citizen/cases/{case['id']}/documents/upload-intents",
        headers=headers,
        json={"filename": "large.pdf", "content_type": "application/pdf", "size_bytes": 20 * 1024 * 1024 + 1},
    )
    assert too_large.status_code == 422
