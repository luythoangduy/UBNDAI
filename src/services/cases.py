"""Case lifecycle service: CRUD + status machine. Owner: Dev C.

Status machine (chỉ chuyển qua hàm ở đây, không set status tuỳ tiện):
draft → collecting (có checklist) → ready (readiness >= ngưỡng, không blocking error)
→ submitted → processing → done | rejected; processing → need_more_info → collecting.
"""

from src.models import Case, CaseCreate, CaseUpdate


async def create(payload: CaseCreate) -> Case:
    raise NotImplementedError  # TODO(C) Sprint 1


async def get(case_id: str) -> Case:
    raise NotImplementedError  # TODO(C)


async def update(case_id: str, payload: CaseUpdate) -> Case:
    raise NotImplementedError  # TODO(C)
