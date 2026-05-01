import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from infra.http_client import forward_request, WALLET_URL

router = APIRouter()


def _err_or_resp(resp_or_exc) -> JSONResponse:
    return JSONResponse(status_code=resp_or_exc.status_code, content=resp_or_exc.json())


@router.get("")
async def list_wallets(request: Request):
    target = f"{WALLET_URL}/wallets"
    if request.url.query:
        target += f"?{request.url.query}"
    try:
        resp = await forward_request("GET", target)
    except httpx.HTTPStatusError as e:
        return _err_or_resp(e.response)
    return _err_or_resp(resp)


@router.post("")
async def create_wallet():
    try:
        resp = await forward_request("POST", f"{WALLET_URL}/wallets")
    except httpx.HTTPStatusError as e:
        return _err_or_resp(e.response)
    return _err_or_resp(resp)


@router.get("/{path:path}")
async def forward_get_wallet(path: str, request: Request):
    qs = request.url.query
    target = f"{WALLET_URL}/wallets/{path}" + (f"?{qs}" if qs else "")
    try:
        resp = await forward_request("GET", target)
    except httpx.HTTPStatusError as e:
        return _err_or_resp(e.response)
    return _err_or_resp(resp)
