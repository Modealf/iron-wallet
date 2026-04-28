import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import session_dependency
from resources.wallets import wallet_dal
from resources.wallets.wallet_schema import WalletView, TopUpView, FundTransferView
from resources.top_ups.top_up_model import TopUp
from resources.fund_transfers.fund_transfer_model import FundTransfer

router = APIRouter()


async def _session():
    async for s in session_dependency("investment_wallet"):
        yield s


async def _build_view(session: AsyncSession, wallet) -> WalletView:
    top_ups = (await session.execute(
        select(TopUp).where(TopUp.wallet_id == wallet.id).order_by(desc(TopUp.created_at)).limit(20)
    )).scalars().all()
    fund_transfers = (await session.execute(
        select(FundTransfer).where(FundTransfer.wallet_id == wallet.id).order_by(desc(FundTransfer.created_at)).limit(20)
    )).scalars().all()
    return WalletView(
        id=wallet.id,
        user_id=wallet.user_id,
        balance_minor=wallet.balance_minor,
        currency=wallet.currency,
        recent_top_ups=[TopUpView.model_validate(t, from_attributes=True) for t in top_ups],
        recent_fund_transfers=[FundTransferView.model_validate(f, from_attributes=True) for f in fund_transfers],
    )


@router.get("/demo", response_model=WalletView)
async def get_demo_wallet(session: AsyncSession = Depends(_session)) -> WalletView:
    wallet = await wallet_dal.get_or_create_demo(session)
    return await _build_view(session, wallet)


@router.get("/{wallet_id}", response_model=WalletView)
async def get_wallet(wallet_id: uuid.UUID, session: AsyncSession = Depends(_session)) -> WalletView:
    wallet = await wallet_dal.get_by_id(session, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="wallet not found")
    return await _build_view(session, wallet)
