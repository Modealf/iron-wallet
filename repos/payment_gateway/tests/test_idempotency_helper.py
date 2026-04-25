from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from infra.idempotency import IdempotentStart, hash_body, start
from resources.idempotency_keys.model import IdempotencyKey


def test_hash_body_stable_for_equal_dicts():
    a = hash_body({"amount": 100, "currency": "SAR"})
    b = hash_body({"currency": "SAR", "amount": 100})
    assert a == b


def test_hash_body_differs_for_different_bodies():
    assert hash_body({"x": 1}) != hash_body({"x": 2})


@pytest.mark.asyncio
async def test_start_treats_expired_completed_row_as_fresh_claim(db_session):
    key = "expired-key"
    db_session.add(
        IdempotencyKey(
            key=key,
            request_hash=hash_body({"amount": 1}),
            state="completed",
            response_status=200,
            response_body={"old": True},
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    await db_session.flush()

    result = await start(db_session, key, {"amount": 2})
    assert isinstance(result, IdempotentStart)
    assert result.new is True
    refreshed = await db_session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key))
    assert refreshed.state == "in_progress"
    assert refreshed.response_body is None
