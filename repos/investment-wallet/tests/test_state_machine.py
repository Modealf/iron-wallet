import uuid
import pytest
from sqlalchemy import select

from resources.wallets.wallet_model import Wallet
from resources.top_ups.top_up_model import TopUp
from infra.state_machine import guarded_transition, IllegalStateTransition


@pytest.mark.asyncio
async def test_transition_succeeds_when_status_matches(db_session):
    wallet = Wallet(id=uuid.uuid4(), user_id=uuid.uuid4(), balance_minor=0, currency="SAR")
    db_session.add(wallet)
    await db_session.flush()
    topup = TopUp(id=uuid.uuid4(), wallet_id=wallet.id, amount_minor=100, currency="SAR", status="PENDING")
    db_session.add(topup)
    await db_session.flush()

    await guarded_transition(db_session, TopUp, topup.id, expected="PENDING", new="PROCESSING")
    refreshed = await db_session.scalar(select(TopUp).where(TopUp.id == topup.id))
    assert refreshed.status == "PROCESSING"


@pytest.mark.asyncio
async def test_transition_raises_on_illegal(db_session):
    wallet = Wallet(id=uuid.uuid4(), user_id=uuid.uuid4(), balance_minor=0, currency="SAR")
    db_session.add(wallet)
    await db_session.flush()
    topup = TopUp(id=uuid.uuid4(), wallet_id=wallet.id, amount_minor=100, currency="SAR", status="PENDING")
    db_session.add(topup)
    await db_session.flush()

    with pytest.raises(IllegalStateTransition):
        await guarded_transition(db_session, TopUp, topup.id, expected="PROCESSING", new="PAID")
