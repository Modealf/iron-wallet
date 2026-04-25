import asyncio
import os
import uuid
import hmac
import hashlib
import json
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .port import ProviderChargeRequest, ProviderChargeResponse

OMNIBUS_WEBHOOK_URL = os.getenv("OMNIBUS_WEBHOOK_URL", "http://localhost:8084/webhooks/moyasar")
WEBHOOK_SECRET = os.getenv("MOYASAR_WEBHOOK_SECRET", "dev-secret")
WEBHOOK_DELAY_SECONDS = float(os.getenv("MOYASAR_WEBHOOK_DELAY_SECONDS", "1.0"))


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


class MockMoyasarProvider:
    """Simulates Moyasar: accepts all requests, schedules a webhook back to Omnibus."""

    async def create_payment(self, req: ProviderChargeRequest) -> ProviderChargeResponse:
        payment_id = f"pay_{uuid.uuid4().hex[:12]}"
        asyncio.create_task(self._fire_webhook(payment_id, req))
        return ProviderChargeResponse(payment_id=payment_id, accepted=True)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=0.5, max=8))
    async def _post(self, body: bytes, sig: str) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                OMNIBUS_WEBHOOK_URL,
                content=body,
                headers={"Content-Type": "application/json", "X-Signature": sig},
            )
            resp.raise_for_status()

    async def _fire_webhook(self, payment_id: str, req: ProviderChargeRequest) -> None:
        await asyncio.sleep(WEBHOOK_DELAY_SECONDS)
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.paid",
            "payment_id": payment_id,
            "amount_minor": req.amount_minor,
            "currency": req.currency,
            "metadata": req.metadata,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        body = json.dumps(payload).encode()
        try:
            await self._post(body, _sign(body))
        except Exception:
            # In a real system this goes to a DLQ / retry queue. For the POC we just log.
            pass
