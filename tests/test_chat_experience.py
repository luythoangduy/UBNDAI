import asyncio

from fastapi.testclient import TestClient

from src.config import settings
from src.main import app
from src.services import chat_experience
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


def test_empty_live_fetch_is_not_reported_as_verified(monkeypatch):
    """HTTP 200 nhưng không bóc được biểu mẫu nào không được gắn ✓ 'đã kiểm tra'.

    Cổng DVC nay render phía client nên HTML trả về chỉ là vỏ SPA rỗng. Gắn
    status="ready" cho trường hợp này là tuyên bố đã kiểm chứng một thứ chưa hề
    đọc được — vi phạm quy tắc grounding (AGENTS.md §5) và làm hỏng chính luận
    điểm "có căn cứ" của sản phẩm.
    """

    class _EmptyShellResponse:
        text = "<!doctype html><html><head><link rel='icon' href='/quoc_huy.svg'></head><body></body></html>"

        def raise_for_status(self) -> None:
            return None

    class _Client:
        def __init__(self, *args, **kwargs) -> None: ...
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args) -> None:
            return None
        async def get(self, *args, **kwargs):
            return _EmptyShellResponse()

    monkeypatch.setattr(settings, "official_source_live_fetch", True)
    monkeypatch.setattr(chat_experience.httpx, "AsyncClient", _Client)

    resources, step, retry_soon = asyncio.run(
        chat_experience._fetch_official_page(
            "https://dichvucong.gov.vn/p/home/thu-tuc.html", "khai_sinh"
        )
    )

    assert resources == []
    assert step.status == "fallback", "vỏ SPA rỗng phải là fallback, không phải ready"
    assert "không đọc được" in step.detail
    assert retry_soon is True


def test_live_fetch_failure_is_cached_briefly_so_it_can_recover(monkeypatch):
    """Lỗi nguồn live phải hết hạn sau vài phút, không bị đóng băng cả tiếng."""

    class _Boom:
        def __init__(self, *args, **kwargs) -> None: ...
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args) -> None:
            return None
        async def get(self, *args, **kwargs):
            raise RuntimeError("Cổng DVC trả 503")

    recorded: dict[str, int] = {}

    async def _capture_ttl(key, value, *, ttl_seconds):
        recorded[key] = ttl_seconds
        return "memory"

    monkeypatch.setattr(settings, "official_source_live_fetch", True)
    monkeypatch.setattr(chat_experience.httpx, "AsyncClient", _Boom)
    monkeypatch.setattr(chat_experience, "set_json", _capture_ttl)

    asyncio.run(chat_experience.build_experience("khai_sinh", "đăng ký khai sinh"))

    assert recorded, "phải ghi cache cho lượt vừa dựng"
    ttl = next(iter(recorded.values()))
    assert ttl == settings.official_source_retry_ttl_s
    assert ttl < settings.chat_experience_cache_ttl_s


def test_cache_info_reports_the_ttl_actually_used(monkeypatch):
    """ttl_seconds trả về client phải khớp TTL đã ghi, không phải hằng số mặc định."""

    class _Boom:
        def __init__(self, *args, **kwargs) -> None: ...
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args) -> None:
            return None
        async def get(self, *args, **kwargs):
            raise RuntimeError("Cổng DVC trả 503")

    monkeypatch.setattr(settings, "official_source_live_fetch", True)
    monkeypatch.setattr(chat_experience.httpx, "AsyncClient", _Boom)

    experience = asyncio.run(
        chat_experience.build_experience("khai_sinh", "đăng ký khai sinh")
    )

    assert experience.cache.ttl_seconds == settings.official_source_retry_ttl_s
