"""guidance_bridge: portal-case projection chỉ được tạo sau lượt chat thành công.

Bug đã sửa: resolve_case_id() từng gọi store.ensure_guidance_case() ngay khi tạo
case mới, TRƯỚC KHI graph chạy. Nếu lượt chat lỗi (agent/LLM/hạ tầng), case rỗng
đó vẫn bị lưu vĩnh viễn trong /citizen/cases với procedure_id "pending_guidance"
— rò rỉ tên trạng thái nội bộ ra lịch sử trò chuyện của công dân và tạo ra các
mục "ma" mỗi lần người dùng thử lại sau lỗi.
"""

from fastapi.testclient import TestClient

from src.main import app
import src.agents.graph as graph_module

client = TestClient(app)


def auth(username: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "ChangeMe123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_successful_turn_creates_portal_case_projection():
    headers = auth("citizen.demo")
    response = client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "tôi muốn đăng ký khai sinh cho con mới sinh"},
    )
    assert response.status_code == 200, response.text
    case_id = response.json()["case_id"]

    cases = client.get("/api/v1/citizen/cases", headers=headers)
    assert cases.status_code == 200, cases.text
    assert any(item["id"] == case_id for item in cases.json()["data"])


def test_failed_turn_leaves_no_ghost_case_in_citizen_history(monkeypatch):
    async def boom(*_args, **_kwargs):
        raise RuntimeError("simulated agent/LLM failure")

    monkeypatch.setattr(graph_module, "_run_locked_turn", boom)
    headers = auth("citizen.demo")

    before = client.get("/api/v1/citizen/cases", headers=headers)
    assert before.status_code == 200, before.text
    before_ids = {item["id"] for item in before.json()["data"]}

    # raise_server_exceptions=False: lượt chat lỗi phải trả 500 cho client thật,
    # không phải để bài test tự nổ theo traceback của unhandled exception.
    unsafe_client = TestClient(app, raise_server_exceptions=False)
    response = unsafe_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "tôi muốn đăng ký khai sinh cho con mới sinh"},
    )
    assert response.status_code == 500

    after = client.get("/api/v1/citizen/cases", headers=headers)
    assert after.status_code == 200, after.text
    after_ids = {item["id"] for item in after.json()["data"]}
    assert after_ids == before_ids, (
        "Lượt chat lỗi không được để lại case rỗng trong lịch sử công dân "
        f"(mục mới xuất hiện: {after_ids - before_ids})"
    )
