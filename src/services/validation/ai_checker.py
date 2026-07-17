"""AI cross-check mâu thuẫn ngữ nghĩa giữa các giấy tờ. Owner: Dev B.

Chỉ sinh warning/info — ValidationIssue tự chặn error từ source='ai'.
Input: field_map các giấy tờ + form_data. Output structured (JSON mode) → ValidationIssue.
Ví dụ bắt được: tên khác dấu giữa CCCD và giấy chứng sinh, địa chỉ không nhất quán.
LLM lỗi/timeout → trả [] (validation không được chết vì AI checker).
"""

from src.models import Case, ExtractedDocument, ValidationIssue


async def run(case: Case, documents: list[ExtractedDocument]) -> list[ValidationIssue]:
    raise NotImplementedError  # TODO(B) Sprint 2
