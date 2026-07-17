"""Case lifecycle service: CRUD + status machine. Owner: Dev C.

Status machine (chỉ chuyển qua hàm ở đây, không set status tuỳ tiện):
draft → collecting (có checklist) → ready (readiness >= ngưỡng, không blocking error)
→ submitted → processing → done | rejected; processing → need_more_info → collecting.

MVP tạm của Dev A để unblock luồng chat (Sprint 1): store SQLite (stdlib sqlite3,
Case serialize JSON) + bảng case_messages cho lịch sử hội thoại. Dev C thay bằng
SQLAlchemy/Alembic port từ C2-App-108 mà không đổi chữ ký các hàm public.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings
from src.models import Case, CaseCreate, CaseUpdate


class CaseNotFoundError(LookupError):
    pass


async def create(payload: CaseCreate) -> Case:
    now = datetime.now(timezone.utc)
    case = Case(
        id=uuid.uuid4().hex,
        citizen_id=payload.citizen_id,
        procedure_id=payload.procedure_id,
        created_at=now,
        updated_at=now,
    )
    _upsert(case)
    return case


async def get(case_id: str) -> Case:
    row = _connect().execute(
        "SELECT data FROM cases WHERE id = ?", (case_id,)
    ).fetchone()
    if row is None:
        raise CaseNotFoundError(case_id)
    return Case.model_validate_json(row[0])


async def update(case_id: str, payload: CaseUpdate) -> Case:
    case = await get(case_id)
    changes = payload.model_dump(exclude_none=True)
    case = case.model_copy(update=changes)
    return await save(case)


async def save(case: Case) -> Case:
    """Persist toàn bộ Case (dùng nội bộ bởi agent sau mỗi lượt chat)."""
    case = case.model_copy(update={"updated_at": datetime.now(timezone.utc)})
    _upsert(case)
    return case


async def append_message(case_id: str, role: str, content: str) -> None:
    _connect().execute(
        "INSERT INTO case_messages (case_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (case_id, role, content, datetime.now(timezone.utc).isoformat()),
    )


async def get_messages(case_id: str, *, limit: int = 20) -> list[dict[str, str]]:
    rows = _connect().execute(
        "SELECT role, content FROM case_messages WHERE case_id = ? "
        "ORDER BY rowid DESC LIMIT ?",
        (case_id, limit),
    ).fetchall()
    return [{"role": role, "content": content} for role, content in reversed(rows)]


def _upsert(case: Case) -> None:
    _connect().execute(
        "INSERT INTO cases (id, data) VALUES (?, ?) "
        "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
        (case.id, case.model_dump_json()),
    )


def _db_path() -> Path:
    url = settings.database_url
    raw = url.split("sqlite:///", 1)[1] if url.startswith("sqlite:///") else url
    return Path(raw)


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, data TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS case_messages ("
        "case_id TEXT NOT NULL, role TEXT NOT NULL, "
        "content TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    return connection
