import os

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

WALLET_URL = os.getenv("WALLET_URL", "http://localhost:8083")
OMNIBUS_URL = os.getenv("OMNIBUS_URL", "http://localhost:8084")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
async def forward_request(
    method: str,
    url: str,
    headers: dict | None = None,
    json_body: dict | None = None,
) -> httpx.Response:
    """
    Forward HTTP request with automatic retry via tenacity.
    Raises httpx exceptions on failure after retries exhausted.
    """
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            json=json_body,
        )
        response.raise_for_status()
        return response
