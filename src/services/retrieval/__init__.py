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
import re
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
from src.services.retrieval.raw_procedures import chunks as raw_chunks
from src.services.retrieval.raw_procedures import identity_chunks as raw_identity_chunks
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
        available = chunks_from_procedure(procedure) if procedure else raw_chunks(procedure_id)
        sparse = Bm25Index(available).search(query, top_k=limit * 2)
        dense = _dense_search(query, top_k=limit * 2, procedure_id=procedure_id)
        return (reciprocal_rank_fusion([dense, sparse]) if dense and sparse else dense or sparse)[:limit]
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
    by_procedure = {chunk.procedure_id: chunk for chunk in ranked}
    for chunk in raw_identity_chunks(query):
        existing = by_procedure.get(chunk.procedure_id)
        if existing is None or float(chunk.score or 0) > float(existing.score or 0):
            by_procedure[chunk.procedure_id] = chunk
    ranked = list(by_procedure.values())
    ranked.sort(key=lambda chunk: float(chunk.score or 0), reverse=True)
    return ranked


def _identity_score(query: str, procedure: Procedure) -> float:
    from src.services.retrieval.common import fold_ascii, tokenize

    folded_query = fold_ascii(query)
    query_tokens = set(tokenize(query)) - _IDENTITY_GENERIC_TOKENS
    if not query_tokens:
        return 0.0
    explicit_phrases = [procedure.name, *procedure.aliases]
    if any(
        fold_ascii(phrase) in folded_query
        and not _phrase_is_negated(folded_query, fold_ascii(phrase))
        for phrase in explicit_phrases
    ):
        return 1.0
    signature_match = any(
        {fold_ascii(token) for token in group} <= query_tokens
        for group in procedure.required_token_groups
    )
    signature_negated = any(
        _phrase_is_negated(folded_query, " ".join(fold_ascii(token) for token in group))
        for group in procedure.required_token_groups
    )
    if signature_match and not signature_negated:
        return 0.95
    if any(
        fold_ascii(keyword) in folded_query
        and not _phrase_is_negated(folded_query, fold_ascii(keyword))
        for keyword in procedure.negative_keywords
    ):
        return 0.0
    phrases = [*explicit_phrases, *procedure.example_queries]
    best = 0.0
    for phrase in phrases:
        folded_phrase = fold_ascii(phrase)
        phrase_tokens = set(tokenize(phrase)) - _IDENTITY_GENERIC_TOKENS
        if len(phrase_tokens) < 2:
            continue
        if folded_phrase in folded_query:
            return 1.0
        overlap = len(query_tokens & phrase_tokens)
        procedure_coverage = overlap / len(phrase_tokens)
        query_coverage = overlap / len(query_tokens)
        best = max(best, 0.7 * procedure_coverage + 0.3 * query_coverage)
    return round(best, 6)


def _phrase_is_negated(text: str, phrase: str) -> bool:
    escaped = re.escape(phrase)
    return bool(
        re.search(
            rf"\b(?:khong\s+(?:phai|hoi|lam)|bo\s+qua)"
            rf"(?:\s+\w+){{0,3}}\s+{escaped}\b",
            text,
        )
    )


def reset_caches() -> None:
    """Cho tests: xoá cache BM25/catalog sau khi đổi settings."""
    _BM25_CACHE.clear()
    catalog.clear_cache()


def _bm25_index() -> Bm25Index:
    cache_path = Path(settings.bm25_index_path)
    raw = raw_chunks()
    raw_fingerprint = ":".join(
        sorted(str(chunk.metadata.get("source_hash") or "") for chunk in raw)
    )
    if cache_path.is_file():
        key = f"file:{cache_path.resolve()}:{cache_path.stat().st_mtime_ns}:{raw_fingerprint}"
        if key not in _BM25_CACHE:
            _BM25_CACHE.clear()
            cached = Bm25Index.load(cache_path)
            _BM25_CACHE[key] = Bm25Index([*cached.chunks, *raw])
        return _BM25_CACHE[key]
    key = f"catalog:{raw_fingerprint}"
    if key not in _BM25_CACHE:
        _BM25_CACHE.clear()
        _BM25_CACHE[key] = Bm25Index(
            [*chunks_from_catalog(catalog.load_catalog()), *raw]
        )
    return _BM25_CACHE[key]


def _dense_search(
    query: str, *, top_k: int, procedure_id: str | None = None
) -> list[RetrievedChunk]:
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
        query_kwargs = {
            "query_embeddings": [embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if procedure_id:
            query_kwargs["where"] = {"procedure_id": procedure_id}
        result = collection.query(
            **query_kwargs,
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
