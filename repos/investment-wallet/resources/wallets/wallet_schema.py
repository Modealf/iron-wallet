import uuid
from datetime import datetime
from pydantic import BaseModel


class TopUpView(BaseModel):
    id: uuid.UUID
    amount_minor: int
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime


class FundTransferView(BaseModel):
    id: uuid.UUID
    amount_minor: int
    currency: str
    bank_reference: str
    created_at: datetime


class WalletView(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    balance_minor: int
    currency: str
    recent_top_ups: list[TopUpView]
    recent_fund_transfers: list[FundTransferView]
