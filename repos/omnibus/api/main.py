import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from uvicorn import run
from alembic import command
from alembic.config import Config

from api.routes import init_routes
from db.session import get_sessionmaker
from infra.broker import Broker
from infra.outbox import run_drain_loop


_broker = Broker()
_drain_task: asyncio.Task | None = None


def _routing_key_for_type(t: str) -> str:
    if t == "settlement.completed":
        return "omnibus.settlement.completed"
    return f"omnibus.{t}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _broker.start("iron_wallet")
    sm = get_sessionmaker("omnibus")
    global _drain_task
    _drain_task = asyncio.create_task(run_drain_loop(sm, _broker, _routing_key_for_type))
    yield
    _drain_task.cancel()
    await _broker.stop()


app: FastAPI = init_routes(FastAPI(title="IronWallet Omnibus", lifespan=lifespan))

if __name__ == "__main__":
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    run("api.main:app", host="0.0.0.0", port=8084, reload=False)
