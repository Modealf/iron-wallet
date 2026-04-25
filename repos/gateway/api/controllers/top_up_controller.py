from fastapi import APIRouter, Body, Header, status
from infra.http_client import forward_request, WALLET_URL

router = APIRouter()


@router.post(
    "",
    status_code=status.HTTP_200_OK,
)
async def create_top_up(
    body: dict = Body(...),
    idempotency_key: str = Header(...),
):
    """
    Forward POST /top-ups request to wallet service.
    Preserves the Idempotency-Key header for deduplication.
    """
    headers = {
        "Idempotency-Key": idempotency_key,
    }
    response = await forward_request(
        method="POST",
        url=f"{WALLET_URL}/top-ups",
        headers=headers,
        json_body=body,
    )
    return response.json()
