"""Retrieval hybrid: BM25 fallback in-memory, RRF, metadata citation."""

from src.services.retrieval import citations_from_chunks, retrieve
from src.services.retrieval.common import RetrievedChunk, reciprocal_rank_fusion


def test_retrieve_finds_procedure_without_any_index():
    """Không Chroma, không BM25 cache → vẫn truy xuất được từ catalog."""
    chunks = retrieve("đăng ký khai sinh cho con mới sinh")
    assert chunks, "BM25 in-memory phải trả kết quả"
    assert chunks[0].procedure_id == "khai_sinh"
    for chunk in chunks:
        assert chunk.metadata["procedure_id"]
        assert chunk.metadata["section"]
        assert chunk.metadata["chunk_id"]


def test_retrieve_matches_diacritic_insensitive():
    chunks = retrieve("dang ky khai sinh")
    assert chunks and chunks[0].procedure_id == "khai_sinh"


def test_retrieve_returns_empty_for_gibberish():
    assert retrieve("xyzt qwerty lorem") == []


def test_citations_map_one_to_one_to_chunks_and_carry_source():
    chunks = retrieve("thành phần hồ sơ khai sinh")
    citations = citations_from_chunks(chunks)
    assert len(citations) == len(chunks)
    citation = citations[0]
    assert citation.index == 1
    assert citation.procedure_id == "khai_sinh"
    assert citation.chunk_id == chunks[0].chunk_id
    assert citation.section == chunks[0].metadata["section"]
    assert citation.excerpt
    assert "Đăng ký khai sinh" in citation.label
    assert "Luật Hộ tịch 2014" in citation.label
    assert citation.source_url and citation.source_url.startswith("https://")


def test_reciprocal_rank_fusion_prefers_chunk_in_both_lists():
    a = RetrievedChunk(content="a", metadata={"chunk_id": "a"})
    b = RetrievedChunk(content="b", metadata={"chunk_id": "b"})
    c = RetrievedChunk(content="c", metadata={"chunk_id": "c"})
    fused = reciprocal_rank_fusion([[a, b], [c, b]])
    assert fused[0].metadata["chunk_id"] == "b"
    assert len(fused) == 3
