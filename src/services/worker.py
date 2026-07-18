"""PostgreSQL-backed background job worker primitives.

The deployment runs this module as a separate process. Jobs are claimed with
row locks so multiple workers can run safely without Redis.
"""

from datetime import datetime, UTC
from uuid import uuid4

from sqlalchemy import select, update

from src.models.orm import BackgroundJobORM
from src.services.persistence import AsyncDatabase


async def enqueue(database: AsyncDatabase, job_type: str, payload: dict) -> str:
    job_id = str(uuid4())
    async with database.session() as session:
        session.add(BackgroundJobORM(id=job_id, job_type=job_type, payload=payload, status="pending"))
        await session.commit()
    return job_id


async def claim_one(database: AsyncDatabase) -> BackgroundJobORM | None:
    async with database.session() as session:
        result = await session.execute(select(BackgroundJobORM).where(BackgroundJobORM.status == "pending").order_by(BackgroundJobORM.created_at).with_for_update(skip_locked=True).limit(1))
        job = result.scalar_one_or_none()
        if job is None:
            return None
        job.status = "processing"
        job.attempts += 1
        job.locked_at = datetime.now(UTC)
        await session.commit()
        return job


async def mark_done(database: AsyncDatabase, job_id: str) -> None:
    async with database.session() as session:
        await session.execute(update(BackgroundJobORM).where(BackgroundJobORM.id == job_id).values(status="done"))
        await session.commit()


async def mark_failed(database: AsyncDatabase, job_id: str, error: str, retry: bool = True) -> None:
    async with database.session() as session:
        await session.execute(update(BackgroundJobORM).where(BackgroundJobORM.id == job_id).values(status="pending" if retry else "dead_letter", last_error=error[:2000]))
        await session.commit()
