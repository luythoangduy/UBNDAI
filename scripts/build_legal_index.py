"""Tải corpus pháp luật Hugging Face và build collection Chroma tách biệt.

Chunking mặc định là ``legal_hybrid`` tương thích C2: bảo toàn Chương/Mục/
Điều/Khoản/Điểm, chỉ fallback overlap 2.000/200 với văn bản dài không có cấu trúc.

Ví dụ:
    .venv\\Scripts\\python.exe scripts\\build_legal_index.py --download \\
        --embedding-provider bge-m3 --build-bm25

``hashing`` là embedding offline lexical để smoke-test/index nội bộ. Khi có
embedding semantic thực, dùng ``--embedding-provider bge-m3`` hoặc ``google``
và rebuild collection để không trộn vector khác không gian.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

from src.config import settings  # noqa: E402
from src.services.retrieval.bm25 import Bm25Index  # noqa: E402
from src.services.retrieval.chroma_client import get_chroma_persistent_client  # noqa: E402
from src.services.retrieval.embeddings import (  # noqa: E402
    get_embedding_model,
    resolve_embedding_provider,
)
from src.services.retrieval.legal_chunking import chunks_from_legal_record  # noqa: E402

SOURCES_PATH = PROJECT_ROOT / "data" / "legal_sources.json"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "legal"


def _load_source() -> dict[str, object]:
    return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))


def _download_file(*, source: dict[str, object], target_dir: Path, filename: str) -> Path:
    dataset_id = str(source["dataset_id"])
    revision = str(source["revision"])
    url = f"https://huggingface.co/datasets/{dataset_id}/resolve/{revision}/{filename}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    temp = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()
        with temp.open("wb") as output:
            for block in response.iter_bytes(chunk_size=1024 * 1024):
                output.write(block)
                digest.update(block)
        metadata = {
            "dataset_id": dataset_id,
            "revision": revision,
            "dataset_url": source["dataset_url"],
            "license": source["license"],
            "filename": filename,
            "downloaded_at": datetime.now(UTC).isoformat(),
            "sha256": digest.hexdigest(),
            "bytes": temp.stat().st_size,
            "url": str(response.url),
        }
    temp.replace(target)
    target.with_suffix(target.suffix + ".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target


def _require_pyarrow():
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise RuntimeError(
            "Thiếu pyarrow. Cài pipeline dữ liệu bằng: "
            ".\\.venv\\Scripts\\pip.exe install -e '.[legal-data]'"
        ) from exc
    return parquet


def _iter_chunks(corpus_path: Path, *, source: dict[str, object], limit: int | None):
    parquet = _require_pyarrow()
    yielded = 0
    file = parquet.ParquetFile(corpus_path)
    for batch in file.iter_batches(batch_size=256, columns=["cid", "text"]):
        rows = batch.to_pylist()
        for row in rows:
            for chunk in chunks_from_legal_record(
                row["cid"],
                row["text"],
                dataset_id=str(source["dataset_id"]),
                dataset_revision=str(source["revision"]),
            ):
                yield chunk
                yielded += 1
                if limit is not None and yielded >= limit:
                    return


def _batches(items: list, size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--download", action="store_true", help="Tải/re-tải corpus.parquet từ Hugging Face")
    parser.add_argument("--download-eval", action="store_true", help="Tải thêm test.parquet để đánh giá retrieval")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số chunk, chỉ dùng khi thử nghiệm")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--persist-dir", default=settings.chroma_persist_dir)
    parser.add_argument("--collection-name", default=settings.legal_collection)
    parser.add_argument("--bm25-path", default=settings.legal_bm25_index_path)
    parser.add_argument("--build-bm25", action="store_true")
    parser.add_argument(
        "--embedding-provider",
        default="bge-m3",
        choices=["auto", "google", "bge-m3", "hashing", "fake"],
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit phải lớn hơn 0")

    source = _load_source()
    corpus_path = args.data_dir / str(source["corpus_file"])
    if args.download or not corpus_path.is_file():
        corpus_path = _download_file(
            source=source, target_dir=args.data_dir, filename=str(source["corpus_file"])
        )
        print(f"Đã tải corpus: {corpus_path} ({corpus_path.stat().st_size:,} bytes)")
    if args.download_eval:
        eval_path = _download_file(
            source=source, target_dir=args.data_dir, filename=str(source["evaluation_file"])
        )
        print(f"Đã tải evaluation: {eval_path} ({eval_path.stat().st_size:,} bytes)")

    chunks = list(_iter_chunks(corpus_path, source=source, limit=args.limit))
    if not chunks:
        print("Corpus không có chunk hợp lệ", file=sys.stderr)
        return 1
    provider = resolve_embedding_provider(args.embedding_provider)
    model = get_embedding_model(provider)
    client = get_chroma_persistent_client(args.persist_dir)
    if client is None:
        print("chromadb chưa được cài", file=sys.stderr)
        return 1
    try:
        client.delete_collection(args.collection_name)
    except Exception:
        pass
    collection = client.create_collection(
        args.collection_name,
        metadata={
            "embedding_provider": provider,
            "dataset_id": str(source["dataset_id"]),
            "dataset_revision": str(source["revision"]),
            "source_type": "huggingface_dataset",
        },
    )
    for number, batch in enumerate(_batches(chunks, args.batch_size), start=1):
        collection.add(
            ids=[chunk.chunk_id for chunk in batch],
            documents=[chunk.content for chunk in batch],
            metadatas=[chunk.metadata for chunk in batch],
            embeddings=model.embed_documents([chunk.content for chunk in batch]),
        )
        if number % 20 == 0 or number == (len(chunks) + args.batch_size - 1) // args.batch_size:
            print(f"Đã index {min(number * args.batch_size, len(chunks)):,}/{len(chunks):,} chunks")
    if args.build_bm25:
        Bm25Index(chunks).save(args.bm25_path)
        print(f"Đã ghi BM25: {args.bm25_path}")
    print(
        f"Legal index sẵn sàng: collection={args.collection_name}, chunks={collection.count():,}, "
        f"embedding_provider={provider}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
