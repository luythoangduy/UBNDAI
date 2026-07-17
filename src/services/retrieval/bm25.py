"""BM25 (Okapi) thuần Python cho catalog TTHC. Owner: Dev A.

Corpus nhỏ (hàng trăm thủ tục) nên không cần thư viện ngoài. Tokenize
bỏ dấu tiếng Việt (common.tokenize). Cache JSON build bằng
scripts/index_procedures.py --build-bm25; thiếu cache thì build in-memory
trực tiếp từ catalog.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from src.services.retrieval.common import RetrievedChunk, tokenize

_K1 = 1.5
_B = 0.75


class Bm25Index:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks
        self._doc_tokens = [tokenize(chunk.content) for chunk in chunks]
        self._doc_lens = [len(tokens) for tokens in self._doc_tokens]
        self._avg_len = (
            sum(self._doc_lens) / len(self._doc_lens) if self._doc_lens else 0.0
        )
        self._doc_freq: dict[str, int] = {}
        for tokens in self._doc_tokens:
            for term in set(tokens):
                self._doc_freq[term] = self._doc_freq.get(term, 0) + 1

    def search(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        query_terms = tokenize(query)
        if not query_terms or not self._chunks:
            return []
        total_docs = len(self._chunks)
        scored: list[tuple[float, int]] = []
        for index, tokens in enumerate(self._doc_tokens):
            term_freq: dict[str, int] = {}
            for term in tokens:
                term_freq[term] = term_freq.get(term, 0) + 1
            score = 0.0
            for term in query_terms:
                freq = term_freq.get(term, 0)
                if not freq:
                    continue
                doc_freq = self._doc_freq.get(term, 0)
                idf = math.log(1 + (total_docs - doc_freq + 0.5) / (doc_freq + 0.5))
                denom = freq + _K1 * (
                    1 - _B + _B * self._doc_lens[index] / (self._avg_len or 1.0)
                )
                score += idf * freq * (_K1 + 1) / denom
            if score > 0:
                scored.append((score, index))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievedChunk(
                content=self._chunks[i].content,
                metadata=self._chunks[i].metadata,
                score=score,
            )
            for score, i in scored[:top_k]
        ]

    def save(self, path: Path | str) -> None:
        payload: dict[str, Any] = {
            "chunks": [
                {"content": c.content, "metadata": c.metadata} for c in self._chunks
            ]
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: Path | str) -> "Bm25Index":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        chunks = [
            RetrievedChunk(content=item["content"], metadata=item.get("metadata", {}))
            for item in payload.get("chunks", [])
        ]
        return cls(chunks)
