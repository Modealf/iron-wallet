from fastapi import FastAPI
from uvicorn import run
from api.routes import init_routes
from alembic import command
from alembic.config import Config


app: FastAPI = init_routes(
    FastAPI(
        title="payment_gateway",
        description="This service is to abstract processing payments and integration with payment gateway providers",
    )
)


if __name__ == "__main__":

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    run(
        "api.main:app",
        host="0.0.0.0",
        port=8082,
        reload=True,
    )
