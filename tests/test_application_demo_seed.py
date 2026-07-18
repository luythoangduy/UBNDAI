from pathlib import Path

import pytest

from scripts import seed_application_demo_data as seed_module
from src.config import settings
from src.services.officer_store import OfficerStore
from src.services.storage import LocalPrivateStorage


def test_showcase_seed_backfills_documents_and_ocr_idempotently(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "persistence_enabled", False)
    demo_store = OfficerStore(seed=True)
    monkeypatch.setattr(seed_module, "store", demo_store)
    monkeypatch.setattr(seed_module, "storage", LocalPrivateStorage(tmp_path), raising=False)

    assert seed_module.seed_application_demo_data() == 3

    showcase_ids = ("case-demo-ready", "case-demo-processing", "case-demo-returned")
    for case_id in showcase_ids:
        documents = [item for item in demo_store.documents.values() if item.case_id == case_id]
        assert len(documents) == 1
        fields = [item for item in demo_store.extracted_fields.values() if item.document_id == documents[0].id]
        assert len(fields) == 5

    assert seed_module.seed_application_demo_data() == 0
    assert sum(item.case_id in showcase_ids for item in demo_store.documents.values()) == 3


def test_showcase_seed_fails_when_base_ocr_is_missing(monkeypatch):
    monkeypatch.setattr(settings, "persistence_enabled", False)
    demo_store = OfficerStore(seed=True)
    source_document = next(item for item in demo_store.documents.values() if item.case_id == "case-demo-001")
    demo_store.extracted_fields = {
        key: item for key, item in demo_store.extracted_fields.items() if item.document_id != source_document.id
    }
    monkeypatch.setattr(seed_module, "store", demo_store)

    with pytest.raises(RuntimeError, match="base officer demo OCR fields"):
        seed_module.seed_application_demo_data()
