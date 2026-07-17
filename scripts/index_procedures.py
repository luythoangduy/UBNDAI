"""Index catalog thủ tục vào Chroma (+ tuỳ chọn BM25 cache). Owner: Dev A.

Sửa từ C2-App-108/scripts/index_legal_corpus.py. Mỗi thủ tục chunk theo:
tổng quan / thành phần hồ sơ / biểu mẫu — giữ metadata procedure_id + section
cho citation. Provider embedding được ghi vào metadata collection để lúc query
dùng đúng model.

Usage:
    python scripts/index_procedures.py --source data/procedures \
        --collection-name tthc_procedures --build-bm25
    python scripts/index_procedures.py --embedding-provider fake   # dev/test nhanh
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Console Windows mặc định cp1252 không in được tiếng Việt
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

from src.config import settings  # noqa: E402
from src.services.catalog import load_catalog  # noqa: E402
from src.services.retrieval.bm25 import Bm25Index  # noqa: E402
from src.services.retrieval.chroma_client import get_chroma_persistent_client  # noqa: E402
from src.services.retrieval.chunking import chunks_from_catalog  # noqa: E402
from src.services.retrieval.embeddings import (  # noqa: E402
    get_embedding_model,
    resolve_embedding_provider,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="data/procedures")
    parser.add_argument("--persist-dir", default=settings.chroma_persist_dir)
    parser.add_argument("--collection-name", default=settings.procedures_collection)
    parser.add_argument(
        "--embedding-provider",
        default=settings.embedding_provider,
        choices=["auto", "google", "bge-m3", "fake"],
    )
    parser.add_argument(
        "--build-bm25",
        action="store_true",
        help=f"Ghi thêm cache BM25 ra {settings.bm25_index_path}",
    )
    parser.add_argument("--bm25-path", default=settings.bm25_index_path)
    args = parser.parse_args()

    catalog = load_catalog(args.source)
    chunks = chunks_from_catalog(catalog)
    if not chunks:
        print(f"Không có thủ tục nào trong {args.source}", file=sys.stderr)
        return 1
    print(f"Catalog: {len(catalog)} thủ tục → {len(chunks)} chunks")

    provider = resolve_embedding_provider(args.embedding_provider)
    model = get_embedding_model(provider)
    embeddings = model.embed_documents([chunk.content for chunk in chunks])
    print(f"Embedded bằng provider '{provider}' (dim={len(embeddings[0])})")

    client = get_chroma_persistent_client(args.persist_dir)
    if client is None:
        print("chromadb chưa cài — bỏ qua dense index", file=sys.stderr)
        return 1
    try:
        client.delete_collection(args.collection_name)
    except Exception:
        pass
    collection = client.create_collection(
        args.collection_name, metadata={"embedding_provider": provider}
    )
    collection.add(
        ids=[chunk.chunk_id for chunk in chunks],
        documents=[chunk.content for chunk in chunks],
        metadatas=[chunk.metadata for chunk in chunks],
        embeddings=embeddings,
    )
    print(
        f"Đã index {collection.count()} chunks vào "
        f"'{args.collection_name}' ({args.persist_dir})"
    )

    if args.build_bm25:
        Bm25Index(chunks).save(args.bm25_path)
        print(f"Đã ghi BM25 cache: {args.bm25_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
