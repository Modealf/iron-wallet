import uuid
from pydantic import BaseModel, Field


class CreateTopUpRequest(BaseModel):
    wallet_id: uuid.UUID
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)


class TopUpResponse(BaseModel):
    top_up_id: uuid.UUID
    status: str
