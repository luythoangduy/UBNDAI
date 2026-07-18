"""Case persistence SQLite: I/O ngoài event loop, transaction và optimistic lock."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from contextlib import asynccontextmanager, closing
from datetime import datetime, UTC
from pathlib import Path
from collections.abc import AsyncIterator

from src.config import settings
from src.models import Case, CaseCreate, CaseUpdate, ChatHistoryMessage, ChatHistoryResponse


class CaseNotFoundError(LookupError):
    pass


class ConcurrentCaseUpdateError(RuntimeError):
    pass


_LOCKS: dict[str, asyncio.Lock] = {}
_LOCK_USERS: dict[str, int] = {}
_LOCKS_GUARD = threading.Lock()
_INITIALIZED_DATABASES: set[str] = set()
_SCHEMA_GUARD = threading.Lock()


@asynccontextmanager
async def case_lock(case_id: str) -> AsyncIterator[None]:
    """Tuần tự hoá các lượt chat cùng case trong một process."""
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(case_id, asyncio.Lock())
        _LOCK_USERS[case_id] = _LOCK_USERS.get(case_id, 0) + 1
    try:
        async with lock:
            yield
    finally:
        with _LOCKS_GUARD:
            users = _LOCK_USERS[case_id] - 1
            if users == 0:
                _LOCK_USERS.pop(case_id, None)
                _LOCKS.pop(case_id, None)
            else:
                _LOCK_USERS[case_id] = users


async def create(payload: CaseCreate) -> Case:
    now = datetime.now(UTC)
    case = Case(
        id=uuid.uuid4().hex,
        citizen_id=payload.citizen_id,
        procedure_id=payload.procedure_id,
        created_at=now,
        updated_at=now,
    )
    await asyncio.to_thread(_insert_sync, case)
    return case


async def create_from_identity(citizen_id: str) -> Case:
    return await create(CaseCreate(citizen_id=citizen_id))


async def insert_exact(case: Case) -> Case:
    """Insert a pre-built case while preserving its externally assigned id.

    The citizen/officer workflow owns public case identifiers. Guidance uses
    this helper when it needs to attach LangGraph state to an existing portal
    case instead of creating a second, disconnected record.
    """
    await asyncio.to_thread(_insert_sync, case)
    return case


async def get(case_id: str) -> Case:
    return await asyncio.to_thread(_get_sync, case_id)


async def get_owned(case_id: str, citizen_id: str) -> Case:
    """Return a case only to its citizen owner, masking ownership as not found."""
    case = await get(case_id)
    if case.citizen_id != citizen_id:
        raise CaseNotFoundError(case_id)
    return case


async def list_all() -> list[Case]:
    return await asyncio.to_thread(_list_all_sync)


async def update(case_id: str, payload: CaseUpdate) -> Case:
    async with case_lock(case_id):
        case = await get(case_id)
        return await save(case.model_copy(update=payload.model_dump(exclude_none=True)))


async def save(case: Case) -> Case:
    """Persist Case bằng optimistic locking; version tăng đúng một đơn vị."""
    updated = case.model_copy(
        update={
            "updated_at": datetime.now(UTC),
            "version": case.version + 1,
        }
    )
    await asyncio.to_thread(_update_sync, updated, case.version)
    return updated


async def commit_turn(
    case: Case,
    user_message: str,
    assistant_message: str,
    *,
    assistant_response: dict | None = None,
) -> tuple[Case, int]:
    """Atomic: cập nhật case và append cả user/assistant message."""
    updated = case.model_copy(
        update={
            "updated_at": datetime.now(UTC),
            "version": case.version + 1,
        }
    )
    assistant_message_id = await asyncio.to_thread(
        _commit_turn_sync,
        updated,
        case.version,
        user_message,
        assistant_message,
        assistant_response,
    )
    return updated, assistant_message_id


async def append_message(case_id: str, role: str, content: str) -> None:
    await asyncio.to_thread(_append_message_sync, case_id, role, content)


async def set_message_response(
    case_id: str,
    message_id: int,
    response: dict,
) -> None:
    """Attach post-commit presentation metadata without holding the case lock."""
    await asyncio.to_thread(_set_message_response_sync, case_id, message_id, response)


async def get_messages(case_id: str, *, limit: int = 20) -> list[dict]:
    return await asyncio.to_thread(_get_messages_sync, case_id, limit)


async def get_chat_history(case_id: str, citizen_id: str) -> ChatHistoryResponse:
    """Load a complete, authenticated conversation transcript for resume."""
    case = await get_owned(case_id, citizen_id)
    messages = await get_messages(case_id, limit=500)
    return ChatHistoryResponse(
        case_id=case.id,
        procedure_id=case.procedure_id,
        status=case.status,
        messages=[ChatHistoryMessage.model_validate(message) for message in messages],
    )


def _insert_sync(case: Case) -> None:
    with closing(_connect()) as connection, connection:
        connection.execute(
            "INSERT INTO cases (id, version, data) VALUES (?, ?, ?)",
            (case.id, case.version, case.model_dump_json()),
        )


def _get_sync(case_id: str) -> Case:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT data FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
    if row is None:
        raise CaseNotFoundError(case_id)
    return Case.model_validate_json(row[0])


def _list_all_sync() -> list[Case]:
    with closing(_connect()) as connection:
        rows = connection.execute("SELECT data FROM cases").fetchall()
    return [Case.model_validate_json(row[0]) for row in rows]


def _update_sync(case: Case, expected_version: int) -> None:
    with closing(_connect()) as connection, connection:
        cursor = connection.execute(
            "UPDATE cases SET version = ?, data = ? WHERE id = ? AND version = ?",
            (case.version, case.model_dump_json(), case.id, expected_version),
        )
        if cursor.rowcount != 1:
            raise ConcurrentCaseUpdateError(case.id)


def _commit_turn_sync(
    case: Case,
    expected_version: int,
    user_message: str,
    assistant_message: str,
    assistant_response: dict | None,
) -> int:
    with closing(_connect()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            cursor = connection.execute(
                "UPDATE cases SET version = ?, data = ? WHERE id = ? AND version = ?",
                (case.version, case.model_dump_json(), case.id, expected_version),
            )
            if cursor.rowcount != 1:
                raise ConcurrentCaseUpdateError(case.id)
            now = datetime.now(UTC).isoformat()
            connection.execute(
                "INSERT INTO case_messages "
                "(case_id, role, content, created_at, response_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (case.id, "user", user_message, now, None),
            )
            assistant_cursor = connection.execute(
                "INSERT INTO case_messages "
                "(case_id, role, content, created_at, response_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    case.id,
                    "assistant",
                    assistant_message,
                    now,
                    json.dumps(assistant_response, ensure_ascii=False)
                    if assistant_response is not None
                    else None,
                ),
            )
            connection.commit()
            return int(assistant_cursor.lastrowid)
        except Exception:
            connection.rollback()
            raise


def _append_message_sync(case_id: str, role: str, content: str) -> None:
    with closing(_connect()) as connection, connection:
        connection.execute(
            "INSERT INTO case_messages (case_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (case_id, role, content, datetime.now(UTC).isoformat()),
        )


def _get_messages_sync(case_id: str, limit: int) -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT id, role, content, created_at, response_json "
            "FROM case_messages WHERE case_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (case_id, limit),
        ).fetchall()
    return [
        {
            "id": message_id,
            "role": role,
            "content": content,
            "created_at": created_at,
            "response": json.loads(response_json) if response_json else None,
        }
        for message_id, role, content, created_at, response_json in reversed(rows)
    ]


def _db_path() -> Path:
    url = settings.database_url
    raw = url.split("sqlite:///", 1)[1] if url.startswith("sqlite:///") else url
    return Path(raw)


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0)
    connection.execute("PRAGMA busy_timeout = 5000")
    _ensure_schema(connection, path)
    return connection


def _ensure_schema(connection: sqlite3.Connection, path: Path) -> None:
    database_key = str(path.resolve())
    if database_key in _INITIALIZED_DATABASES:
        return
    with _SCHEMA_GUARD:
        if database_key in _INITIALIZED_DATABASES:
            return
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS cases ("
            "id TEXT PRIMARY KEY, version INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL)"
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(cases)")}
        if "version" not in columns:
            connection.execute(
                "ALTER TABLE cases ADD COLUMN version INTEGER NOT NULL DEFAULT 0"
            )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS case_messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, "
            "role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL, "
            "response_json TEXT)"
        )
        message_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(case_messages)")
        }
        if "id" not in message_columns:
            connection.execute("ALTER TABLE case_messages RENAME TO case_messages_legacy")
            connection.execute(
                "CREATE TABLE case_messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, "
                "role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL, "
                "response_json TEXT)"
            )
            connection.execute(
                "INSERT INTO case_messages (case_id, role, content, created_at) "
                "SELECT case_id, role, content, created_at FROM case_messages_legacy "
                "ORDER BY rowid"
            )
            connection.execute("DROP TABLE case_messages_legacy")
            message_columns.add("response_json")
        if "response_json" not in message_columns:
            connection.execute(
                "ALTER TABLE case_messages ADD COLUMN response_json TEXT"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_case_messages_case_id "
            "ON case_messages(case_id, id)"
        )
        connection.commit()
        _INITIALIZED_DATABASES.add(database_key)


def _set_message_response_sync(
    case_id: str,
    message_id: int,
    response: dict,
) -> None:
    with closing(_connect()) as connection, connection:
        connection.execute(
            "UPDATE case_messages SET response_json = ? "
            "WHERE id = ? AND case_id = ? AND role = 'assistant'",
            (json.dumps(response, ensure_ascii=False), message_id, case_id),
        )
