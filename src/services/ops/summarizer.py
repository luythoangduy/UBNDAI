"""Tóm tắt hồ sơ + daily digest bằng LLM. Owner: Dev C.

LLM chỉ tóm tắt dữ liệu structured (Case + ValidationReport + checklist) — không quyết định,
không sinh số liệu mới. Số đếm trong digest tính bằng SQL, LLM chỉ viết lời văn.
"""

from src.models import CaseSummary, DailyDigest


async def summarize_case(case_id: str) -> CaseSummary:
    raise NotImplementedError  # TODO(C) Sprint 2


async def daily_digest(officer_id: str, date: str) -> DailyDigest:
    raise NotImplementedError  # TODO(C) Sprint 3
