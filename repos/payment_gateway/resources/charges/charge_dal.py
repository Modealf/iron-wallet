import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from resources.charges.charge_model import Charge


async def insert_charge(session: AsyncSession, *, amount_minor: int, currency: str, metadata: dict, provider: str) -> Charge:
    charge = Charge(
        id=uuid.uuid4(),
        amount_minor=amount_minor,
        currency=currency,
        provider=provider,
        metadata_=metadata,
        status="CREATED",
    )
    session.add(charge)
    await session.flush()
    return charge


async def set_accepted(session: AsyncSession, charge_id: uuid.UUID, provider_payment_id: str) -> None:
    charge = await session.get(Charge, charge_id)
    assert charge is not None
    charge.status = "ACCEPTED"
    charge.provider_payment_id = provider_payment_id


async def set_rejected(session: AsyncSession, charge_id: uuid.UUID) -> None:
    charge = await session.get(Charge, charge_id)
    assert charge is not None
    charge.status = "REJECTED"
