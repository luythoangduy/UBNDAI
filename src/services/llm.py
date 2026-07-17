"""Chat LLM factory (Claude — Anthropic). Port pattern từ C2-App-108/src/services/llm.py.

Mặc định claude-haiku-4-5 — tier Claude rẻ/nhanh nhất, cố định theo quyết định
dự án để không trôi sang model đắt hơn (giống C2).

Caller phải chịu được RuntimeError (thiếu key/thiếu package) — planner có
rule-based fallback, answer node có fallback trích dẫn deterministic.
"""

from __future__ import annotations

import os
from typing import Any

from src.config import settings
from src.services.retrieval.embeddings import has_real_api_key


def anthropic_api_key() -> str:
    return settings.llm_api_key or os.environ.get("ANTHROPIC_API_KEY", "")


def get_llm(*, temperature: float | None = None) -> Any:
    key = anthropic_api_key()
    if not has_real_api_key(key):
        raise RuntimeError("Thiếu LLM_API_KEY/ANTHROPIC_API_KEY hợp lệ cho Claude.")
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:
        raise RuntimeError(
            "Cần langchain-anthropic: pip install langchain-anthropic"
        ) from exc
    return ChatAnthropic(
        model=settings.llm_model,
        anthropic_api_key=key,
        temperature=settings.llm_temperature if temperature is None else temperature,
        timeout=settings.llm_timeout_s,
        max_retries=1,
    )
