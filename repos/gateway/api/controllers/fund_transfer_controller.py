from fastapi import APIRouter, Body, status
from infra.http_client import forward_request, OMNIBUS_URL

router = APIRouter()


@router.post(
    "",
    status_code=status.HTTP_200_OK,
)
async def create_bank_transfer(
    body: dict = Body(...),
):
    """
    Forward POST /bank-transfers request to omnibus service.
    """
    response = await forward_request(
        method="POST",
        url=f"{OMNIBUS_URL}/bank-transfers",
        headers=None,
        json_body=body,
    )
    return response.json()
