import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from infra import idempotency
from infra.state_machine import guarded_transition
from resources.top_ups import top_up_dal
from resources.top_ups.top_up_model import TopUp
from resources.top_ups.top_up_schema import CreateTopUpRequest, TopUpResponse


@dataclass
class TopUpService:
    session: AsyncSession
    payment_gateway: object  # has async create_charge(...)

    async def create(self, req: CreateTopUpRequest, idempotency_key: str) -> TopUpResponse:
        idem = await idempotency.start(self.session, idempotency_key, req.model_dump(mode="json"))
        if not idem.new and idem.cached_body is not None:
            return TopUpResponse(**idem.cached_body)

        top_up = await top_up_dal.insert_pending(
            self.session, wallet_id=req.wallet_id, amount_minor=req.amount_minor, currency=req.currency
        )
        charge = await self.payment_gateway.create_charge(
            amount_minor=req.amount_minor,
            currency=req.currency,
            metadata={"top_up_id": str(top_up.id)},
            idempotency_key=f"topup-{top_up.id}",
        )
        await top_up_dal.set_charge_id(self.session, top_up.id, uuid.UUID(charge["charge_id"]))
        if charge["status"] == "ACCEPTED":
            await guarded_transition(self.session, TopUp, top_up.id, expected="PENDING", new="PROCESSING")
            response = TopUpResponse(top_up_id=top_up.id, status="PROCESSING")
        else:
            await top_up_dal.set_failed(self.session, top_up.id, reason="provider_rejected")
            response = TopUpResponse(top_up_id=top_up.id, status="FAILED")

        await idempotency.complete(
            self.session, idempotency_key, status=200, body=response.model_dump(mode="json"), resource_id=top_up.id
        )
        return response
