"""Cách ly môi trường test: DB tạm, không Chroma index, không API key.

Không có key → planner/answer tự rơi về rule-based/extractive fallback,
retrieval rơi về BM25 in-memory từ catalog — không load model thật trong pytest
(bài học C2: bge-m3 trong pytest gây access violation).
"""

import os

import pytest

# Tests must never bootstrap the global OfficerStore against a developer's
# persistent SQLite database from .env. Persistence-specific tests construct
# their own Database/OfficerStore instances explicitly.
os.environ["PERSISTENCE_ENABLED"] = "false"

from src.config import settings
from src.services import retrieval
from src.services.retrieval import legal
from src.services.response_cache import reset_cache


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'app.db'}")
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings, "legal_chroma_persist_dir", "")
    monkeypatch.setattr(settings, "bm25_index_path", str(tmp_path / "bm25.json"))
    monkeypatch.setattr(settings, "raw_documents_dir", str(tmp_path / "raw_documents"))
    monkeypatch.setattr(settings, "procedure_candidates_dir", str(tmp_path / "procedure_candidates"))
    monkeypatch.setattr(settings, "legal_bm25_index_path", str(tmp_path / "legal_bm25.json"))
    monkeypatch.setattr(settings, "legal_collection", "legal_documents_test")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "ocr_engine", "paddleocr")
    monkeypatch.setattr(settings, "ocr_llm_api_key", "")
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "official_source_live_fetch", False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OCR_LLM_API_KEY", raising=False)
    retrieval.reset_caches()
    legal.reset_caches()
    reset_cache()
    yield
    retrieval.reset_caches()
    legal.reset_caches()
    reset_cache()
