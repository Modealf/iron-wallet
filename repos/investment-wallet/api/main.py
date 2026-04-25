from fastapi import FastAPI
from uvicorn import run
from api.routes import init_routes
from alembic import command
from alembic.config import Config


app: FastAPI = init_routes(
    FastAPI(
        title="Investment-Wallet Service",
        description="This service is to abstract wallets operations",
    )
)


if __name__ == "__main__":

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    run(
        "api.main:app",
        host="0.0.0.0",
        port=8083,
        reload=True,
    )
