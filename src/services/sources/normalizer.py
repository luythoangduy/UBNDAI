"""LLM structured extraction produces review candidates, never published records."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from src.models import NormalizedProcedureMetadata, ProcedureDocument
from src.services.llm import get_llm, llm_is_configured

SYSTEM_PROMPT = """Bạn trích xuất metadata thủ tục hành chính từ nguồn chính thức.
Mọi giá trị phải có URL, trích đoạn nguyên văn và confidence. Không suy đoán.
Nếu nguồn không nêu một trường, để trống. Kết quả chỉ là ứng viên chờ cán bộ duyệt."""


async def normalize(document: ProcedureDocument) -> NormalizedProcedureMetadata | None:
    if not llm_is_configured():
        return None
    source = "\n\n".join(
        f"[{section.section}]\n{section.content}" for section in document.sections
    )
    llm = get_llm(temperature=0).with_structured_output(NormalizedProcedureMetadata)
    return await llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"procedure_id={document.procedure_id}\n"
                    f"source_url={document.source_url}\n\n{source}"
                )
            ),
        ]
    )
