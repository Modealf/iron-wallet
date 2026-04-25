import hashlib
import hmac
import json
import os
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import session_dependency
from resources.statements.statement_service import record_provider_webhook, WebhookAlreadyProcessed

router = APIRouter()

WEBHOOK_SECRET = os.getenv("MOYASAR_WEBHOOK_SECRET", "dev-secret")


def _verify(body: bytes, sig: str | None) -> bool:
    if sig is None:
        return False
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


async def _session():
    async for s in session_dependency("omnibus"):
        yield s


@router.post("/moyasar")
async def moyasar_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
    session: AsyncSession = Depends(_session),
):
    raw = await request.body()
    if not _verify(raw, x_signature):
        raise HTTPException(status_code=401, detail="bad signature")

    payload = json.loads(raw)
    correlation = payload.get("metadata", {}).get("top_up_id")
    try:
        await record_provider_webhook(
            session,
            provider="moyasar",
            event_id=payload["event_id"],
            amount_minor=payload["amount_minor"],
            currency=payload["currency"],
            correlation_id=uuid.UUID(correlation) if correlation else None,
            source_ref=payload["event_id"],
            kind="top_up",
        )
        return {"status": "recorded"}
    except WebhookAlreadyProcessed:
        return {"status": "duplicate"}
