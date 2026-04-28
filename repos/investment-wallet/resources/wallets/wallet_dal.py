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
