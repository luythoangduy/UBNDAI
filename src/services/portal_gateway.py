"""Adapter handoff sang cổng dịch vụ công. Owner: Dev C.

MVP: mock — sinh biên nhận giả lập, chuyển Case sang 'submitted'.
Giữ interface hẹp để thay bằng API cổng DVC thật sau này mà không sửa caller.
Chặn submit khi ValidationReport còn blocking error hoặc readiness < ngưỡng.
"""

from src.models import Case


async def submit(case: Case) -> Case:
    raise NotImplementedError  # TODO(C) Sprint 3
