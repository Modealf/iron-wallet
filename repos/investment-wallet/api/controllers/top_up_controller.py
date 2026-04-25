from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import session_dependency
from infra.idempotency import IdempotencyConflict, IdempotencyInProgress
from infra.http_client import PaymentGatewayClient
from resources.top_ups.top_up_schema import CreateTopUpRequest, TopUpResponse
from resources.top_ups.top_up_service import TopUpService

router = APIRouter()

_pg_client = PaymentGatewayClient()


async def _session():
    async for s in session_dependency("investment_wallet"):
        yield s


@router.post("", response_model=TopUpResponse)
async def create_top_up(
    req: CreateTopUpRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(_session),
):
    svc = TopUpService(session=session, payment_gateway=_pg_client)
    try:
        return await svc.create(req, idempotency_key=idempotency_key)
    except IdempotencyConflict:
        raise HTTPException(422, "Idempotency-Key reused with different body")
    except IdempotencyInProgress:
        raise HTTPException(409, "Request with this Idempotency-Key is in progress")
