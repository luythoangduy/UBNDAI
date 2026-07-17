"""Auto-assignment hồ sơ cho cán bộ. Owner: Dev C.

Round-robin có trọng số: lọc officer theo lĩnh vực thủ tục, chọn người ít việc nhất.
Priority: +N nếu có ChecklistItem 'uncertain' hoặc needs_human_review (AI không chắc → người xem sớm).
reason luôn ghi rõ để giải thích được với cán bộ.
"""

from src.models import Assignment


async def auto_assign(case_id: str) -> Assignment:
    raise NotImplementedError  # TODO(C) Sprint 1
