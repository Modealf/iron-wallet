import pytest
from unittest.mock import AsyncMock
from resources.providers.port import ProviderChargeResponse
from resources.charges.charge_service import ChargeService
from resources.charges.charge_schema import CreateChargeRequest


@pytest.mark.asyncio
async def test_service_inserts_charge_and_marks_accepted_on_provider_success(db_session):
    provider = AsyncMock()
    provider.create_payment.return_value = ProviderChargeResponse(payment_id="pay_x", accepted=True)

    svc = ChargeService(session=db_session, provider=provider)
    result = await svc.create(
        CreateChargeRequest(amount_minor=1000, currency="SAR", metadata={"top_up_id": "abc"}),
        idempotency_key="k1",
    )
    assert result.status == "ACCEPTED"
    assert result.provider_payment_id == "pay_x"


@pytest.mark.asyncio
async def test_service_marks_rejected_when_provider_says_no(db_session):
    provider = AsyncMock()
    provider.create_payment.return_value = ProviderChargeResponse(payment_id="pay_y", accepted=False)

    svc = ChargeService(session=db_session, provider=provider)
    result = await svc.create(
        CreateChargeRequest(amount_minor=1000, currency="SAR", metadata={}),
        idempotency_key="k2",
    )
    assert result.status == "REJECTED"
