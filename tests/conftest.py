"""Cách ly môi trường test: DB tạm, không Chroma index, không API key.

Không có key → planner/answer tự rơi về rule-based/extractive fallback,
retrieval rơi về BM25 in-memory từ catalog — không load model thật trong pytest
(bài học C2: bge-m3 trong pytest gây access violation).
"""

import pytest

from src.config import settings
from src.services import retrieval


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'app.db'}")
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings, "bm25_index_path", str(tmp_path / "bm25.json"))
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    retrieval.reset_caches()
    yield
    retrieval.reset_caches()
