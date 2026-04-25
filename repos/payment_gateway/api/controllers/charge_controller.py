from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import session_dependency
from infra.idempotency import IdempotencyConflict, IdempotencyInProgress
from resources.charges.charge_schema import CreateChargeRequest, ChargeResponse
from resources.charges.charge_service import ChargeService
from resources.providers.mock_moyasar import MockMoyasarProvider

router = APIRouter()

_provider = MockMoyasarProvider()


async def _session():
    async for s in session_dependency("payment_gateway"):
        yield s


@router.post("", response_model=ChargeResponse, status_code=status.HTTP_200_OK)
async def create_charge(
    req: CreateChargeRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(_session),
) -> ChargeResponse:
    svc = ChargeService(session=session, provider=_provider)
    try:
        return await svc.create(req, idempotency_key=idempotency_key)
    except IdempotencyConflict:
        raise HTTPException(status_code=422, detail="Idempotency-Key reused with different body")
    except IdempotencyInProgress:
        raise HTTPException(status_code=409, detail="Request with this Idempotency-Key is in progress")
