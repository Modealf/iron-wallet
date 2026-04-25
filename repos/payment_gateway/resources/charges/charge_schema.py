import uuid
from pydantic import BaseModel, Field


class CreateChargeRequest(BaseModel):
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    metadata: dict = Field(default_factory=dict)


class ChargeResponse(BaseModel):
    charge_id: uuid.UUID
    status: str
    provider_payment_id: str | None
