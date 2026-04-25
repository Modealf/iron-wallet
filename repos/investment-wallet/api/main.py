import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from uvicorn import run
from alembic import command
from alembic.config import Config

from api.routes import init_routes
from api.consumers.settlement_consumer import run_consumer
from db.session import get_sessionmaker
from infra.broker import Broker, RABBITMQ_URL
from infra.events import (
    CONSUMER_QUEUE,
    CONSUMER_BINDING,
    EXCHANGE,
    DLQ_NAME,
    RK_TOP_UP_PAID,
    RK_FUND_TRANSFER_PAID,
)
from infra.outbox import run_drain_loop


_broker = Broker()
_tasks: list[asyncio.Task] = []


def _rk(type_: str) -> str:
    return {
        "top_up.paid": RK_TOP_UP_PAID,
        "fund_transfer.paid": RK_FUND_TRANSFER_PAID,
    }.get(type_, f"wallet.{type_}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _broker.start(EXCHANGE)
    sm = get_sessionmaker("investment_wallet")
    _tasks.append(asyncio.create_task(run_drain_loop(sm, _broker, _rk)))
    _tasks.append(
        asyncio.create_task(
            run_consumer(sm, RABBITMQ_URL, CONSUMER_QUEUE, CONSUMER_BINDING, EXCHANGE, DLQ_NAME)
        )
    )
    yield
    for t in _tasks:
        t.cancel()
    await _broker.stop()


app: FastAPI = init_routes(
    FastAPI(
        title="Investment-Wallet Service",
        description="This service is to abstract wallets operations",
        lifespan=lifespan,
    )
)


if __name__ == "__main__":
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    RELOAD = os.getenv("UVICORN_RELOAD", "true").lower() == "true"

    run(
        "api.main:app",
        host="0.0.0.0",
        port=8083,
        reload=RELOAD,
    )
