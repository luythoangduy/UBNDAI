"""Durable guidance-case persistence with optimistic locking."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, UTC
from collections.abc import AsyncIterator

from sqlalchemy import select, update as sql_update

from src.config import settings
from src.models import Case, CaseCreate, CaseUpdate, ChatHistoryMessage, ChatHistoryResponse
from src.services.persistence import (
    Base,
    Database,
    GuidanceCaseORM,
    GuidanceMessageORM,
)


class CaseNotFoundError(LookupError):
    pass


class ConcurrentCaseUpdateError(RuntimeError):
    pass


_LOCKS: dict[str, asyncio.Lock] = {}
_LOCK_USERS: dict[str, int] = {}
_LOCKS_GUARD = threading.Lock()
_DATABASES: dict[str, Database] = {}
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
    database = _database()
    with database.session() as session:
        session.add(
            GuidanceCaseORM(
                id=case.id,
                version=case.version,
                data=case.model_dump_json(),
            )
        )
        session.commit()


def _get_sync(case_id: str) -> Case:
    database = _database()
    with database.session() as session:
        row = session.get(GuidanceCaseORM, case_id)
    if row is None:
        raise CaseNotFoundError(case_id)
    return Case.model_validate_json(row.data)


def _list_all_sync() -> list[Case]:
    database = _database()
    with database.session() as session:
        rows = session.scalars(select(GuidanceCaseORM)).all()
    return [Case.model_validate_json(row.data) for row in rows]


def _update_sync(case: Case, expected_version: int) -> None:
    database = _database()
    with database.session() as session:
        result = session.execute(
            sql_update(GuidanceCaseORM)
            .where(
                GuidanceCaseORM.id == case.id,
                GuidanceCaseORM.version == expected_version,
            )
            .values(version=case.version, data=case.model_dump_json())
        )
        if result.rowcount != 1:
            raise ConcurrentCaseUpdateError(case.id)
        session.commit()


def _commit_turn_sync(
    case: Case,
    expected_version: int,
    user_message: str,
    assistant_message: str,
    assistant_response: dict | None,
) -> int:
    database = _database()
    with database.session() as session:
        result = session.execute(
            sql_update(GuidanceCaseORM)
            .where(
                GuidanceCaseORM.id == case.id,
                GuidanceCaseORM.version == expected_version,
            )
            .values(version=case.version, data=case.model_dump_json())
        )
        if result.rowcount != 1:
            raise ConcurrentCaseUpdateError(case.id)
        now = datetime.now(UTC)
        session.add(
            GuidanceMessageORM(
                case_id=case.id,
                role="user",
                content=user_message,
                created_at=now,
            )
        )
        assistant_row = GuidanceMessageORM(
            case_id=case.id,
            role="assistant",
            content=assistant_message,
            created_at=now,
            response_json=(
                json.dumps(assistant_response, ensure_ascii=False)
                if assistant_response is not None
                else None
            ),
        )
        session.add(assistant_row)
        session.flush()
        assistant_message_id = assistant_row.id
        session.commit()
        return int(assistant_message_id)


def _append_message_sync(case_id: str, role: str, content: str) -> None:
    database = _database()
    with database.session() as session:
        session.add(
            GuidanceMessageORM(
                case_id=case_id,
                role=role,
                content=content,
                created_at=datetime.now(UTC),
            )
        )
        session.commit()


def _get_messages_sync(case_id: str, limit: int) -> list[dict]:
    database = _database()
    with database.session() as session:
        rows = session.scalars(
            select(GuidanceMessageORM)
            .where(GuidanceMessageORM.case_id == case_id)
            .order_by(GuidanceMessageORM.id.desc())
            .limit(limit)
        ).all()
    return [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "created_at": row.created_at,
            "response": json.loads(row.response_json) if row.response_json else None,
        }
        for row in reversed(rows)
    ]


def _database() -> Database:
    """Return a URL-keyed sync database; tests may swap DATABASE_URL per case."""
    database_url = settings.database_url
    database = _DATABASES.get(database_url)
    if database is not None:
        return database
    with _SCHEMA_GUARD:
        database = _DATABASES.get(database_url)
        if database is None:
            database = Database(database_url)
            if settings.app_env != "production":
                Base.metadata.create_all(
                    database.engine,
                    tables=[GuidanceCaseORM.__table__, GuidanceMessageORM.__table__],
                )
            _DATABASES[database_url] = database
        return database


def _set_message_response_sync(
    case_id: str,
    message_id: int,
    response: dict,
) -> None:
    database = _database()
    with database.session() as session:
        session.execute(
            sql_update(GuidanceMessageORM)
            .where(
                GuidanceMessageORM.id == message_id,
                GuidanceMessageORM.case_id == case_id,
                GuidanceMessageORM.role == "assistant",
            )
            .values(response_json=json.dumps(response, ensure_ascii=False))
        )
        session.commit()
