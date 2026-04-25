from typing import Protocol
from pydantic import BaseModel


class ProviderChargeRequest(BaseModel):
    amount_minor: int
    currency: str
    metadata: dict


class ProviderChargeResponse(BaseModel):
    payment_id: str
    accepted: bool


class PaymentProviderPort(Protocol):
    async def create_payment(self, req: ProviderChargeRequest) -> ProviderChargeResponse: ...
