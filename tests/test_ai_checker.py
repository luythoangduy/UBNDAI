"""Tests AI checker — mock Anthropic qua MockTransport, LLM lỗi không được làm chết validation."""

import json
from datetime import UTC, datetime

import anthropic
import httpx

from src.models import Case, ExtractedDocument, ExtractedField
from src.services.validation import ai_checker


def _case(form_data=None) -> Case:
    now = datetime.now(UTC)
    return Case(
        id="case_1",
        citizen_id="citizen_1",
        procedure_id="khai_sinh",
        form_data=form_data if form_data is not None else {"ho_ten_me": "Trần Thị Hoa"},
        created_at=now,
        updated_at=now,
    )


def _doc() -> ExtractedDocument:
    return ExtractedDocument(
        id="doc_1",
        case_id="case_1",
        file_id="file_1",
        doc_type="cccd",
        doc_type_confidence=0.95,
        fields=[ExtractedField(key="ho_ten", value="Trần Thị Hòa", confidence=0.9)],
        ocr_engine="vision_llm",
        created_at=datetime.now(UTC),
    )


def _client(handler) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )


def _message_response(payload: dict) -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-4-5",
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


async def test_ai_issues_are_parsed_with_source_ai():
    payload = {
        "issues": [
            {
                "kind": "name_mismatch",
                "severity": "warning",
                "message": "Tên mẹ trên CCCD và biểu mẫu khác dấu: 'Hòa' vs 'Hoa'.",
                "field_keys": ["cccd.ho_ten"],
                "suggestion": "Kiểm tra lại dấu trong họ tên.",
            }
        ]
    }
    client = _client(lambda req: httpx.Response(200, json=_message_response(payload)))

    issues = await ai_checker.run(_case(), [_doc()], client=client)

    assert len(issues) == 1
    assert issues[0].rule_id == "ai.name_mismatch"
    assert issues[0].severity == "warning"
    assert issues[0].source == "ai"


async def test_llm_failure_returns_empty_list():
    client = _client(lambda req: httpx.Response(500, json={"error": {"message": "boom"}}))

    issues = await ai_checker.run(_case(), [_doc()], client=client)

    assert issues == []


async def test_non_json_answer_returns_empty_list():
    body = _message_response({})
    body["content"] = [{"type": "text", "text": "xin lỗi, tôi không chắc"}]
    client = _client(lambda req: httpx.Response(200, json=body))

    issues = await ai_checker.run(_case(), [_doc()], client=client)

    assert issues == []


async def test_empty_dossier_short_circuits_without_llm_call():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json=_message_response({"issues": []}))

    case = _case(form_data={})
    issues = await ai_checker.run(case, [], client=_client(handler))

    assert issues == []
    assert calls == []
