import os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

PAYMENT_GATEWAY_URL = os.getenv("PAYMENT_GATEWAY_URL", "http://localhost:8082")


class PaymentGatewayClient:
    def __init__(self, base_url: str = PAYMENT_GATEWAY_URL) -> None:
        self._base_url = base_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4))
    async def create_charge(self, *, amount_minor: int, currency: str, metadata: dict, idempotency_key: str) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/charges",
                json={"amount_minor": amount_minor, "currency": currency, "metadata": metadata},
                headers={"Idempotency-Key": idempotency_key},
            )
            resp.raise_for_status()
            return resp.json()
