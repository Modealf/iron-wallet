import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from infra import idempotency
from resources.charges import charge_dal
from resources.charges.charge_schema import CreateChargeRequest, ChargeResponse
from resources.providers.port import PaymentProviderPort, ProviderChargeRequest


@dataclass
class ChargeService:
    session: AsyncSession
    provider: PaymentProviderPort

    async def create(self, req: CreateChargeRequest, idempotency_key: str) -> ChargeResponse:
        idem = await idempotency.start(self.session, idempotency_key, req.model_dump(mode="json"))
        if not idem.new and idem.cached_body is not None:
            return ChargeResponse(**idem.cached_body)

        charge = await charge_dal.insert_charge(
            self.session,
            amount_minor=req.amount_minor,
            currency=req.currency,
            metadata=req.metadata,
            provider="moyasar",
        )

        prov = await self.provider.create_payment(
            ProviderChargeRequest(
                amount_minor=req.amount_minor, currency=req.currency, metadata=req.metadata
            )
        )

        if prov.accepted:
            await charge_dal.set_accepted(self.session, charge.id, prov.payment_id)
            response = ChargeResponse(charge_id=charge.id, status="ACCEPTED", provider_payment_id=prov.payment_id)
        else:
            await charge_dal.set_rejected(self.session, charge.id)
            response = ChargeResponse(charge_id=charge.id, status="REJECTED", provider_payment_id=prov.payment_id)

        await idempotency.complete(
            self.session, idempotency_key, status=200, body=response.model_dump(mode="json"), resource_id=charge.id
        )
        return response
