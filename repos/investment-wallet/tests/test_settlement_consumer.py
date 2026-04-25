import uuid
import pytest
from sqlalchemy import select

from api.consumers.settlement_consumer import handle_settlement
from resources.wallets.wallet_model import Wallet
from resources.top_ups.top_up_model import TopUp


@pytest.mark.asyncio
async def test_handle_settlement_credits_wallet_and_marks_paid(db_session_factory):
    wallet_id = uuid.uuid4()
    top_up_id = uuid.uuid4()
    async with db_session_factory() as s:
        s.add(Wallet(id=wallet_id, user_id=uuid.uuid4(), balance_minor=0, currency="SAR"))
        await s.flush()
        s.add(TopUp(id=top_up_id, wallet_id=wallet_id, amount_minor=1000, currency="SAR", status="PROCESSING"))
        await s.commit()

    envelope = {
        "id": str(uuid.uuid4()),
        "type": "settlement.completed",
        "payload": {
            "kind": "top_up",
            "correlation_id": str(top_up_id),
            "amount_minor": 1000,
            "statement_id": str(uuid.uuid4()),
            "currency": "SAR",
        },
    }
    await handle_settlement(db_session_factory, envelope)

    async with db_session_factory() as s:
        refreshed = await s.scalar(select(TopUp).where(TopUp.id == top_up_id))
        assert refreshed.status == "PAID"
        w = await s.scalar(select(Wallet).where(Wallet.id == wallet_id))
        assert w.balance_minor == 1000


@pytest.mark.asyncio
async def test_handle_settlement_is_idempotent(db_session_factory):
    wallet_id = uuid.uuid4()
    top_up_id = uuid.uuid4()
    async with db_session_factory() as s:
        s.add(Wallet(id=wallet_id, user_id=uuid.uuid4(), balance_minor=0, currency="SAR"))
        await s.flush()
        s.add(TopUp(id=top_up_id, wallet_id=wallet_id, amount_minor=500, currency="SAR", status="PROCESSING"))
        await s.commit()

    envelope = {
        "id": str(uuid.uuid4()),
        "type": "settlement.completed",
        "payload": {
            "kind": "top_up",
            "correlation_id": str(top_up_id),
            "amount_minor": 500,
            "statement_id": str(uuid.uuid4()),
            "currency": "SAR",
        },
    }
    await handle_settlement(db_session_factory, envelope)
    await handle_settlement(db_session_factory, envelope)  # replay

    async with db_session_factory() as s:
        w = await s.scalar(select(Wallet).where(Wallet.id == wallet_id))
        assert w.balance_minor == 500  # credited exactly once
