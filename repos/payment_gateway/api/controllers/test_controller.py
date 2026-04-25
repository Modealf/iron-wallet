from fastapi import APIRouter, Body, Depends, Path, status


router = APIRouter()


@router.get(
    "",
)
async def test_route():
    return {"message": "Testing"}
