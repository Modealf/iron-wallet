import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from resources.top_ups.top_up_model import TopUp


async def insert_pending(session: AsyncSession, *, wallet_id, amount_minor, currency) -> TopUp:
    t = TopUp(id=uuid.uuid4(), wallet_id=wallet_id, amount_minor=amount_minor, currency=currency, status="PENDING")
    session.add(t)
    await session.flush()
    return t


async def set_charge_id(session: AsyncSession, top_up_id: uuid.UUID, charge_id: uuid.UUID) -> None:
    t = await session.get(TopUp, top_up_id)
    assert t is not None
    t.charge_id = charge_id


async def set_failed(session: AsyncSession, top_up_id: uuid.UUID, reason: str) -> None:
    t = await session.get(TopUp, top_up_id)
    assert t is not None
    t.status = "FAILED"
    t.failure_reason = reason
