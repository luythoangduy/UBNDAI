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


def test_content_chunks_do_not_expose_internal_condition_expression():
    chunks = retrieve("thành phần hồ sơ khai sinh")
    assert all("answers." not in chunk.content for chunk in chunks)


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


def test_short_phrase_does_not_fuzzy_match_after_diacritic_folding():
    """Cụm ≤2 token sau khi bỏ dấu không được chấm fuzzy.

    Hồi quy cho một lỗi thật: alias "chứng minh thư" của can_cuoc rút gọn thành
    {chung, minh} sau khi fold bỏ dấu và loại token chung. Câu hỏi về kết hôn
    "tụi mình định về chung một nhà, cần giấy tờ gì" chứa đúng hai token đó, cho
    procedure_coverage = 1.0 → điểm 0.80, vượt identify_min_relevance và khiến
    hệ thống CHỐT HẲN can_cuoc. Chốt nhầm thủ tục làm sai toàn bộ checklist phía
    sau nên tệ hơn nhiều so với việc thành thật hỏi lại (AGENTS.md §5).
    """
    from src.services.catalog import get_procedure
    from src.services.retrieval import _identity_score

    query = "tụi mình định về chung một nhà, cần giấy tờ gì"
    assert _identity_score(query, get_procedure("can_cuoc")) < 0.6, (
        "cụm 2 token sau fold không được vượt identify_min_relevance"
    )


def test_short_alias_still_matches_when_written_out():
    """Chặn fuzzy không được làm mất khả năng khớp chính xác."""
    from src.services.catalog import get_procedure
    from src.services.retrieval import _identity_score

    assert _identity_score("tôi mất chứng minh thư rồi", get_procedure("can_cuoc")) == 1.0


def test_short_alias_does_not_match_inside_another_word():
    """Khớp cụm phải xét ranh giới từ, không dùng substring thuần.

    Hồi quy hai lỗi thật, cả hai đều cho điểm 1.0 — tức chốt chắc chắn:

    - alias "ở nhờ" của tam_tru fold thành "o nho", nằm gọn giữa "cho nho"
      (cho nhỏ) → "cho nhỏ nhà tôi mượn giấy tờ" bị chốt tam_tru.
    - alias "cưới" của ket_hon fold thành "cuoi", trùng khít "cuối" →
      "nộp hồ sơ vào cuối năm" bị chốt ket_hon. Đây là đồng tự sau khi bỏ dấu
      nên ranh giới từ không cứu được; alias đó đã phải gỡ khỏi catalog và thay
      bằng cụm dài hơn ("đám cưới", "muốn cưới").
    """
    from src.services.catalog import get_procedure
    from src.services.retrieval import _identity_score

    assert _identity_score("cho nhỏ nhà tôi mượn giấy tờ", get_procedure("tam_tru")) < 0.6
    assert _identity_score("nộp hồ sơ vào cuối năm có được không", get_procedure("ket_hon")) < 0.6


def test_word_boundary_fix_keeps_genuine_matches():
    """Chặn substring lọt giữa từ không được làm mất ca khớp thật."""
    from src.services.catalog import get_procedure
    from src.services.retrieval import _identity_score

    assert _identity_score("tôi ở trọ cần khai báo", get_procedure("tam_tru")) == 1.0
    assert _identity_score("hai đứa tụi mình muốn cưới", get_procedure("ket_hon")) == 1.0
