from src.config import settings
from src.agents.nodes import answer
from src.services.retrieval.bm25 import Bm25Index
from src.services.retrieval.legal import retrieve_legal
from src.services.retrieval.common import RetrievedChunk, citations_from_chunks
from src.services.retrieval.legal_chunking import chunks_from_legal_record


def test_legal_chunks_keep_dataset_provenance_and_split_long_record():
    text = "Điều 1. Quy định chung. " + ("Nội dung pháp luật. " * 180) + "Điều 2. Điều khoản thi hành."

    chunks = chunks_from_legal_record("42", text, max_chars=300, overlap_chars=40)

    assert len(chunks) > 1
    assert all(chunk.metadata["source_type"] == "huggingface_dataset" for chunk in chunks)
    assert all(chunk.metadata["dataset_id"] == "YuITC/Vietnamese-Legal-Documents" for chunk in chunks)
    assert chunks[0].metadata["procedure_id"] == "legal:42"
    assert all(chunk.metadata["source_hash"] for chunk in chunks)


def test_legal_hybrid_chunking_keeps_article_clause_and_point_path():
    text = """Chương I
Quy định chung

Điều 1. Phạm vi điều chỉnh
1. Nội dung thứ nhất.
a) Điểm a.
b) Điểm b.
2. Nội dung thứ hai.

Điều 2. Điều khoản thi hành
1. Có hiệu lực từ ngày ban hành.
"""

    chunks = chunks_from_legal_record("vbpl-1", text)

    first_clause = next(chunk for chunk in chunks if chunk.metadata["clause"] == "Khoản 1")
    assert first_clause.metadata["chunking_method"] == "legal_hybrid"
    assert first_clause.metadata["chapter"] == "Chương I"
    assert first_clause.metadata["article"] == "Điều 1"
    assert first_clause.metadata["points"] == "Điểm a,Điểm b"


def test_unstructured_long_text_uses_c2_overlap_fallback():
    chunks = chunks_from_legal_record(
        "unstructured",
        "Nội dung không có đề mục. " * 300,
        fallback_max_chars=300,
        overlap_chars=30,
    )

    assert len(chunks) > 1
    assert all(chunk.metadata["chunk_type"] == "overlap_fallback" for chunk in chunks)
    assert all(chunk.metadata["fallback_strategy"] == "overlap" for chunk in chunks)
    assert all(len(chunk.content) <= 300 for chunk in chunks)


def test_legal_retrieval_uses_its_own_bm25_cache(tmp_path, monkeypatch):
    chunks = chunks_from_legal_record(
        "99",
        "Điều 12. Đăng ký thường trú được thực hiện tại cơ quan đăng ký cư trú.",
    )
    bm25_path = tmp_path / "legal.json"
    Bm25Index(chunks).save(bm25_path)
    monkeypatch.setattr(settings, "legal_bm25_index_path", str(bm25_path))

    result = retrieve_legal("đăng ký thường trú", top_k=1)

    assert result
    assert result[0].metadata["legal_record_id"] == "99"


def test_c2_vbpl_metadata_is_normalized_for_legal_citation():
    from src.services.retrieval.legal import _legal_metadata

    metadata = _legal_metadata(
        {
            "document_id": "doc_123",
            "chunk_id": "chunk_123",
            "title": "Luật Cư trú",
            "url": "https://vbpl.vn/example",
            "source_scope": "public_vbpl",
        }
    )
    citation = citations_from_chunks([RetrievedChunk(content="Điều 1", metadata=metadata)])[0]

    assert citation.procedure_id == "legal:doc_123"
    assert citation.source_url == "https://vbpl.vn/example"
    assert citation.label == "Văn bản pháp luật — Luật Cư trú"


async def test_answer_uses_legal_rag_for_unselected_legal_question(monkeypatch):
    calls: list[str] = []

    def fake_legal(query, *, top_k=None):
        calls.append(query)
        return [
            RetrievedChunk(
                content="Điều 1. Nội dung văn bản.",
                metadata={
                    "procedure_id": "legal:doc_1",
                    "procedure_name": "Luật Cư trú",
                    "chunk_id": "doc_1::0",
                    "section": "Điều 1",
                    "source_type": "legal_corpus",
                    "source_url": "https://vbpl.vn/example",
                },
            )
        ]

    monkeypatch.setattr(answer, "retrieve_legal", fake_legal)
    result = await answer.run(
        {"rewritten_query": "Luật Cư trú quy định gì?", "detected_intents": ["legal_basis"]}
    )

    assert calls == ["Luật Cư trú quy định gì?"]
    assert result["citations"][0]["label"].startswith("Văn bản pháp luật")
    assert "đối chiếu văn bản gốc" in result["reply"]
