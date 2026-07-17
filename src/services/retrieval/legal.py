"""Hybrid retrieval cho corpus pháp luật tải từ nguồn dữ liệu đã khai báo.

Collection này tách biệt hoàn toàn với ``tthc_procedures``: nó bổ sung căn cứ
pháp lý cho chat, không thay thế dữ liệu thủ tục đã được cơ quan công bố.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.config import settings
from src.services.retrieval.bm25 import Bm25Index
from src.services.retrieval.chroma_client import get_chroma_persistent_client
from src.services.retrieval.common import RetrievedChunk, reciprocal_rank_fusion
from src.services.retrieval.embeddings import get_embedding_model

logger = logging.getLogger(__name__)

_BM25_CACHE: dict[str, Bm25Index] = {}


def retrieve_legal(query: str, *, top_k: int | None = None) -> list[RetrievedChunk]:
    """Trả về các đoạn luật đã index, kèm metadata provenance để tạo citation."""
    limit = top_k or settings.retrieval_top_k
    sparse = _bm25_index().search(query, top_k=limit * 2) if _has_bm25() else []
    dense = _dense_search(query, top_k=limit * 2)
    if dense and sparse:
        return reciprocal_rank_fusion([dense, sparse])[:limit]
    return (dense or sparse)[:limit]


def reset_caches() -> None:
    _BM25_CACHE.clear()


def _has_bm25() -> bool:
    return bool(settings.legal_bm25_index_path) and Path(
        settings.legal_bm25_index_path
    ).is_file()


def _bm25_index() -> Bm25Index:
    path = Path(settings.legal_bm25_index_path)
    key = f"file:{path.resolve()}:{path.stat().st_mtime_ns}"
    if key not in _BM25_CACHE:
        _BM25_CACHE.clear()
        _BM25_CACHE[key] = Bm25Index.load(path)
    return _BM25_CACHE[key]


def _dense_search(query: str, *, top_k: int) -> list[RetrievedChunk]:
    try:
        persist_dir = settings.legal_chroma_persist_dir or settings.chroma_persist_dir
        client = get_chroma_persistent_client(persist_dir)
        if client is None:
            return []
        try:
            collection = client.get_collection(settings.legal_collection)
        except Exception:
            return []
        provider = (collection.metadata or {}).get("embedding_provider")
        embedding = get_embedding_model(provider).embed_query(query)
        result = collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            RetrievedChunk(
                content=content,
                metadata=_legal_metadata(
                    dict(metadatas[index] or {}) if index < len(metadatas) else {}
                ),
                score=(1.0 - float(distances[index])) if index < len(distances) else None,
            )
            for index, content in enumerate(documents)
        ]
    except Exception:
        logger.warning("Legal dense retrieval lỗi — fallback BM25-only", exc_info=True)
        return []


def _legal_metadata(metadata: dict[str, object]) -> dict[str, object]:
    """Chuẩn hoá metadata của các legal corpus để citation luôn hoạt động.

    C2 VBPL dùng ``document_id/title/url`` thay vì contract catalog
    ``procedure_id/procedure_name/source_url``. Chuyển đổi tại ranh giới
    retrieval giúp index được tái sử dụng read-only, không sửa dữ liệu gốc.
    """
    normalized = dict(metadata)
    document_id = str(
        normalized.get("document_id")
        or normalized.get("legal_number")
        or normalized.get("chunk_id")
        or "unknown"
    )
    normalized.setdefault("procedure_id", f"legal:{document_id}")
    normalized.setdefault(
        "procedure_name",
        str(normalized.get("citation_label") or normalized.get("title") or document_id),
    )
    normalized.setdefault("source_url", str(normalized.get("url") or ""))
    normalized.setdefault("section", str(normalized.get("article") or "văn_bản_pháp_luật"))
    normalized.setdefault("source_type", "legal_corpus")
    return normalized
