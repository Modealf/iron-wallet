import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from db.session import session_dependency
from resources.statements.statement_service import record_bank_transfer, BankTransferDuplicate

router = APIRouter()


class BankTransferIn(BaseModel):
    virtual_iban: str
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    bank_reference: str
    wallet_id: uuid.UUID


async def _session():
    async for s in session_dependency("omnibus"):
        yield s


@router.post("")
async def create_bank_transfer(body: BankTransferIn, session: AsyncSession = Depends(_session)):
    try:
        statement_id = await record_bank_transfer(session, body=body)
        return {"statement_id": str(statement_id)}
    except BankTransferDuplicate:
        raise HTTPException(status_code=409, detail="duplicate bank_reference")
