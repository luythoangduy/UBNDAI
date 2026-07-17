import hashlib
import json
from datetime import datetime, timezone

import pytest

from src.models import ProcedureDocument, ProcedureSection
from src.services.sources.connectors import (
    DvcNationalConnector,
    ProcedureConnector,
    RawDocument,
)
from src.services.sources.pipeline import sync_connector
from src.services.sources.store import RawDocumentStore
from src.config import settings
from src.services import retrieval


def _raw(body: bytes, url: str = "https://dichvucong.gov.vn/detail?ma_thu_tuc=1.999999") -> RawDocument:
    return RawDocument(
        url=url,
        content_type="text/html",
        body=body,
        retrieved_at=datetime.now(timezone.utc),
        checksum=f"sha256:{hashlib.sha256(body).hexdigest()}",
    )


@pytest.mark.asyncio
async def test_dvc_connector_extracts_known_sections_with_provenance():
    raw = _raw(
        b"<html><title>Thu tuc cap ban sao</title><body><p>Tong quan</p>"
        b"<h2>Thanh phan ho so</h2><p>To khai theo mau.</p>"
        b"<h2>Thoi han giai quyet</h2><p>03 ngay lam viec.</p></body></html>"
    )
    connector = DvcNationalConnector([], rate_limit_seconds=0)

    document = await connector.extract(raw)

    assert document.procedure_id == "1.999999"
    by_section = {section.section: section for section in document.sections}
    assert "To khai theo mau." in by_section["thanh_phan_ho_so"].content
    assert by_section["thoi_han"].source_hash == raw.checksum
    assert by_section["thoi_han"].source_url == raw.url


def test_raw_store_is_incremental_and_keeps_immutable_versions(tmp_path):
    store = RawDocumentStore(tmp_path)
    first = _raw(b"<p>v1</p>")
    first_doc = _document(first)
    assert store.save(first, first_doc) is True
    assert store.save(first, first_doc) is False

    second = _raw(b"<p>v2</p>")
    assert store.save(second, _document(second)) is True
    assert store.current_hash(second.url) == second.checksum
    assert len(list(next(tmp_path.iterdir()).glob("*/document.json"))) == 2


def test_raw_sections_are_searchable_before_catalog_approval():
    store = RawDocumentStore(settings.raw_documents_dir)
    raw = _raw(b"<p>v1</p>")
    store.save(raw, _document(raw))
    retrieval.reset_caches()

    identities = retrieval.retrieve_procedure_identity("thủ tục thử nghiệm")
    contents = retrieval.retrieve("nội dung chính thức", procedure_id="1.999999")

    assert identities[0].procedure_id == "1.999999"
    assert contents[0].metadata["review_status"] == "unreviewed"
    assert contents[0].metadata["source_hash"] == raw.checksum


class _FakeConnector(ProcedureConnector):
    def __init__(self, raw: RawDocument) -> None:
        self.raw = raw

    async def discover(self) -> list[str]:
        return [self.raw.url]

    async def fetch(self, url: str) -> RawDocument:
        return self.raw

    async def extract(self, document: RawDocument) -> ProcedureDocument:
        return _document(document)


@pytest.mark.asyncio
async def test_sync_writes_chat_ready_review_candidate_and_skips_unchanged(tmp_path):
    raw = _raw(b"<p>Noi dung chinh thuc</p>")
    store = RawDocumentStore(tmp_path / "raw")
    review = tmp_path / "review"

    first = await sync_connector(
        _FakeConnector(raw), store=store, review_dir=review, run_llm=False
    )
    second = await sync_connector(
        _FakeConnector(raw), store=store, review_dir=review, run_llm=False
    )

    assert first.changed == 1 and first.review_items == ["1.999999"]
    assert second.unchanged == 1 and second.changed == 0
    candidate = json.loads((review / "1.999999.json").read_text(encoding="utf-8"))
    assert candidate["status"] == "needs_review"
    assert candidate["quality"]["chat_ready"] is True
    assert candidate["quality"]["workflow_ready"] is False


def _document(raw: RawDocument) -> ProcedureDocument:
    section = ProcedureSection(
        procedure_id="1.999999",
        procedure_name="Thủ tục thử nghiệm",
        section="tong_quan",
        content="Nội dung chính thức",
        source_url=raw.url,
        retrieved_at=raw.retrieved_at,
        source_hash=raw.checksum,
    )
    return ProcedureDocument(
        procedure_id=section.procedure_id,
        procedure_name=section.procedure_name,
        source_url=raw.url,
        retrieved_at=raw.retrieved_at,
        source_hash=raw.checksum,
        sections=[section],
    )
