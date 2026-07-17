"""Incremental discover → fetch → extract → candidate pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.models import SyncResult
from src.config import settings
from src.services.sources.connectors import ProcedureConnector
from src.services.sources.normalizer import normalize
from src.services.sources.quality import evaluate
from src.services.sources.store import RawDocumentStore

logger = logging.getLogger(__name__)


async def sync_connector(
    connector: ProcedureConnector,
    *,
    store: RawDocumentStore | None = None,
    review_dir: Path | str | None = None,
    run_llm: bool = True,
    index_dense: bool = False,
) -> SyncResult:
    raw_store = store or RawDocumentStore(settings.raw_documents_dir)
    result = SyncResult()
    urls = await connector.discover()
    result.discovered = len(urls)
    candidates_dir = Path(review_dir or settings.procedure_candidates_dir)
    for url in urls:
        try:
            raw = await connector.fetch(url)
            if raw_store.current_hash(raw.url) == raw.checksum:
                result.unchanged += 1
                continue
            document = await connector.extract(raw)
            raw_store.save(raw, document)
            if index_dense:
                try:
                    from src.services.sources.indexing import index_document

                    index_document(document)
                except Exception:
                    # Raw + sparse chat remains available; dense is a soft dependency.
                    logger.warning("Không thể cập nhật dense index cho %s", url, exc_info=True)
            normalized = await normalize(document) if run_llm else None
            report = evaluate(document, normalized)
            result.changed += 1
            if report.chat_ready:
                result.review_items.append(document.procedure_id)
            candidates_dir.mkdir(parents=True, exist_ok=True)
            (candidates_dir / f"{_safe_id(document.procedure_id)}.json").write_text(
                json.dumps(
                    {
                        "status": "needs_review",
                        "document": document.model_dump(mode="json"),
                        "normalized": normalized.model_dump(mode="json") if normalized else None,
                        "quality": report.model_dump(mode="json"),
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
        except Exception:
            result.failed += 1
            logger.exception("Không thể đồng bộ nguồn %s", url)
    return result


def _safe_id(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return safe[:120] or "unknown"
