import uuid
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from resources.wallets.wallet_model import Wallet

DEMO_WALLET_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "ironwallet.demo.wallet")
DEMO_USER_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "ironwallet.demo.user")


async def get_by_id(session: AsyncSession, wallet_id: uuid.UUID) -> Wallet | None:
    return await session.scalar(select(Wallet).where(Wallet.id == wallet_id))


async def get_or_create_demo(session: AsyncSession) -> Wallet:
    stmt = (
        insert(Wallet)
        .values(id=DEMO_WALLET_ID, user_id=DEMO_USER_ID, balance_minor=0, currency="SAR")
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await session.execute(stmt)
    wallet = await session.scalar(select(Wallet).where(Wallet.id == DEMO_WALLET_ID))
    assert wallet is not None
    return wallet


async def create_fresh(session: AsyncSession, *, currency: str = "SAR") -> Wallet:
    wallet = Wallet(id=uuid.uuid4(), user_id=uuid.uuid4(), balance_minor=0, currency=currency)
    session.add(wallet)
    await session.flush()
    await session.refresh(wallet)
    return wallet


async def list_recent(session: AsyncSession, limit: int = 50) -> list[Wallet]:
    rows = await session.execute(
        select(Wallet).order_by(Wallet.created_at.desc()).limit(limit)
    )
    return list(rows.scalars().all())
