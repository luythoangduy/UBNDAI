"""Bridge LangGraph guidance state into the citizen/officer workflow.

The project still has two domain models for compatibility, but they now share
one public case id and an authenticated citizen projection. This keeps the
chat checklist, document intake and officer review in one demo journey.
"""

from datetime import datetime, UTC

from src.models import Case, ChecklistItem
from src.services import cases
from src.services.cases import CaseNotFoundError
from src.services.officer_store import store


async def resolve_case_id(case_id: str | None, citizen_id: str | None) -> str:
    if case_id is None:
        # Không tạo portal-case projection ở đây: nếu lượt chat lỗi (LLM/hạ tầng),
        # case rỗng sẽ bị bỏ lại vĩnh viễn trong lịch sử công dân, luôn mang tiêu đề
        # "pending_guidance". sync_to_portal() sẽ tạo/đồng bộ projection sau khi
        # lượt chat thành công.
        case = await cases.create_from_identity(citizen_id or "anonymous")
        return case.id

    try:
        await cases.get(case_id)
        if citizen_id:
            portal_case = store.get_citizen_case(case_id, citizen_id)
            if portal_case is None:
                store.ensure_guidance_case(case_id, citizen_id)
        return case_id
    except CaseNotFoundError:
        if not citizen_id:
            raise

    portal_case = store.get_citizen_case(case_id, citizen_id)
    if portal_case is None:
        raise CaseNotFoundError(case_id)
    answers = portal_case.form_data.get("_answers", {})
    checklist = [
        ChecklistItem(requirement_code=code, status=status)
        for code, status in portal_case.checklist.items()
    ]
    timestamp = datetime.now(UTC)
    legacy_case = Case(
        id=portal_case.id,
        citizen_id=citizen_id,
        procedure_id=(
            None
            if portal_case.procedure_id == "pending_guidance"
            else portal_case.procedure_id
        ),
        answers=answers if isinstance(answers, dict) else {},
        checklist=checklist,
        form_data={
            key: value
            for key, value in portal_case.form_data.items()
            if key != "_answers"
        },
        status="collecting" if portal_case.status == "collecting" else "draft",
        created_at=portal_case.created_at or timestamp,
        updated_at=portal_case.updated_at or timestamp,
    )
    await cases.insert_exact(legacy_case)
    return case_id


async def sync_to_portal(case_id: str, citizen_id: str | None) -> None:
    if not citizen_id:
        return
    case = await cases.get(case_id)
    # Idempotent: tạo portal-case projection nếu đây là lượt thành công đầu tiên
    # (case_id có thể chưa tồn tại vì resolve_case_id không còn tạo trước).
    store.ensure_guidance_case(case_id, citizen_id, case.procedure_id)
    checklist = {item.requirement_code: item.status for item in case.checklist}
    store.sync_guidance_case(
        case_id=case.id,
        citizen_id=citizen_id,
        procedure_id=case.procedure_id,
        answers=case.answers,
        checklist=checklist,
        status=case.status,
    )
