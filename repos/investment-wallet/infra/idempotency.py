import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from resources.idempotency_keys.model import IdempotencyKey

IDEMPOTENCY_TTL = timedelta(hours=24)


class IdempotencyConflict(Exception):
    """Same key, different request body — client bug. Surface as 422."""


class IdempotencyInProgress(Exception):
    """Same key, still running. Surface as 409."""


@dataclass
class IdempotentStart:
    new: bool                 # True if we just claimed the key
    cached_status: int | None
    cached_body: dict | None
    resource_id: Any | None


def hash_body(body: dict) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


async def start(session: AsyncSession, key: str, body: dict) -> IdempotentStart:
    """Attempt to claim a key. Must run inside the business txn."""
    rh = hash_body(body)
    expires = datetime.now(timezone.utc) + IDEMPOTENCY_TTL

    stmt = (
        insert(IdempotencyKey)
        .values(key=key, request_hash=rh, state="in_progress", expires_at=expires)
        .on_conflict_do_nothing(index_elements=["key"])
        .returning(IdempotencyKey.key)
    )
    result = await session.execute(stmt)
    inserted = result.scalar_one_or_none()
    if inserted is not None:
        return IdempotentStart(new=True, cached_status=None, cached_body=None, resource_id=None)

    existing = await session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key))
    assert existing is not None
    if existing.request_hash != rh:
        raise IdempotencyConflict()
    if existing.state == "in_progress":
        raise IdempotencyInProgress()
    return IdempotentStart(
        new=False,
        cached_status=existing.response_status,
        cached_body=existing.response_body,
        resource_id=existing.resource_id,
    )


async def complete(session: AsyncSession, key: str, status: int, body: dict, resource_id) -> None:
    row = await session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key))
    assert row is not None
    row.state = "completed"
    row.response_status = status
    row.response_body = body
    row.resource_id = resource_id
