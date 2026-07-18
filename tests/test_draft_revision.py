from types import SimpleNamespace

import pytest

from src.models import DraftReviseRequest
from src.services.drafts import reviser


class _FakeLlm:
    async def ainvoke(self, _messages):
        return SimpleNamespace(
            content=(
                "```html\n<h1 onclick=\"bad()\">Tiêu đề mới</h1>"
                "<script>alert(1)</script><p style=\"color:red\">Nội dung</p>\n```"
            )
        )


@pytest.mark.asyncio
async def test_revise_sanitizes_model_html(monkeypatch):
    monkeypatch.setattr(reviser, "llm_is_configured", lambda: True)
    monkeypatch.setattr(reviser, "get_llm", lambda **_: _FakeLlm())

    result = await reviser.revise(
        DraftReviseRequest(
            html="<h1>Tiêu đề</h1><p>Nội dung</p>",
            instruction="Viết tiêu đề rõ hơn",
        )
    )

    assert result.revised_html == "<h1>Tiêu đề mới</h1><p>Nội dung</p>"
    assert "script" not in result.revised_html
    assert "onclick" not in result.revised_html


@pytest.mark.asyncio
async def test_revise_requires_configured_model(monkeypatch):
    monkeypatch.setattr(reviser, "llm_is_configured", lambda: False)

    with pytest.raises(RuntimeError, match="Chưa cấu hình"):
        await reviser.revise(
            DraftReviseRequest(html="<p>Nội dung</p>", instruction="Rút gọn")
        )
