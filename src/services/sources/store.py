"""Immutable raw versions plus a small current-version manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.models import ProcedureDocument
from src.services.sources.connectors import RawDocument

DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw_documents"


class RawDocumentStore:
    def __init__(self, root: Path | str = DEFAULT_RAW_DIR) -> None:
        self.root = Path(root)

    def current_hash(self, source_url: str) -> str | None:
        manifest = self._manifest_path(source_url)
        if not manifest.is_file():
            return None
        return str(json.loads(manifest.read_text(encoding="utf-8")).get("source_hash") or "") or None

    def save(self, raw: RawDocument, document: ProcedureDocument) -> bool:
        if self.current_hash(raw.url) == raw.checksum:
            return False
        source_dir = self._source_dir(raw.url)
        version_dir = source_dir / raw.checksum.removeprefix("sha256:")
        version_dir.mkdir(parents=True, exist_ok=True)
        (version_dir / "source.bin").write_bytes(raw.body)
        (version_dir / "document.json").write_text(
            document.model_dump_json(indent=2), encoding="utf-8"
        )
        source_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path(raw.url).write_text(
            json.dumps(
                {
                    "source_url": raw.url,
                    "source_hash": raw.checksum,
                    "procedure_id": document.procedure_id,
                    "version": version_dir.name,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return True

    def load_current_documents(self) -> list[ProcedureDocument]:
        documents: list[ProcedureDocument] = []
        if not self.root.is_dir():
            return documents
        for manifest_path in self.root.glob("*/latest.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            path = manifest_path.parent / manifest["version"] / "document.json"
            if path.is_file():
                documents.append(ProcedureDocument.model_validate_json(path.read_text(encoding="utf-8")))
        return documents

    def _source_dir(self, source_url: str) -> Path:
        return self.root / hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:24]

    def _manifest_path(self, source_url: str) -> Path:
        return self._source_dir(source_url) / "latest.json"
