import os

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

WALLET_URL = os.getenv("WALLET_URL", "http://localhost:8083")
OMNIBUS_URL = os.getenv("OMNIBUS_URL", "http://localhost:8084")


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600
    return False


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
async def forward_request(
    method: str,
    url: str,
    headers: dict | None = None,
    json_body: dict | None = None,
) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        response = await client.request(method=method, url=url, headers=headers, json=json_body)
        response.raise_for_status()
        return response
