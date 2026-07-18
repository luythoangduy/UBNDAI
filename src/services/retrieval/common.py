"""Kiểu dữ liệu chung + RRF + citation builder cho retrieval TTHC. Owner: Dev A.

Port pattern từ C2-App-108/src/services/retrieval_common.py, gọt bỏ phần
đặc thù VBPL (legal number, private scope) — domain ở đây là catalog thủ tục.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from src.models import Citation

# Cảnh báo grounding (AGENTS.md §5): thiếu nguồn → không đoán.
NO_SOURCE_WARNING = (
    "Chưa tìm thấy đủ căn cứ trong các nguồn thủ tục và văn bản pháp luật đã đồng bộ "
    "để trả lời chắc chắn. Bạn có thể mở kết quả từ nguồn Chính phủ bên dưới, mô tả "
    "cụ thể hơn nhu cầu, hoặc liên hệ cơ quan tiếp nhận."
)

RRF_K = 60


@dataclass(frozen=True)
class RetrievedChunk:
    """Một đoạn catalog được truy xuất, giữ metadata để trace citation."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None

    @property
    def chunk_id(self) -> str:
        return str(self.metadata.get("chunk_id") or "")

    @property
    def procedure_id(self) -> str:
        return str(self.metadata.get("procedure_id") or "")

    def excerpt(self, max_chars: int = 400) -> str:
        compact = " ".join(self.content.split())
        if len(compact) <= max_chars:
            return compact
        return compact[: max_chars - 3].rstrip() + "..."


def fold_ascii(text: str) -> str:
    """Bỏ dấu tiếng Việt + casefold — dùng cho BM25 và so khớp keyword."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.replace("đ", "d").replace("Đ", "D").casefold()


def tokenize(text: str) -> list[str]:
    return [tok for tok in re.split(r"[^0-9a-z]+", fold_ascii(text)) if tok]


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedChunk]], *, k: int = RRF_K
) -> list[RetrievedChunk]:
    scores: dict[str, float] = {}
    best: dict[str, RetrievedChunk] = {}
    for chunks in ranked_lists:
        for rank, chunk in enumerate(chunks, start=1):
            key = chunk.chunk_id or chunk.content
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in best:
                best[key] = chunk
    fused = sorted(
        best.items(), key=lambda item: scores[item[0]], reverse=True
    )
    return [
        RetrievedChunk(content=c.content, metadata=c.metadata, score=scores[key])
        for key, c in fused
    ]


def citations_from_chunks(chunks: list[RetrievedChunk]) -> list[Citation]:
    """Một citation cho mỗi chunk; ``index`` khớp trực tiếp chỉ dấu [n]."""
    citations: list[Citation] = []
    for index, chunk in enumerate(chunks, start=1):
        procedure_id = chunk.procedure_id
        if not procedure_id or not chunk.chunk_id:
            continue
        name = str(chunk.metadata.get("procedure_name") or procedure_id)
        legal_basis = str(chunk.metadata.get("legal_basis") or "").strip()
        if (
            chunk.metadata.get("source_type") == "legal_corpus"
            or chunk.metadata.get("source_scope") == "public_vbpl"
        ):
            label = f"Văn bản pháp luật — {name}"
        elif chunk.metadata.get("source_type") == "huggingface_dataset":
            label = f"Corpus pháp luật tham khảo — {name}"
        else:
            label = f"Thủ tục {name}" + (f" — {legal_basis}" if legal_basis else "")
        citations.append(
            Citation(
                index=index,
                procedure_id=procedure_id,
                chunk_id=chunk.chunk_id,
                section=str(chunk.metadata.get("section") or ""),
                label=label,
                excerpt=chunk.excerpt(),
                source_url=str(chunk.metadata.get("source_url") or "") or None,
            )
        )
    return citations
