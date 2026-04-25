import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from resources.wallets.wallet_model import Wallet


async def get_by_id(session: AsyncSession, wallet_id: uuid.UUID) -> Wallet | None:
    return await session.scalar(select(Wallet).where(Wallet.id == wallet_id))
