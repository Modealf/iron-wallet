import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from resources.outbox.model import OutboxEvent
from infra.broker import Broker
from infra.events import EXCHANGE


async def enqueue(session: AsyncSession, *, aggregate_id: uuid.UUID, type_: str, payload: dict) -> None:
    session.add(OutboxEvent(id=uuid.uuid4(), aggregate_id=aggregate_id, type=type_, payload=payload))


async def drain_once(sm: async_sessionmaker[AsyncSession], broker: Broker, routing_key_for_type) -> int:
    """Returns number of events published."""
    published = 0
    async with sm() as session:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.occurred_at)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
        rows = (await session.execute(stmt)).scalars().all()
        for row in rows:
            rk = routing_key_for_type(row.type)
            await broker.publish(rk, {
                "id": str(row.id),
                "aggregate_id": str(row.aggregate_id),
                "type": row.type,
                "payload": row.payload,
                "occurred_at": row.occurred_at.isoformat(),
            })
            row.published_at = datetime.now(timezone.utc)
            published += 1
        await session.commit()
    return published


async def run_drain_loop(sm, broker: Broker, routing_key_for_type, interval_seconds: float = 0.5) -> None:
    while True:
        try:
            n = await drain_once(sm, broker, routing_key_for_type)
            if n == 0:
                await asyncio.sleep(interval_seconds)
        except Exception:
            await asyncio.sleep(interval_seconds)
