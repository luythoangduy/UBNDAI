"""Tests cho VisionLlmEngine + factory. Mock Gemini qua httpx.MockTransport."""

import json

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
    engine = VisionLlmEngine(api_key="test-key", model="gemini-test", client=client)
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
    engine = VisionLlmEngine(api_key="", model="m")

    with pytest.raises(OcrEngineError):
        engine.extract(FAKE_IMAGE)


def test_factory_resolves_all_engines():
    assert isinstance(get_engine("vision_llm"), VisionLlmEngine)
    assert isinstance(get_engine("paddleocr"), PaddleOcrEngine)
    assert isinstance(get_engine("google_vision"), GoogleVisionEngine)
    with pytest.raises(OcrEngineError):
        get_engine("does-not-exist")
