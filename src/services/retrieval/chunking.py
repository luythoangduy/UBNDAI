"""Chunk một Procedure thành các đoạn index được. Owner: Dev A.

Mỗi thủ tục chunk theo section: tổng quan / thành phần hồ sơ / biểu mẫu.
Metadata giữ procedure_id + section để trace citation (AGENTS.md §5).
Dùng chung cho scripts/index_procedures.py và BM25 fallback in-memory.
"""

from __future__ import annotations

from src.models import Procedure
from src.services.retrieval.common import RetrievedChunk


def chunks_from_procedure(procedure: Procedure) -> list[RetrievedChunk]:
    base_metadata = {
        "procedure_id": procedure.id,
        "procedure_name": procedure.name,
        "national_code": procedure.national_code or "",
        "agency": procedure.agency,
        "legal_basis": "; ".join(procedure.legal_basis),
        "source_url": procedure.source_url or "",
    }

    chunks = [
        _chunk(procedure, "tong_quan", _overview_text(procedure), base_metadata),
        _chunk(procedure, "thanh_phan_ho_so", _requirements_text(procedure), base_metadata),
    ]
    if procedure.form_templates:
        chunks.append(
            _chunk(procedure, "bieu_mau", _forms_text(procedure), base_metadata)
        )
    return chunks


def chunks_from_catalog(catalog: dict[str, Procedure]) -> list[RetrievedChunk]:
    chunks: list[RetrievedChunk] = []
    for procedure in catalog.values():
        chunks.extend(chunks_from_procedure(procedure))
    return chunks


def identity_chunk_from_procedure(procedure: Procedure) -> RetrievedChunk:
    """Chunk riêng cho identify; tuyệt đối không chứa hồ sơ/biểu mẫu."""
    lines = [f"Tên thủ tục: {procedure.name}"]
    if procedure.aliases:
        lines.append(f"Tên gọi khác: {'; '.join(procedure.aliases)}")
    if procedure.example_queries:
        lines.append(f"Nhu cầu ví dụ: {'; '.join(procedure.example_queries)}")
    return _chunk(procedure, "identity", "\n".join(lines), {
        "procedure_id": procedure.id,
        "procedure_name": procedure.name,
        "national_code": procedure.national_code or "",
        "agency": procedure.agency,
        "legal_basis": "; ".join(procedure.legal_basis),
        "source_url": procedure.source_url or "",
    })


def _chunk(
    procedure: Procedure, section: str, text: str, base_metadata: dict[str, str]
) -> RetrievedChunk:
    return RetrievedChunk(
        content=text,
        metadata={
            **base_metadata,
            "section": section,
            "chunk_id": f"{procedure.id}::{section}",
        },
    )


def _overview_text(procedure: Procedure) -> str:
    lines = [f"Thủ tục: {procedure.name}"]
    if procedure.national_code:
        lines.append(f"Mã thủ tục quốc gia: {procedure.national_code}")
    lines.append(f"Cơ quan thực hiện: {procedure.agency}")
    if procedure.processing_days is not None:
        lines.append(f"Thời hạn xử lý: {procedure.processing_days} ngày làm việc")
    if procedure.fee_vnd is not None:
        fee = "miễn phí" if procedure.fee_vnd == 0 else f"{procedure.fee_vnd:,}đ"
        lines.append(f"Lệ phí: {fee}")
    if procedure.legal_basis:
        lines.append(f"Căn cứ pháp lý: {'; '.join(procedure.legal_basis)}")
    return "\n".join(lines)


def _requirements_text(procedure: Procedure) -> str:
    lines = [f"Thành phần hồ sơ của thủ tục {procedure.name}:"]
    for req in procedure.requirements:
        detail = req.name
        if req.condition:
            detail += f" (điều kiện áp dụng: {req.condition})"
        if req.notes:
            detail += f" — {req.notes}"
        lines.append(f"- {detail}")
    return "\n".join(lines)


def _forms_text(procedure: Procedure) -> str:
    lines = [f"Biểu mẫu của thủ tục {procedure.name}:"]
    for template in procedure.form_templates:
        field_labels = ", ".join(f.label for f in template.fields)
        lines.append(f"- {template.name} ({template.id}): các trường {field_labels}")
    return "\n".join(lines)
