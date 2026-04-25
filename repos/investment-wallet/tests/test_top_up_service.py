import uuid
import pytest
from unittest.mock import AsyncMock
from sqlalchemy import select

from resources.wallets.wallet_model import Wallet
from resources.top_ups.top_up_model import TopUp
from resources.top_ups.top_up_service import TopUpService
from resources.top_ups.top_up_schema import CreateTopUpRequest


@pytest.mark.asyncio
async def test_create_top_up_transitions_to_processing_when_charge_accepted(db_session):
    wallet = Wallet(id=uuid.uuid4(), user_id=uuid.uuid4(), balance_minor=0, currency="SAR")
    db_session.add(wallet)
    await db_session.flush()

    pg = AsyncMock()
    pg.create_charge.return_value = {
        "charge_id": str(uuid.uuid4()), "status": "ACCEPTED", "provider_payment_id": "pay_x"
    }
    svc = TopUpService(session=db_session, payment_gateway=pg)
    resp = await svc.create(
        CreateTopUpRequest(wallet_id=wallet.id, amount_minor=1000, currency="SAR"),
        idempotency_key="k1",
    )
    assert resp.status == "PROCESSING"
    row = await db_session.scalar(select(TopUp).where(TopUp.id == resp.top_up_id))
    assert row.status == "PROCESSING"


@pytest.mark.asyncio
async def test_create_top_up_transitions_to_failed_when_charge_rejected(db_session):
    wallet = Wallet(id=uuid.uuid4(), user_id=uuid.uuid4(), balance_minor=0, currency="SAR")
    db_session.add(wallet)
    await db_session.flush()

    pg = AsyncMock()
    pg.create_charge.return_value = {"charge_id": str(uuid.uuid4()), "status": "REJECTED", "provider_payment_id": None}
    svc = TopUpService(session=db_session, payment_gateway=pg)
    resp = await svc.create(
        CreateTopUpRequest(wallet_id=wallet.id, amount_minor=1000, currency="SAR"),
        idempotency_key="k2",
    )
    assert resp.status == "FAILED"
