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

    # Completing the document may bump the case version (checklist item flips
    # to 'uploaded'/'uncertain') — re-fetch to get the current version before
    # the version-checked PATCH below, same as the citizen portal frontend does.
    refreshed = client.get(f"/api/v1/citizen/cases/{case['id']}", headers=citizen_headers)
    assert refreshed.status_code == 200, refreshed.text
    case_version_after_upload = refreshed.json()["data"]["case"]["version"]

    updated = client.patch(
        f"/api/v1/citizen/cases/{case['id']}",
        headers=citizen_headers,
        json={
            "expected_version": case_version_after_upload,
            "form_data": {"ho_ten_con": "Nguyễn An", "ho_ten_me": "Nguyễn Văn A"},
        },
    )
    assert updated.status_code == 200, updated.text
    updated_case = updated.json()["data"]

    submitted = client.post(
        f"/api/v1/citizen/cases/{case['id']}/submit",
        headers={**citizen_headers, "Idempotency-Key": f"submit-{case['id']}"},
        json={"expected_version": updated_case["version"], "consent_version": "privacy-v1", "consent_accepted": True},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "awaiting_officer_review"

    repeated = client.post(
        f"/api/v1/citizen/cases/{case['id']}/submit",
        headers={**citizen_headers, "Idempotency-Key": f"submit-{case['id']}"},
        json={"expected_version": updated_case["version"], "consent_version": "privacy-v1", "consent_accepted": True},
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


def test_citizen_can_update_form_data_and_clarification_answers():
    headers = auth("citizen.demo")
    created = client.post(
        "/api/v1/citizen/cases",
        headers=headers,
        json={"procedure_id": "khai_sinh", "locality_code": "00001"},
    ).json()["data"]
    updated = client.patch(
        f"/api/v1/citizen/cases/{created['id']}",
        headers=headers,
        json={
            "expected_version": created["version"],
            "form_data": {"full_name": "Nguyen An"},
            "answers": {"ket_hon": True},
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["form_data"]["full_name"] == "Nguyen An"
    assert updated.json()["data"]["form_data"]["_answers"] == {"ket_hon": True}
    assert updated.json()["data"]["version"] == created["version"] + 1


def test_clarification_answers_rebuild_conditional_checklist():
    headers = auth("citizen.demo")
    created = client.post(
        "/api/v1/citizen/cases",
        headers=headers,
        json={"procedure_id": "can_cuoc", "locality_code": "00001"},
    ).json()["data"]
    assert created["checklist"]["phieu_dc02"] == "missing"

    updated = client.patch(
        f"/api/v1/citizen/cases/{created['id']}",
        headers=headers,
        json={
            "expected_version": created["version"],
            "answers": {
                "nop_truc_tuyen": False,
                "co_thong_tin_csdl_dan_cu": True,
            },
        },
    )
    assert updated.status_code == 200, updated.text
    checklist = updated.json()["data"]["checklist"]
    assert checklist["phieu_cc01"] == "missing"
    assert checklist["phieu_dc02"] == "not_applicable"
    assert checklist["phieu_dc01"] == "not_applicable"
    assert checklist["giay_to_phap_ly_thong_tin_cong_dan"] == "not_applicable"


def test_preprocess_endpoint_returns_step_snapshots():
    import cv2
    import numpy as np

    headers = auth("citizen.demo")
    case = client.post("/api/v1/citizen/cases", headers=headers, json={"procedure_id": "khai_sinh", "locality_code": "00001"}).json()["data"]

    canvas = np.full((300, 400, 3), 240, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", canvas)
    assert ok
    content = encoded.tobytes()

    intent = client.post(
        f"/api/v1/citizen/cases/{case['id']}/documents/upload-intents",
        headers=headers,
        json={"filename": "giay.png", "content_type": "image/png", "size_bytes": len(content)},
    )
    assert intent.status_code == 201, intent.text
    document = intent.json()["data"]
    uploaded = client.put(document["upload_url"], headers={**headers, "Content-Type": "application/octet-stream"}, content=content)
    assert uploaded.status_code == 204, uploaded.text

    response = client.post(f"/api/v1/citizen/documents/{document['document_id']}/preprocess", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert "clahe_contrast" in data["applied_steps"]
    names = [step["name"] for step in data["steps"]]
    assert names[0] == "original"
    assert names[-1] == "clahe_contrast"
    assert all(step["image"].startswith("data:image/jpeg;base64,") for step in data["steps"])


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
