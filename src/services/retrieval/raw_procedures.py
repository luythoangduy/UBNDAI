"""Read current raw source versions for chat-only retrieval."""

from __future__ import annotations

from src.config import settings
from src.models import ProcedureDocument
from src.services.retrieval.common import RetrievedChunk, fold_ascii, tokenize
from src.services.sources.store import RawDocumentStore


def documents() -> list[ProcedureDocument]:
    return RawDocumentStore(settings.raw_documents_dir).load_current_documents()


def chunks(procedure_id: str | None = None) -> list[RetrievedChunk]:
    result: list[RetrievedChunk] = []
    for document in documents():
        if procedure_id and document.procedure_id != procedure_id:
            continue
        for section in document.sections:
            result.append(
                RetrievedChunk(
                    content=section.content,
                    metadata={
                        "procedure_id": document.procedure_id,
                        "procedure_name": document.procedure_name,
                        "section": section.section,
                        "chunk_id": f"raw::{document.procedure_id}::{section.section}::{document.source_hash}",
                        "source_url": document.source_url,
                        "source_hash": document.source_hash,
                        "retrieved_at": document.retrieved_at.isoformat(),
                        "locality_code": document.locality_code,
                        "source_type": "official_raw_procedure",
                        "review_status": "unreviewed",
                    },
                )
            )
    return result


def get_document(procedure_id: str) -> ProcedureDocument | None:
    return next((item for item in documents() if item.procedure_id == procedure_id), None)


def identity_chunks(query: str) -> list[RetrievedChunk]:
    query_folded = fold_ascii(query)
    query_tokens = set(tokenize(query))
    ranked: list[RetrievedChunk] = []
    for document in documents():
        name_folded = fold_ascii(document.procedure_name)
        name_tokens = set(tokenize(document.procedure_name))
        overlap = len(query_tokens & name_tokens)
        score = 1.0 if name_folded and name_folded in query_folded else overlap / max(len(name_tokens), 1)
        if score < 0.35:
            continue
        ranked.append(
            RetrievedChunk(
                content=f"Tên thủ tục: {document.procedure_name}",
                metadata={
                    "procedure_id": document.procedure_id,
                    "procedure_name": document.procedure_name,
                    "section": "identity",
                    "chunk_id": f"raw::{document.procedure_id}::identity::{document.source_hash}",
                    "source_url": document.source_url,
                    "source_hash": document.source_hash,
                    "source_type": "official_raw_procedure",
                    "review_status": "unreviewed",
                },
                score=round(score, 6),
            )
        )
    return sorted(ranked, key=lambda item: float(item.score or 0), reverse=True)
