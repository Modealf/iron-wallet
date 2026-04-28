import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from infra.http_client import forward_request, WALLET_URL

router = APIRouter()


@router.get("/{path:path}")
async def forward_get_wallet(path: str, request: Request):
    qs = request.url.query
    target = f"{WALLET_URL}/wallets/{path}" + (f"?{qs}" if qs else "")
    try:
        resp = await forward_request("GET", target)
    except httpx.HTTPStatusError as e:
        return JSONResponse(status_code=e.response.status_code, content=e.response.json())
    return JSONResponse(status_code=resp.status_code, content=resp.json())
