"""Tests cho VisionLlmEngine + factory.

Gemini mock qua httpx.MockTransport trực tiếp; Anthropic mock qua MockTransport
gắn vào http_client của official SDK (giữ nguyên wire format Messages API).
"""

import json

import anthropic
import httpx
import pytest

from src.services.ocr.engine import (
    GoogleVisionEngine,
    OcrEngineError,
    PaddleOcrEngine,
    VisionLlmEngine,
    get_engine,
)

FAKE_IMAGE = b"\x89PNG fake-bytes"


def _gemini_response(payload: dict) -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}
        ]
    }


def _anthropic_response(payload: dict) -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-test",
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


def _engine_with_mock(payload: dict | None = None, status_code: int = 200, raw_text: str | None = None):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = json.loads(request.content)
        captured["url"] = str(request.url)
        if raw_text is not None:
            body = {"candidates": [{"content": {"parts": [{"text": raw_text}]}}]}
        else:
            body = _gemini_response(payload or {})
        return httpx.Response(status_code, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    engine = VisionLlmEngine(
        provider="gemini", api_key="test-key", model="gemini-test", client=client
    )
    return engine, captured


def _anthropic_engine_with_mock(payload: dict):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = json.loads(request.content)
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json=_anthropic_response(payload))

    sdk_client = anthropic.Anthropic(
        api_key="test-anthropic-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )
    engine = VisionLlmEngine(
        provider="anthropic",
        api_key="test-anthropic-key",
        model="claude-test",
        anthropic_client=sdk_client,
    )
    return engine, captured


def test_extract_parses_fields_and_doc_type():
    engine, captured = _engine_with_mock(
        {
            "raw_text": "Họ tên: Nguyễn Văn A",
            "doc_type": "giay_chung_sinh",
            "doc_type_confidence": 0.92,
            "fields": [
                {"key": "ho_ten", "value": "Nguyễn Văn A", "confidence": 0.95},
                {"key": "ngay_sinh", "value": "12/03/2024", "confidence": 0.7, "note": "số mờ"},
            ],
        }
    )

    result = engine.extract(FAKE_IMAGE)

    assert result.doc_type_hint == "giay_chung_sinh"
    assert result.doc_type_confidence == 0.92
    assert [f.key for f in result.fields] == ["ho_ten", "ngay_sinh"]
    assert result.fields[1].note == "số mờ"
    assert result.engine == "vision_llm"
    assert "gemini-test" in captured["url"]


def test_extract_sends_field_keys_instruction():
    engine, captured = _engine_with_mock({"raw_text": "x", "fields": []})

    engine.extract(FAKE_IMAGE, field_keys=["ho_ten", "so_cccd"])

    task_text = captured["request"]["contents"][0]["parts"][0]["text"]
    assert "ho_ten" in task_text
    assert "so_cccd" in task_text


def test_extract_clamps_out_of_range_confidence():
    engine, _ = _engine_with_mock(
        {
            "raw_text": "x",
            "doc_type": "cccd",
            "doc_type_confidence": 1.7,
            "fields": [{"key": "ho_ten", "value": "A", "confidence": -0.5}],
        }
    )

    result = engine.extract(FAKE_IMAGE)

    assert result.doc_type_confidence == 1.0
    assert result.fields[0].confidence == 0.0


def test_extract_tolerates_markdown_fenced_json():
    payload = json.dumps({"raw_text": "ok", "fields": []})
    engine, _ = _engine_with_mock(raw_text=f"```json\n{payload}\n```")

    assert engine.extract(FAKE_IMAGE).raw_text == "ok"


def test_extract_raises_on_http_error():
    engine, _ = _engine_with_mock({}, status_code=500)

    with pytest.raises(OcrEngineError):
        engine.extract(FAKE_IMAGE)


def test_extract_raises_on_non_json_answer():
    engine, _ = _engine_with_mock(raw_text="xin lỗi, không đọc được")

    with pytest.raises(OcrEngineError):
        engine.extract(FAKE_IMAGE)


def test_extract_requires_api_key():
    engine = VisionLlmEngine(provider="gemini", api_key="", model="m")

    with pytest.raises(OcrEngineError):
        engine.extract(FAKE_IMAGE)


def test_extract_rejects_unsupported_provider():
    engine = VisionLlmEngine(provider="openai", api_key="k", model="m")

    with pytest.raises(OcrEngineError):
        engine.extract(FAKE_IMAGE)


def test_anthropic_provider_parses_fields_and_sends_image_block():
    engine, captured = _anthropic_engine_with_mock(
        {
            "raw_text": "GIẤY CHỨNG SINH",
            "doc_type": "giay_chung_sinh",
            "doc_type_confidence": 0.9,
            "fields": [{"key": "ho_ten_con", "value": "Nguyễn Văn Bé", "confidence": 0.88}],
        }
    )

    result = engine.extract(FAKE_IMAGE, field_keys=["ho_ten_con"])

    assert result.doc_type_hint == "giay_chung_sinh"
    assert result.fields[0].key == "ho_ten_con"
    assert result.engine == "vision_llm"
    # Đúng endpoint + headers Anthropic (SDK tự set version header)
    assert "api.anthropic.com/v1/messages" in captured["url"]
    assert captured["headers"]["x-api-key"] == "test-anthropic-key"
    assert "anthropic-version" in captured["headers"]
    # Payload: structured output schema + image block base64, KHÔNG có temperature
    assert captured["request"]["model"] == "claude-test"
    assert "temperature" not in captured["request"]
    assert captured["request"]["output_config"]["format"]["type"] == "json_schema"
    content = captured["request"]["messages"][0]["content"]
    assert content[0]["type"] == "text" and "ho_ten_con" in content[0]["text"]
    assert content[1]["type"] == "image"
    assert content[1]["source"]["media_type"] == "image/jpeg"


def _openai_engine_with_mock(payload: dict | None = None, refusal: str | None = None):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = json.loads(request.content)
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        message: dict = {"role": "assistant"}
        if refusal is not None:
            message["content"] = None
            message["refusal"] = refusal
        else:
            message["content"] = json.dumps(payload or {}, ensure_ascii=False)
        return httpx.Response(200, json={"choices": [{"message": message}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    engine = VisionLlmEngine(
        provider="openai", api_key="test-openai-key", model="gpt-5-test", client=client
    )
    return engine, captured


def test_openai_provider_parses_fields_and_sends_strict_schema():
    engine, captured = _openai_engine_with_mock(
        {
            "raw_text": "GIẤY CHỨNG SINH",
            "doc_type": "giay_chung_sinh",
            "doc_type_confidence": 0.9,
            "fields": [
                {"key": "ho_ten_con", "value": "Nguyễn Văn Bé", "confidence": 0.88, "note": ""}
            ],
        }
    )

    result = engine.extract(FAKE_IMAGE, field_keys=["ho_ten_con"])

    assert result.doc_type_hint == "giay_chung_sinh"
    assert result.fields[0].key == "ho_ten_con"
    # Đúng endpoint + bearer auth
    assert "api.openai.com/v1/chat/completions" in captured["url"]
    assert captured["headers"]["authorization"] == "Bearer test-openai-key"
    # Reasoning model: không temperature, dùng max_completion_tokens + strict schema;
    # OCR là phiên âm thuần nên chạy reasoning_effort minimal cho nhanh.
    req = captured["request"]
    assert "temperature" not in req
    assert req["max_completion_tokens"] == 4000
    assert req["reasoning_effort"] == "minimal"
    assert req["response_format"]["json_schema"]["strict"] is True
    field_schema = req["response_format"]["json_schema"]["schema"]["properties"]["fields"]["items"]
    assert set(field_schema["properties"]) == set(field_schema["required"])
    user_content = req["messages"][1]["content"]
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_openai_refusal_raises():
    engine, _ = _openai_engine_with_mock(refusal="I can't help with that.")

    with pytest.raises(OcrEngineError):
        engine.extract(FAKE_IMAGE)


def test_handwriting_notes_and_quality_are_parsed():
    engine, _ = _engine_with_mock(
        {
            "raw_text": "QUYẾT ĐỊNH\nSố: 123/QĐ-UBND\n[ILLEGIBLE] ngày 12/03/2026",
            "doc_type": "van_ban_hanh_chinh",
            "doc_type_confidence": 0.9,
            "fields": [{"key": "so_van_ban", "value": "123/QĐ-UBND", "confidence": 0.95, "note": ""}],
            "handwriting_notes": [
                {
                    "location": "góc trên phải",
                    "content": "Kính chuyển phòng TP xử lý",
                    "confidence": 0.7,
                    "alternatives": "1. Kính chuyển phòng TP xử lý (70%) | 2. Kính chuyển phòng TC xử lý (30%)",
                }
            ],
            "illegible_regions": ["dòng 3 — mực nhòe trước ngày tháng"],
            "quality": {"ocr_confidence": 0.82, "handwriting_confidence": 0.6, "issues": ["ảnh nghiêng nhẹ"]},
        }
    )

    result = engine.extract(FAKE_IMAGE)

    assert result.doc_type_hint == "van_ban_hanh_chinh"
    assert "[ILLEGIBLE]" in result.raw_text
    note = result.handwriting_notes[0]
    assert note.location == "góc trên phải" and "Kính chuyển" in note.content
    assert "70%" in note.alternatives
    assert result.illegible_regions == ["dòng 3 — mực nhòe trước ngày tháng"]
    assert result.ocr_confidence == 0.82
    assert result.quality_issues == ["ảnh nghiêng nhẹ"]


def test_missing_quality_sections_default_to_confident():
    engine, _ = _engine_with_mock({"raw_text": "x", "fields": []})

    result = engine.extract(FAKE_IMAGE)

    assert result.handwriting_notes == []
    assert result.illegible_regions == []
    assert result.ocr_confidence == 1.0


def test_factory_resolves_all_engines():
    assert isinstance(get_engine("vision_llm"), VisionLlmEngine)
    assert isinstance(get_engine("paddleocr"), PaddleOcrEngine)
    assert isinstance(get_engine("google_vision"), GoogleVisionEngine)
    with pytest.raises(OcrEngineError):
        get_engine("does-not-exist")


def test_openai_payload_includes_reasoning_effort():
    engine, captured = _openai_engine_with_mock({"raw_text": "x", "fields": []})
    engine._reasoning_effort = "low"

    engine.extract(FAKE_IMAGE)

    assert captured["request"]["reasoning_effort"] == "low"


def test_invalid_reasoning_effort_is_omitted():
    engine, captured = _openai_engine_with_mock({"raw_text": "x", "fields": []})
    engine._reasoning_effort = "turbo"

    engine.extract(FAKE_IMAGE)

    assert "reasoning_effort" not in captured["request"]
