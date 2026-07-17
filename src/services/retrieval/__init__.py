"""Hybrid retrieval trên catalog TTHC. Owner: Dev A.

Pattern port từ C2-App-108: dense (Chroma) + sparse (BM25) hợp nhất bằng
reciprocal rank fusion. Suy giảm mềm theo môi trường:

- Chưa index Chroma → chỉ BM25.
- Chưa build cache BM25 (scripts/index_procedures.py --build-bm25)
  → BM25 in-memory dựng thẳng từ ``data/procedures/*.json``.

Nhờ vậy luồng chat chạy được ngay sau khi clone repo, không cần model/index.
Mỗi chunk giữ metadata procedure_id + section để trace citation (AGENTS.md §5).
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.config import settings
from src.models import Procedure
from src.services import catalog
from src.services.retrieval.bm25 import Bm25Index
from src.services.retrieval.chroma_client import get_chroma_persistent_client
from src.services.retrieval.chunking import (
    chunks_from_catalog,
    chunks_from_procedure,
    identity_chunk_from_procedure,
)
from src.services.retrieval.common import (
    NO_SOURCE_WARNING,
    RetrievedChunk,
    citations_from_chunks,
    reciprocal_rank_fusion,
)
from src.services.retrieval.embeddings import get_embedding_model

__all__ = [
    "NO_SOURCE_WARNING",
    "RetrievedChunk",
    "chunks_from_procedure",
    "citations_from_chunks",
    "reset_caches",
    "retrieve",
    "retrieve_procedure_identity",
]

logger = logging.getLogger(__name__)

_BM25_CACHE: dict[str, Bm25Index] = {}


def retrieve(
    query: str,
    *,
    top_k: int | None = None,
    procedure_id: str | None = None,
) -> list[RetrievedChunk]:
    """Entrypoint duy nhất cho các node agent: trả về chunks đã fuse, tốt nhất trước."""
    limit = top_k or settings.retrieval_top_k
    if procedure_id:
        procedure = catalog.get_procedure(procedure_id)
        if procedure is None:
            return []
        return Bm25Index(chunks_from_procedure(procedure)).search(query, top_k=limit)
    sparse = _bm25_index().search(query, top_k=limit * 2)
    dense = _dense_search(query, top_k=limit * 2)
    if dense and sparse:
        fused = reciprocal_rank_fusion([dense, sparse])
    else:
        fused = dense or sparse
    return fused[:limit]


_IDENTITY_GENERIC_TOKENS = {
    "toi", "can", "muon", "lam", "xin", "thu", "tuc", "dang", "ky",
    "giay", "to", "cho", "con", "be", "moi", "the", "nao", "gi", "ho",
    "so", "va", "cua", "mot", "viec", "gio",
}


def retrieve_procedure_identity(query: str) -> list[RetrievedChunk]:
    """Search identity metadata trên cùng thang điểm lexical [0, 1]."""
    ranked: list[RetrievedChunk] = []
    for procedure in catalog.load_catalog().values():
        score = _identity_score(query, procedure)
        if score <= 0:
            continue
        chunk = identity_chunk_from_procedure(procedure)
        ranked.append(
            RetrievedChunk(content=chunk.content, metadata=chunk.metadata, score=score)
        )
    ranked.sort(key=lambda chunk: float(chunk.score or 0), reverse=True)
    return ranked


def _identity_score(query: str, procedure: Procedure) -> float:
    from src.services.retrieval.common import fold_ascii, tokenize

    folded_query = fold_ascii(query)
    if any(
        fold_ascii(keyword) in folded_query
        for keyword in getattr(procedure, "negative_keywords", [])
    ):
        return 0.0
    query_tokens = set(tokenize(query)) - _IDENTITY_GENERIC_TOKENS
    if not query_tokens:
        return 0.0
    phrases = [
        getattr(procedure, "name", ""),
        *getattr(procedure, "aliases", []),
        *getattr(procedure, "example_queries", []),
    ]
    best = 0.0
    for phrase in phrases:
        folded_phrase = fold_ascii(phrase)
        phrase_tokens = set(tokenize(phrase)) - _IDENTITY_GENERIC_TOKENS
        if not phrase_tokens:
            continue
        if folded_phrase in folded_query:
            return 1.0
        best = max(best, len(query_tokens & phrase_tokens) / len(phrase_tokens))
    return round(best, 6)


def reset_caches() -> None:
    """Cho tests: xoá cache BM25/catalog sau khi đổi settings."""
    _BM25_CACHE.clear()
    catalog.clear_cache()


def _bm25_index() -> Bm25Index:
    cache_path = Path(settings.bm25_index_path)
    if cache_path.is_file():
        key = f"file:{cache_path.resolve()}:{cache_path.stat().st_mtime_ns}"
        if key not in _BM25_CACHE:
            _BM25_CACHE.clear()
            _BM25_CACHE[key] = Bm25Index.load(cache_path)
        return _BM25_CACHE[key]
    if "catalog" not in _BM25_CACHE:
        _BM25_CACHE["catalog"] = Bm25Index(chunks_from_catalog(catalog.load_catalog()))
    return _BM25_CACHE["catalog"]


def _dense_search(query: str, *, top_k: int) -> list[RetrievedChunk]:
    try:
        client = get_chroma_persistent_client(settings.chroma_persist_dir)
        if client is None:
            return []
        try:
            collection = client.get_collection(settings.procedures_collection)
        except Exception:  # collection chưa index
            return []
        if collection.count() == 0:
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
        chunks = []
        for index, content in enumerate(documents):
            metadata = dict(metadatas[index] or {}) if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else None
            score = (1.0 - float(distance)) if distance is not None else None
            chunks.append(RetrievedChunk(content=content, metadata=metadata, score=score))
        return chunks
    except Exception:
        logger.warning("Dense retrieval lỗi — fallback BM25-only", exc_info=True)
        return []
