from fastapi.testclient import TestClient

from src.main import app
from src.services.chat_experience import is_official_url

client = TestClient(app)


def test_starter_options_are_driven_by_published_catalog():
    response = client.get("/api/v1/chat/starter")

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"]
    assert payload["actions"][0]["kind"] == "send_message"
    assert payload["evidence"][0]["id"] == "hybrid-search"


def test_identified_procedure_returns_actions_templates_and_provenance():
    response = client.post(
        "/api/v1/chat",
        json={"message": "tôi muốn đăng ký khai sinh cho con"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["procedure_id"] == "khai_sinh"
    action_ids = {item["id"] for item in payload["actions"]}
    assert {"checklist", "templates", "start-form", "official-source"} <= action_ids
    assert payload["templates"]
    declaration = next(
        item for item in payload["templates"] if item["template_id"] == "khai_sinh.to_khai"
    )
    assert declaration["official_source"] is True
    assert "vanban.chinhphu.vn" in declaration["source_url"]
    assert declaration["citations"][0]["role"] == "output_template"
    assert any(step["id"] == "official-api" for step in payload["evidence"])


def test_same_source_checksum_uses_cache_on_next_chat():
    first = client.post(
        "/api/v1/chat", json={"message": "đăng ký khai sinh cho bé"}
    ).json()
    second = client.post(
        "/api/v1/chat", json={"message": "đăng ký khai sinh cho bé"}
    ).json()

    assert first["cache"]["status"] == "miss"
    assert second["cache"]["status"] == "hit"
    assert second["evidence"][0]["status"] == "cache_hit"


def test_only_government_and_trusted_official_domains_get_official_badge():
    assert is_official_url("https://thutuc.dichvucong.gov.vn/example")
    assert is_official_url("https://vanban.chinhphu.vn/example")
    assert is_official_url("https://vbpl.moj.gov.vn/example")
    assert not is_official_url("https://example.com/template.docx")
