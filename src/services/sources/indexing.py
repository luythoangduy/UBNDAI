"""Incrementally upsert changed raw sections into the dense procedure index."""

from src.config import settings
from src.models import ProcedureDocument
from src.services.retrieval.chroma_client import get_chroma_persistent_client
from src.services.retrieval.common import RetrievedChunk
from src.services.retrieval.embeddings import get_embedding_model, resolve_embedding_provider


def index_document(document: ProcedureDocument) -> int:
    client = get_chroma_persistent_client(settings.chroma_persist_dir)
    if client is None:
        raise RuntimeError("chromadb chưa được cài")
    try:
        collection = client.get_collection(settings.procedures_collection)
        provider = str((collection.metadata or {}).get("embedding_provider") or "")
    except Exception:
        provider = resolve_embedding_provider(settings.embedding_provider)
        collection = client.create_collection(
            settings.procedures_collection,
            metadata={"embedding_provider": provider},
        )
    model = get_embedding_model(provider)
    chunks = [
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
        for section in document.sections
    ]
    existing = collection.get(
        where={"procedure_id": document.procedure_id},
        include=["metadatas"],
    )
    stale_ids = [
        item_id
        for item_id, metadata in zip(
            existing.get("ids") or [], existing.get("metadatas") or [], strict=False
        )
        if (metadata or {}).get("source_type") == "official_raw_procedure"
    ]
    if stale_ids:
        collection.delete(ids=stale_ids)
    if not chunks:
        return 0
    embeddings = model.embed_documents([chunk.content for chunk in chunks])
    collection.upsert(
        ids=[f"raw::{document.procedure_id}::{chunk.metadata['section']}" for chunk in chunks],
        documents=[chunk.content for chunk in chunks],
        metadatas=[chunk.metadata for chunk in chunks],
        embeddings=embeddings,
    )
    return len(chunks)
