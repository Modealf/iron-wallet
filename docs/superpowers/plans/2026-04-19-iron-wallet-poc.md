# IronWallet POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Top-Up and Fund-Transfer flows across 4 FastAPI services with idempotency, state machines, outbox pattern, and RabbitMQ events.

**Architecture:** Hybrid sync+async microservices on CockroachDB. Sync HTTP for commands (client → gateway → wallet → payment-gateway). RabbitMQ for state reconciliation (omnibus → wallet). Each service owns its database; outbox pattern keeps writes and event emission atomic.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, aio-pika 9, tenacity, httpx, pytest, pytest-asyncio, CockroachDB 23.1, RabbitMQ 3.8.

**Spec:** [`../specs/2026-04-19-iron-wallet-design.md`](../specs/2026-04-19-iron-wallet-design.md)

**Working directory:** All commands assume `cd /Users/modealf/Projects/investment-wallet` unless stated otherwise.

---

## File map

```
repos/
├── gateway/                              (thin; no DB, no broker)
│   ├── api/
│   │   ├── controllers/
│   │   │   ├── top_up_controller.py           NEW
│   │   │   └── fund_transfer_controller.py    NEW
│   │   ├── main.py                            MODIFY (port 8084)
│   │   └── routes.py                          MODIFY
│   ├── infra/http_client.py                   NEW
│   ├── tests/test_forwarding.py               NEW
│   └── pyproject.toml                         MODIFY (+httpx, +tenacity)
│
├── payment_gateway/
│   ├── api/controllers/charge_controller.py   NEW
│   ├── api/{main,routes}.py                   MODIFY
│   ├── db/session.py                          NEW
│   ├── db/migrations/versions/001_initial.py  NEW
│   ├── infra/idempotency.py                   NEW
│   ├── resources/charges/{model,schema,dal,service}.py   NEW
│   ├── resources/providers/{port,mock_moyasar}.py        NEW
│   ├── resources/idempotency_keys/model.py    NEW
│   ├── tests/{test_idempotency_helper,test_charge_service,test_charge_controller}.py  NEW
│   └── pyproject.toml                         MODIFY (+httpx, +tenacity)
│
├── omnibus/
│   ├── api/                                   NEW (missing from scaffold)
│   │   ├── main.py, routes.py
│   │   └── controllers/{webhook_controller,bank_transfer_controller}.py
│   ├── db/session.py                          NEW
│   ├── db/migrations/versions/001_initial.py  NEW
│   ├── infra/{idempotency,broker,outbox,events}.py       NEW
│   ├── resources/statements/{model,schema,dal,service}.py  REPLACE (scaffold has typo "statment")
│   ├── resources/outbox/model.py              NEW
│   ├── resources/processed_webhooks/model.py  NEW
│   ├── resources/idempotency_keys/model.py    NEW
│   ├── tests/…                                NEW
│   └── pyproject.toml                         MODIFY (+aio-pika, +httpx, +tenacity)
│
└── investment-wallet/
    ├── api/controllers/{top_up,fund_transfer,wallet}_controller.py   NEW
    ├── api/consumers/settlement_consumer.py   NEW
    ├── api/{main,routes}.py                   MODIFY
    ├── db/session.py                          NEW
    ├── db/migrations/versions/001_initial.py  NEW
    ├── infra/{idempotency,broker,outbox,events,state_machine,http_client}.py   NEW
    ├── resources/wallets/…                    REPLACE scaffold stubs
    ├── resources/top_ups/{model,schema,dal,service}.py   NEW
    ├── resources/fund_transfers/{model,schema,dal,service}.py   NEW
    ├── resources/outbox/model.py              NEW
    ├── resources/processed_events/model.py    NEW
    ├── resources/idempotency_keys/model.py    NEW
    ├── tests/…                                NEW
    └── pyproject.toml                         MODIFY (+aio-pika, +httpx, +tenacity)
```

**Cross-service duplication is accepted** (matches scaffold convention: no shared lib). Each service gets its own copy of `infra/idempotency.py`, `infra/broker.py`, etc. Code is ~40 lines per helper — small enough to diverge per service later.

**Convention for the idempotency helper:** the implementation is identical across services, so the first service (Payment-Gateway) defines the canonical version in Task 2.3; subsequent services paste-and-adapt it in Tasks 3.3 and 4.3.

---

## Phase 0 — Bootstrap

### Task 0.1: Initialize git, fix gateway port collision

**Files:**
- Init: `/Users/modealf/Projects/investment-wallet/.git` (new repo)
- Modify: `repos/gateway/api/main.py`
- Create: `.gitignore` at project root

- [ ] **Step 1: `git init` at project root and add `.gitignore`**

```bash
cd /Users/modealf/Projects/investment-wallet
git init
```

Write `.gitignore`:
```
__pycache__/
*.pyc
.venv/
.mypy_cache/
.pytest_cache/
.DS_Store
*.egg-info/
.coverage
htmlcov/
.idea/
.vscode/*
!.vscode/settings.json
```

- [ ] **Step 2: Change gateway port from 8080 to 8084**

Edit `repos/gateway/api/main.py`:
```python
from fastapi import FastAPI
from uvicorn import run
from api.routes import init_routes

app: FastAPI = init_routes(
    FastAPI(
        title="IronWallet Gateway",
        description="Edge service that routes client requests to internal services.",
    )
)

if __name__ == "__main__":
    run("api.main:app", host="0.0.0.0", port=8084, reload=True)
```

- [ ] **Step 3: Initial commit**

```bash
git add -A
git commit -m "chore: initialize repo and fix gateway port collision with Cockroach admin UI"
```

### Task 0.2: Verify scaffold boots

- [ ] **Step 1: Start infra**

```bash
make up
```

Expected: Cockroach on 26257 + 8080, Redis on 6379, RabbitMQ on 5672 + 15672.

- [ ] **Step 2: Install all services**

```bash
make install
```

Expected: 4 successful Poetry installs.

- [ ] **Step 3: Verify scaffold compiles per service** (each in a separate shell or sequentially)

```bash
cd repos/gateway && poetry run python -c "from api.main import app; print(app.title)"
cd ../payment_gateway && poetry run python -c "from api.main import app; print(app.title)"
cd ../investment-wallet && poetry run python -c "from api.main import app; print(app.title)"
```

Expected: each prints its title. (Omnibus has no api/ yet — intentional, we build it in Phase 3.)

No commit.

---

## Phase 1 — Shared per-service plumbing

Phase 1 adds runtime dependencies and a DB session factory once per service. We apply the **same pattern** to each of `payment_gateway`, `omnibus`, and `investment-wallet`. Gateway has no DB, so it only gets httpx.

### Task 1.1: Add Python dependencies to data services

**Files:**
- Modify: `repos/payment_gateway/pyproject.toml`
- Modify: `repos/omnibus/pyproject.toml`
- Modify: `repos/investment-wallet/pyproject.toml`
- Modify: `repos/gateway/pyproject.toml`

- [ ] **Step 1: Payment-Gateway — add httpx and tenacity**

```bash
cd repos/payment_gateway
poetry add httpx@^0.27 tenacity@^8.2
```

- [ ] **Step 2: Omnibus — add aio-pika, httpx, tenacity**

```bash
cd ../omnibus
poetry add "aio-pika@^9.4" httpx@^0.27 tenacity@^8.2
```

- [ ] **Step 3: Investment-Wallet — add aio-pika, httpx, tenacity**

```bash
cd ../investment-wallet
poetry add "aio-pika@^9.4" httpx@^0.27 tenacity@^8.2
```

- [ ] **Step 4: Gateway — add httpx and tenacity**

```bash
cd ../gateway
poetry add httpx@^0.27 tenacity@^8.2
```

- [ ] **Step 5: Commit**

```bash
cd /Users/modealf/Projects/investment-wallet
git add -A
git commit -m "chore: add httpx, tenacity, aio-pika dependencies per service"
```

### Task 1.2: Async DB session factory (per data service)

Each data service gets an identical `db/session.py`. The scaffold already has `db/models/model_base.py` and `db/migrations/env.py` per service; we plug the session into those.

**Files (create in payment_gateway, omnibus, investment-wallet):**
- Create: `repos/<service>/db/session.py`

- [ ] **Step 1: Create `db/session.py` in each data service**

```python
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "cockroachdb+asyncpg://root@localhost:26257/{db}?sslmode=disable",
)

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine(db_name: str):
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL.format(db=db_name), pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def get_sessionmaker(db_name: str) -> async_sessionmaker[AsyncSession]:
    get_engine(db_name)
    assert _sessionmaker is not None
    return _sessionmaker


async def session_dependency(db_name: str):
    """FastAPI Depends() — yields an async session, commits on success, rolls back on error."""
    sm = get_sessionmaker(db_name)
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

For payment_gateway: set `db_name = "payment_gateway"` in wiring.
For omnibus: `db_name = "omnibus"`.
For investment_wallet: `db_name = "investment_wallet"`.

*Python note for the .NET reader:* `async_sessionmaker` is the `IDbContextFactory` equivalent. `session_dependency` is a FastAPI `Depends()` factory — FastAPI calls it per request (like scoped DI in .NET), yields the session, and runs the teardown after the response returns.

- [ ] **Step 2: Commit**

```bash
git add repos/*/db/session.py
git commit -m "feat: add async SQLAlchemy session factory per data service"
```

### Task 1.3: Alembic env wired to our models

Scaffold has `db/migrations/env.py` and `alembic.ini`. We need to ensure alembic knows about our Base metadata and uses the right URL.

**Files:**
- Modify: `repos/payment_gateway/db/migrations/env.py`
- Modify: `repos/omnibus/db/migrations/env.py` (if exists) or create
- Modify: `repos/investment-wallet/db/migrations/env.py`

- [ ] **Step 1: Read the existing env.py in investment-wallet to understand the scaffold convention**

```bash
cat repos/investment-wallet/db/migrations/env.py
```

- [ ] **Step 2: Replace each `env.py` with a version that imports models and reads DATABASE_URL**

Template (adapt `db_name` per service):

```python
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from db.models.model_base import Base
import db.models.models  # noqa: F401  — ensures all models import

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

DB_NAME = os.getenv("ALEMBIC_DB_NAME", "investment_wallet")  # override per service
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"cockroachdb+asyncpg://root@localhost:26257/{DB_NAME}?sslmode=disable",
)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    context.configure(url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_migrations_online())
```

For `payment_gateway`: default `DB_NAME = "payment_gateway"`.
For `omnibus`: default `DB_NAME = "omnibus"`.

- [ ] **Step 3: Verify alembic can resolve its config** (for each service)

```bash
cd repos/payment_gateway
poetry run alembic current
```

Expected: prints nothing + exits 0 (no migrations yet, no head).

- [ ] **Step 4: Commit**

```bash
git add repos/*/db/migrations/env.py
git commit -m "feat: async alembic env driven by DATABASE_URL/ALEMBIC_DB_NAME"
```

---

## Phase 2 — Payment-Gateway service

Payment-Gateway is the simplest data service. We build it first as the reference implementation for idempotency.

### Task 2.1: `charges` and `idempotency_keys` models

**Files:**
- Create: `repos/payment_gateway/resources/charges/charge_model.py`
- Create: `repos/payment_gateway/resources/idempotency_keys/model.py`
- Modify: `repos/payment_gateway/db/models/models.py` (register imports)

- [ ] **Step 1: Write the charge model**

`repos/payment_gateway/resources/charges/charge_model.py`:

```python
import uuid
from sqlalchemy import BigInteger, String, DateTime, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from db.models.model_base import Base


class Charge(Base):
    __tablename__ = "charges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('CREATED','ACCEPTED','REJECTED')", name="charges_status_check"),
    )
```

- [ ] **Step 2: Write the idempotency_keys model**

`repos/payment_gateway/resources/idempotency_keys/model.py`:

```python
import uuid
from sqlalchemy import String, Integer, DateTime, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from db.models.model_base import Base


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    request_hash: Mapped[str] = mapped_column(String, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("state IN ('in_progress','completed')", name="idemkey_state_check"),
    )
```

- [ ] **Step 3: Register models**

Replace `repos/payment_gateway/db/models/models.py`:

```python
# pylint: disable=unused-import
from resources.charges.charge_model import Charge
from resources.idempotency_keys.model import IdempotencyKey
```

- [ ] **Step 4: Generate Alembic migration**

```bash
cd repos/payment_gateway
poetry run alembic revision --autogenerate -m "001 initial"
```

Expected: a new file under `db/migrations/versions/`. Inspect it and verify it creates `charges` and `idempotency_keys`.

- [ ] **Step 5: Apply migration**

```bash
poetry run alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade  -> <rev>, 001 initial`.

- [ ] **Step 6: Commit**

```bash
git add repos/payment_gateway
git commit -m "feat(payment_gateway): charges and idempotency_keys models + migration"
```

### Task 2.2: Payment provider port + mock Moyasar

**Files:**
- Create: `repos/payment_gateway/resources/providers/port.py`
- Create: `repos/payment_gateway/resources/providers/mock_moyasar.py`
- Create: `repos/payment_gateway/resources/providers/__init__.py`

- [ ] **Step 1: Define the port (Protocol)**

`repos/payment_gateway/resources/providers/port.py`:

```python
from typing import Protocol
from pydantic import BaseModel


class ProviderChargeRequest(BaseModel):
    amount_minor: int
    currency: str
    metadata: dict


class ProviderChargeResponse(BaseModel):
    payment_id: str
    accepted: bool


class PaymentProviderPort(Protocol):
    async def create_payment(self, req: ProviderChargeRequest) -> ProviderChargeResponse: ...
```

*Python note:* `typing.Protocol` is a structural interface — any class with matching method signatures satisfies it. No explicit `implements` needed (closer to Go interfaces than C# interfaces).

- [ ] **Step 2: Implement the mock Moyasar**

`repos/payment_gateway/resources/providers/mock_moyasar.py`:

```python
import asyncio
import os
import uuid
import hmac
import hashlib
import json
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .port import ProviderChargeRequest, ProviderChargeResponse

OMNIBUS_WEBHOOK_URL = os.getenv("OMNIBUS_WEBHOOK_URL", "http://localhost:8082/webhooks/moyasar")
WEBHOOK_SECRET = os.getenv("MOYASAR_WEBHOOK_SECRET", "dev-secret")
WEBHOOK_DELAY_SECONDS = float(os.getenv("MOYASAR_WEBHOOK_DELAY_SECONDS", "1.0"))


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


class MockMoyasarProvider:
    """Simulates Moyasar: accepts all requests, schedules a webhook back to Omnibus."""

    async def create_payment(self, req: ProviderChargeRequest) -> ProviderChargeResponse:
        payment_id = f"pay_{uuid.uuid4().hex[:12]}"
        asyncio.create_task(self._fire_webhook(payment_id, req))
        return ProviderChargeResponse(payment_id=payment_id, accepted=True)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=0.5, max=8))
    async def _post(self, body: bytes, sig: str) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                OMNIBUS_WEBHOOK_URL,
                content=body,
                headers={"Content-Type": "application/json", "X-Signature": sig},
            )
            resp.raise_for_status()

    async def _fire_webhook(self, payment_id: str, req: ProviderChargeRequest) -> None:
        await asyncio.sleep(WEBHOOK_DELAY_SECONDS)
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.paid",
            "payment_id": payment_id,
            "amount_minor": req.amount_minor,
            "currency": req.currency,
            "metadata": req.metadata,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        body = json.dumps(payload).encode()
        try:
            await self._post(body, _sign(body))
        except Exception:
            # In a real system this goes to a DLQ / retry queue. For the POC we just log.
            pass
```

- [ ] **Step 3: Commit**

```bash
git add repos/payment_gateway/resources/providers
git commit -m "feat(payment_gateway): payment provider port + mock Moyasar with signed webhook"
```

### Task 2.3: Idempotency helper (canonical implementation)

This module will be copied (with minor table-name tweaks) into omnibus and wallet.

**Files:**
- Create: `repos/payment_gateway/infra/idempotency.py`
- Create: `repos/payment_gateway/infra/__init__.py`
- Create: `repos/payment_gateway/tests/__init__.py`
- Create: `repos/payment_gateway/tests/test_idempotency_helper.py`

- [ ] **Step 1: Write failing tests first**

`repos/payment_gateway/tests/test_idempotency_helper.py`:

```python
import hashlib
import json
import pytest
from datetime import datetime, timezone, timedelta

from infra.idempotency import hash_body, IdempotencyConflict, IdempotencyInProgress


def test_hash_body_stable_for_equal_dicts():
    a = hash_body({"amount": 100, "currency": "SAR"})
    b = hash_body({"currency": "SAR", "amount": 100})
    assert a == b


def test_hash_body_differs_for_different_bodies():
    assert hash_body({"x": 1}) != hash_body({"x": 2})


# The DB-backed flow is exercised by integration tests in test_charge_service.
```

- [ ] **Step 2: Run and watch it fail**

```bash
cd repos/payment_gateway
poetry run pytest tests/test_idempotency_helper.py -v
```

Expected: ImportError — `infra.idempotency` does not exist.

- [ ] **Step 3: Implement the helper**

`repos/payment_gateway/infra/idempotency.py`:

```python
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from resources.idempotency_keys.model import IdempotencyKey

IDEMPOTENCY_TTL = timedelta(hours=24)


class IdempotencyConflict(Exception):
    """Same key, different request body — client bug. Surface as 422."""


class IdempotencyInProgress(Exception):
    """Same key, still running. Surface as 409."""


@dataclass
class IdempotentStart:
    new: bool                 # True if we just claimed the key
    cached_status: int | None
    cached_body: dict | None
    resource_id: Any | None


def hash_body(body: dict) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


async def start(session: AsyncSession, key: str, body: dict) -> IdempotentStart:
    """Attempt to claim a key. Must run inside the business txn."""
    rh = hash_body(body)
    expires = datetime.now(timezone.utc) + IDEMPOTENCY_TTL

    stmt = (
        insert(IdempotencyKey)
        .values(key=key, request_hash=rh, state="in_progress", expires_at=expires)
        .on_conflict_do_nothing(index_elements=["key"])
        .returning(IdempotencyKey.key)
    )
    result = await session.execute(stmt)
    inserted = result.scalar_one_or_none()
    if inserted is not None:
        return IdempotentStart(new=True, cached_status=None, cached_body=None, resource_id=None)

    existing = await session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key))
    assert existing is not None
    if existing.request_hash != rh:
        raise IdempotencyConflict()
    if existing.state == "in_progress":
        raise IdempotencyInProgress()
    return IdempotentStart(
        new=False,
        cached_status=existing.response_status,
        cached_body=existing.response_body,
        resource_id=existing.resource_id,
    )


async def complete(session: AsyncSession, key: str, status: int, body: dict, resource_id) -> None:
    row = await session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key))
    assert row is not None
    row.state = "completed"
    row.response_status = status
    row.response_body = body
    row.resource_id = resource_id
```

- [ ] **Step 4: Run tests, expect pass**

```bash
poetry run pytest tests/test_idempotency_helper.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add repos/payment_gateway/infra repos/payment_gateway/tests
git commit -m "feat(payment_gateway): idempotency helper + hash tests"
```

### Task 2.4: Charge DAL, schema, and service

**Files:**
- Create: `repos/payment_gateway/resources/charges/charge_schema.py`
- Create: `repos/payment_gateway/resources/charges/charge_dal.py`
- Create: `repos/payment_gateway/resources/charges/charge_service.py`
- Create: `repos/payment_gateway/tests/test_charge_service.py`

- [ ] **Step 1: Schema**

```python
# charge_schema.py
import uuid
from pydantic import BaseModel, Field


class CreateChargeRequest(BaseModel):
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    metadata: dict = Field(default_factory=dict)


class ChargeResponse(BaseModel):
    charge_id: uuid.UUID
    status: str
    provider_payment_id: str | None
```

- [ ] **Step 2: DAL**

```python
# charge_dal.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from resources.charges.charge_model import Charge


async def insert_charge(session: AsyncSession, *, amount_minor: int, currency: str, metadata: dict, provider: str) -> Charge:
    charge = Charge(
        id=uuid.uuid4(),
        amount_minor=amount_minor,
        currency=currency,
        provider=provider,
        metadata_=metadata,
        status="CREATED",
    )
    session.add(charge)
    await session.flush()
    return charge


async def set_accepted(session: AsyncSession, charge_id: uuid.UUID, provider_payment_id: str) -> None:
    charge = await session.get(Charge, charge_id)
    assert charge is not None
    charge.status = "ACCEPTED"
    charge.provider_payment_id = provider_payment_id


async def set_rejected(session: AsyncSession, charge_id: uuid.UUID) -> None:
    charge = await session.get(Charge, charge_id)
    assert charge is not None
    charge.status = "REJECTED"
```

- [ ] **Step 3: Write failing service test**

`repos/payment_gateway/tests/test_charge_service.py`:

```python
import pytest
from unittest.mock import AsyncMock
from resources.providers.port import ProviderChargeResponse
from resources.charges.charge_service import ChargeService
from resources.charges.charge_schema import CreateChargeRequest


@pytest.mark.asyncio
async def test_service_inserts_charge_and_marks_accepted_on_provider_success(db_session):
    provider = AsyncMock()
    provider.create_payment.return_value = ProviderChargeResponse(payment_id="pay_x", accepted=True)

    svc = ChargeService(session=db_session, provider=provider)
    result = await svc.create(
        CreateChargeRequest(amount_minor=1000, currency="SAR", metadata={"top_up_id": "abc"}),
        idempotency_key="k1",
    )
    assert result.status == "ACCEPTED"
    assert result.provider_payment_id == "pay_x"


@pytest.mark.asyncio
async def test_service_marks_rejected_when_provider_says_no(db_session):
    provider = AsyncMock()
    provider.create_payment.return_value = ProviderChargeResponse(payment_id="pay_y", accepted=False)

    svc = ChargeService(session=db_session, provider=provider)
    result = await svc.create(
        CreateChargeRequest(amount_minor=1000, currency="SAR", metadata={}),
        idempotency_key="k2",
    )
    assert result.status == "REJECTED"
```

- [ ] **Step 4: Create `conftest.py` with `db_session` fixture**

`repos/payment_gateway/tests/conftest.py`:

```python
import os
import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models.model_base import Base
import db.models.models  # noqa: F401


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    url = os.getenv(
        "TEST_DATABASE_URL",
        "cockroachdb+asyncpg://root@localhost:26257/payment_gateway_test?sslmode=disable",
    )
    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        yield session
    await engine.dispose()
```

Run once manually to create the test DB:

```bash
docker exec database /cockroach/cockroach sql --insecure -e "CREATE DATABASE IF NOT EXISTS payment_gateway_test"
```

- [ ] **Step 5: Run tests and watch them fail**

```bash
poetry run pytest tests/test_charge_service.py -v
```

Expected: ImportError — `ChargeService` does not exist.

- [ ] **Step 6: Implement the service**

`repos/payment_gateway/resources/charges/charge_service.py`:

```python
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from infra import idempotency
from resources.charges import charge_dal
from resources.charges.charge_schema import CreateChargeRequest, ChargeResponse
from resources.providers.port import PaymentProviderPort, ProviderChargeRequest


@dataclass
class ChargeService:
    session: AsyncSession
    provider: PaymentProviderPort

    async def create(self, req: CreateChargeRequest, idempotency_key: str) -> ChargeResponse:
        idem = await idempotency.start(self.session, idempotency_key, req.model_dump())
        if not idem.new and idem.cached_body is not None:
            return ChargeResponse(**idem.cached_body)

        charge = await charge_dal.insert_charge(
            self.session,
            amount_minor=req.amount_minor,
            currency=req.currency,
            metadata=req.metadata,
            provider="moyasar",
        )

        prov = await self.provider.create_payment(
            ProviderChargeRequest(
                amount_minor=req.amount_minor, currency=req.currency, metadata=req.metadata
            )
        )

        if prov.accepted:
            await charge_dal.set_accepted(self.session, charge.id, prov.payment_id)
            response = ChargeResponse(charge_id=charge.id, status="ACCEPTED", provider_payment_id=prov.payment_id)
        else:
            await charge_dal.set_rejected(self.session, charge.id)
            response = ChargeResponse(charge_id=charge.id, status="REJECTED", provider_payment_id=prov.payment_id)

        await idempotency.complete(
            self.session, idempotency_key, status=200, body=response.model_dump(mode="json"), resource_id=charge.id
        )
        return response
```

- [ ] **Step 7: Run tests and expect pass**

```bash
poetry run pytest tests/test_charge_service.py -v
```

Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add repos/payment_gateway
git commit -m "feat(payment_gateway): charge service with idempotent create"
```

### Task 2.5: `/charges` controller + integration test

**Files:**
- Create: `repos/payment_gateway/api/controllers/charge_controller.py`
- Modify: `repos/payment_gateway/api/routes.py`
- Modify: `repos/payment_gateway/api/main.py` (port 8081)
- Create: `repos/payment_gateway/tests/test_charge_controller.py`

- [ ] **Step 1: Controller**

```python
# api/controllers/charge_controller.py
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import session_dependency
from infra.idempotency import IdempotencyConflict, IdempotencyInProgress
from resources.charges.charge_schema import CreateChargeRequest, ChargeResponse
from resources.charges.charge_service import ChargeService
from resources.providers.mock_moyasar import MockMoyasarProvider

router = APIRouter()

_provider = MockMoyasarProvider()


async def _session():
    async for s in session_dependency("payment_gateway"):
        yield s


@router.post("", response_model=ChargeResponse, status_code=status.HTTP_200_OK)
async def create_charge(
    req: CreateChargeRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(_session),
) -> ChargeResponse:
    svc = ChargeService(session=session, provider=_provider)
    try:
        return await svc.create(req, idempotency_key=idempotency_key)
    except IdempotencyConflict:
        raise HTTPException(status_code=422, detail="Idempotency-Key reused with different body")
    except IdempotencyInProgress:
        raise HTTPException(status_code=409, detail="Request with this Idempotency-Key is in progress")
```

- [ ] **Step 2: Wire route**

Edit `api/routes.py`:

```python
from api.controllers.charge_controller import router as ChargeRouter
from api.controllers.test_controller import router as TestRouter


def init_routes(app):
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])
    app.include_router(ChargeRouter, prefix="/charges", tags=["Charges"])
    return app
```

Verify `api/main.py` runs alembic upgrade on startup and listens on 8081. (Scaffold already does 8081; leave as is.)

- [ ] **Step 3: Write integration test (using TestClient)**

```python
# tests/test_charge_controller.py
import uuid
from fastapi.testclient import TestClient
from api.main import app


def test_duplicate_idempotency_key_returns_same_response(db_session):
    client = TestClient(app)
    key = str(uuid.uuid4())
    body = {"amount_minor": 5000, "currency": "SAR", "metadata": {"top_up_id": str(uuid.uuid4())}}

    r1 = client.post("/charges", json=body, headers={"Idempotency-Key": key})
    r2 = client.post("/charges", json=body, headers={"Idempotency-Key": key})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()


def test_same_key_different_body_returns_422(db_session):
    client = TestClient(app)
    key = str(uuid.uuid4())
    r1 = client.post("/charges", json={"amount_minor": 100, "currency": "SAR", "metadata": {}}, headers={"Idempotency-Key": key})
    r2 = client.post("/charges", json={"amount_minor": 200, "currency": "SAR", "metadata": {}}, headers={"Idempotency-Key": key})
    assert r1.status_code == 200
    assert r2.status_code == 422
```

- [ ] **Step 4: Run, expect pass**

```bash
poetry run pytest tests/test_charge_controller.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Smoke-test manually**

```bash
poetry run poe api_service &
curl -X POST http://localhost:8081/charges \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"amount_minor": 1000, "currency": "SAR", "metadata": {"top_up_id": "00000000-0000-0000-0000-000000000001"}}'
```

Expected: `200 { "charge_id": "...", "status": "ACCEPTED", "provider_payment_id": "pay_..." }` and omnibus webhook fires (but will 404 until we build omnibus).

Kill the process: `kill %1`.

- [ ] **Step 6: Commit**

```bash
git add repos/payment_gateway
git commit -m "feat(payment_gateway): POST /charges with idempotency + dup/conflict tests"
```

---

## Phase 3 — Omnibus service

Omnibus is the most interesting service: it receives webhooks, uses the outbox pattern, and publishes settlement events.

### Task 3.1: Create the missing `api/` layer for omnibus

**Files:**
- Create: `repos/omnibus/api/__init__.py`
- Create: `repos/omnibus/api/main.py`
- Create: `repos/omnibus/api/routes.py`
- Create: `repos/omnibus/api/controllers/__init__.py`
- Create: `repos/omnibus/api/controllers/test_controller.py`

- [ ] **Step 1: Minimal bootable app**

`api/main.py`:

```python
from fastapi import FastAPI
from uvicorn import run
from api.routes import init_routes
from alembic import command
from alembic.config import Config

app: FastAPI = init_routes(
    FastAPI(title="IronWallet Omnibus", description="Settlement ledger and webhook receiver.")
)

if __name__ == "__main__":
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    run("api.main:app", host="0.0.0.0", port=8082, reload=True)
```

`api/routes.py`:

```python
from api.controllers.test_controller import router as TestRouter


def init_routes(app):
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])
    return app
```

`api/controllers/test_controller.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def test_route():
    return {"message": "omnibus up"}
```

- [ ] **Step 2: Add poe task**

Edit `repos/omnibus/pyproject.toml` — add under `[tool.poe.tasks]`:

```toml
[tool.poe.tasks]
api_service = { shell = 'export APP__ROOT_PATH=$(pwd) && python3 -m api.main' }
```

- [ ] **Step 3: Verify it boots**

```bash
cd repos/omnibus
poetry run python -c "from api.main import app; print(app.title)"
```

Expected: `IronWallet Omnibus`.

- [ ] **Step 4: Commit**

```bash
git add repos/omnibus
git commit -m "feat(omnibus): add missing FastAPI api/ layer"
```

### Task 3.2: Omnibus models + migration

**Files:**
- Create: `repos/omnibus/resources/statements/statement_model.py` (new, replacing `statment_*` typo)
- Create: `repos/omnibus/resources/processed_webhooks/model.py`
- Create: `repos/omnibus/resources/outbox/model.py`
- Create: `repos/omnibus/resources/idempotency_keys/model.py`
- Modify: `repos/omnibus/db/models/models.py`
- Delete: the typo'd `statment_*` files (empty, so safe to remove)

- [ ] **Step 1: Remove typo'd empty files**

```bash
rm -rf repos/omnibus/resources/statements
mkdir repos/omnibus/resources/statements
touch repos/omnibus/resources/statements/__init__.py
```

- [ ] **Step 2: `statement_model.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, CheckConstraint, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.models.model_base import Base


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    virtual_iban: Mapped[str | None] = mapped_column(String, nullable=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_ref: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("kind IN ('top_up','fund_transfer')", name="statements_kind_check"),
        UniqueConstraint("kind", "source_ref", name="statements_kind_source_ref_unique"),
    )
```

- [ ] **Step 3: `processed_webhooks/model.py`**

```python
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from db.models.model_base import Base


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"

    provider: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: `outbox/model.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.models.model_base import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("outbox_unpublished_idx", "published_at", postgresql_where=(published_at.is_(None))),
    )
```

- [ ] **Step 5: `idempotency_keys/model.py` — same shape as Payment-Gateway's (copy it)**

Copy from `repos/payment_gateway/resources/idempotency_keys/model.py` verbatim.

- [ ] **Step 6: Register all models**

`repos/omnibus/db/models/models.py`:

```python
# pylint: disable=unused-import
from resources.statements.statement_model import Statement
from resources.processed_webhooks.model import ProcessedWebhook
from resources.outbox.model import OutboxEvent
from resources.idempotency_keys.model import IdempotencyKey
```

- [ ] **Step 7: Migration**

```bash
cd repos/omnibus
ALEMBIC_DB_NAME=omnibus poetry run alembic revision --autogenerate -m "001 initial"
ALEMBIC_DB_NAME=omnibus poetry run alembic upgrade head
```

Expected: creates 4 tables.

- [ ] **Step 8: Commit**

```bash
git add repos/omnibus
git commit -m "feat(omnibus): statements, processed_webhooks, outbox_events, idempotency_keys + migration"
```

### Task 3.3: Idempotency helper (copied from payment_gateway)

- [ ] **Step 1: Copy `infra/idempotency.py`**

```bash
cp repos/payment_gateway/infra/idempotency.py repos/omnibus/infra/idempotency.py
mkdir -p repos/omnibus/infra && touch repos/omnibus/infra/__init__.py
```

Module imports `resources.idempotency_keys.model` which exists in both — no changes needed.

- [ ] **Step 2: Commit**

```bash
git add repos/omnibus/infra
git commit -m "feat(omnibus): idempotency helper (copied from payment_gateway)"
```

### Task 3.4: Broker publisher + event types

**Files:**
- Create: `repos/omnibus/infra/events.py`
- Create: `repos/omnibus/infra/broker.py`

- [ ] **Step 1: Event type constants**

`infra/events.py`:

```python
RK_SETTLEMENT_COMPLETED = "omnibus.settlement.completed"
EXCHANGE = "iron_wallet"
```

- [ ] **Step 2: aio-pika publisher wrapper**

`infra/broker.py`:

```python
import json
import os

import aio_pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


class Broker:
    def __init__(self) -> None:
        self._conn: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def start(self, exchange_name: str) -> None:
        self._conn = await aio_pika.connect_robust(RABBITMQ_URL)
        self._channel = await self._conn.channel()
        self._exchange = await self._channel.declare_exchange(
            exchange_name, type=aio_pika.ExchangeType.TOPIC, durable=True
        )

    async def publish(self, routing_key: str, payload: dict) -> None:
        assert self._exchange is not None, "broker not started"
        body = json.dumps(payload).encode()
        msg = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=str(payload.get("id") or payload.get("event_id") or ""),
        )
        await self._exchange.publish(msg, routing_key=routing_key)

    async def stop(self) -> None:
        if self._conn is not None:
            await self._conn.close()
```

- [ ] **Step 3: Commit**

```bash
git add repos/omnibus/infra
git commit -m "feat(omnibus): aio-pika broker wrapper + event constants"
```

### Task 3.5: Outbox helper + drain task

**Files:**
- Create: `repos/omnibus/infra/outbox.py`

- [ ] **Step 1: Outbox helpers**

```python
# infra/outbox.py
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from resources.outbox.model import OutboxEvent
from infra.broker import Broker
from infra.events import EXCHANGE


async def enqueue(session: AsyncSession, *, aggregate_id: uuid.UUID, type_: str, payload: dict) -> None:
    session.add(OutboxEvent(id=uuid.uuid4(), aggregate_id=aggregate_id, type=type_, payload=payload))


async def drain_once(sm: async_sessionmaker[AsyncSession], broker: Broker, routing_key_for_type) -> int:
    """Returns number of events published."""
    published = 0
    async with sm() as session:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.occurred_at)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
        rows = (await session.execute(stmt)).scalars().all()
        for row in rows:
            rk = routing_key_for_type(row.type)
            await broker.publish(rk, {
                "id": str(row.id),
                "aggregate_id": str(row.aggregate_id),
                "type": row.type,
                "payload": row.payload,
                "occurred_at": row.occurred_at.isoformat(),
            })
            row.published_at = datetime.now(timezone.utc)
            published += 1
        await session.commit()
    return published


async def run_drain_loop(sm, broker: Broker, routing_key_for_type, interval_seconds: float = 0.5) -> None:
    while True:
        try:
            n = await drain_once(sm, broker, routing_key_for_type)
            if n == 0:
                await asyncio.sleep(interval_seconds)
        except Exception:
            await asyncio.sleep(interval_seconds)
```

- [ ] **Step 2: Commit**

```bash
git add repos/omnibus/infra/outbox.py
git commit -m "feat(omnibus): outbox enqueue + drain loop with SKIP LOCKED"
```

### Task 3.6: Webhook controller + HMAC verification + tests

**Files:**
- Create: `repos/omnibus/api/controllers/webhook_controller.py`
- Create: `repos/omnibus/resources/statements/statement_service.py`
- Create: `repos/omnibus/tests/conftest.py`
- Create: `repos/omnibus/tests/test_webhook_controller.py`
- Modify: `api/routes.py`

- [ ] **Step 1: Statement service**

`resources/statements/statement_service.py`:

```python
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from resources.statements.statement_model import Statement
from resources.processed_webhooks.model import ProcessedWebhook
from resources.outbox import outbox_helper  # alias below
from infra import outbox
from infra.events import RK_SETTLEMENT_COMPLETED


class WebhookAlreadyProcessed(Exception):
    pass


async def record_provider_webhook(
    session: AsyncSession,
    *,
    provider: str,
    event_id: str,
    amount_minor: int,
    currency: str,
    correlation_id: uuid.UUID | None,
    source_ref: str,
    kind: str,
) -> uuid.UUID:
    dedup = (
        insert(ProcessedWebhook)
        .values(provider=provider, event_id=event_id)
        .on_conflict_do_nothing(index_elements=["provider", "event_id"])
    )
    result = await session.execute(dedup)
    if result.rowcount == 0:
        raise WebhookAlreadyProcessed()

    statement_id = uuid.uuid4()
    session.add(Statement(
        id=statement_id, kind=kind, amount_minor=amount_minor, currency=currency,
        correlation_id=correlation_id, source_ref=source_ref,
    ))
    await outbox.enqueue(
        session,
        aggregate_id=statement_id,
        type_="settlement.completed",
        payload={
            "statement_id": str(statement_id),
            "kind": kind,
            "amount_minor": amount_minor,
            "currency": currency,
            "correlation_id": str(correlation_id) if correlation_id else None,
        },
    )
    return statement_id
```

- [ ] **Step 2: Webhook controller with HMAC check**

`api/controllers/webhook_controller.py`:

```python
import hmac
import hashlib
import os
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import session_dependency
from resources.statements.statement_service import record_provider_webhook, WebhookAlreadyProcessed

router = APIRouter()

WEBHOOK_SECRET = os.getenv("MOYASAR_WEBHOOK_SECRET", "dev-secret")


def _verify(body: bytes, sig: str | None) -> bool:
    if sig is None:
        return False
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


async def _session():
    async for s in session_dependency("omnibus"):
        yield s


@router.post("/moyasar")
async def moyasar_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
    session: AsyncSession = Depends(_session),
):
    raw = await request.body()
    if not _verify(raw, x_signature):
        raise HTTPException(status_code=401, detail="bad signature")

    import json
    payload = json.loads(raw)
    correlation = payload.get("metadata", {}).get("top_up_id")
    try:
        await record_provider_webhook(
            session,
            provider="moyasar",
            event_id=payload["event_id"],
            amount_minor=payload["amount_minor"],
            currency=payload["currency"],
            correlation_id=uuid.UUID(correlation) if correlation else None,
            source_ref=payload["event_id"],
            kind="top_up",
        )
        return {"status": "recorded"}
    except WebhookAlreadyProcessed:
        return {"status": "duplicate"}
```

- [ ] **Step 3: Wire route**

```python
# api/routes.py
from api.controllers.test_controller import router as TestRouter
from api.controllers.webhook_controller import router as WebhookRouter


def init_routes(app):
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])
    app.include_router(WebhookRouter, prefix="/webhooks", tags=["Webhooks"])
    return app
```

- [ ] **Step 4: Conftest**

`repos/omnibus/tests/conftest.py`:

```python
import os
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from db.models.model_base import Base
import db.models.models  # noqa


@pytest_asyncio.fixture
async def db_session():
    url = os.getenv("TEST_DATABASE_URL", "cockroachdb+asyncpg://root@localhost:26257/omnibus_test?sslmode=disable")
    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        yield session
    await engine.dispose()
```

Create test DB:
```bash
docker exec database /cockroach/cockroach sql --insecure -e "CREATE DATABASE IF NOT EXISTS omnibus_test"
```

- [ ] **Step 5: Tests**

`repos/omnibus/tests/test_webhook_controller.py`:

```python
import hmac
import hashlib
import json
import uuid
from fastapi.testclient import TestClient

from api.main import app


SECRET = "dev-secret"


def _sign(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_rejects_bad_signature(db_session):
    client = TestClient(app)
    body = b'{"event_id":"evt1"}'
    r = client.post("/webhooks/moyasar", content=body, headers={"X-Signature": "wrong"})
    assert r.status_code == 401


def test_webhook_records_and_dedupes(db_session):
    client = TestClient(app)
    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "payment.paid",
        "payment_id": "pay_x",
        "amount_minor": 5000,
        "currency": "SAR",
        "metadata": {"top_up_id": str(uuid.uuid4())},
    }
    body = json.dumps(payload).encode()
    r1 = client.post("/webhooks/moyasar", content=body, headers={"X-Signature": _sign(body), "Content-Type": "application/json"})
    r2 = client.post("/webhooks/moyasar", content=body, headers={"X-Signature": _sign(body), "Content-Type": "application/json"})

    assert r1.status_code == 200
    assert r1.json() == {"status": "recorded"}
    assert r2.json() == {"status": "duplicate"}
```

- [ ] **Step 6: Run and expect pass**

```bash
poetry run pytest tests/test_webhook_controller.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add repos/omnibus
git commit -m "feat(omnibus): signed webhook -> statement + outbox + dedup"
```

### Task 3.7: `/bank-transfers` admin endpoint

**Files:**
- Create: `repos/omnibus/api/controllers/bank_transfer_controller.py`
- Modify: `repos/omnibus/api/routes.py`
- Create: `repos/omnibus/tests/test_bank_transfer_controller.py`

- [ ] **Step 1: Controller**

```python
# api/controllers/bank_transfer_controller.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from db.session import session_dependency
from resources.statements.statement_service import record_bank_transfer, BankTransferDuplicate

router = APIRouter()


class BankTransferIn(BaseModel):
    virtual_iban: str
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    bank_reference: str
    wallet_id: uuid.UUID


async def _session():
    async for s in session_dependency("omnibus"):
        yield s


@router.post("")
async def create_bank_transfer(body: BankTransferIn, session: AsyncSession = Depends(_session)):
    try:
        statement_id = await record_bank_transfer(session, body=body)
        return {"statement_id": str(statement_id)}
    except BankTransferDuplicate:
        raise HTTPException(status_code=409, detail="duplicate bank_reference")
```

- [ ] **Step 2: Add `record_bank_transfer` to `statement_service.py`**

Append:

```python
class BankTransferDuplicate(Exception):
    pass


async def record_bank_transfer(session, *, body) -> uuid.UUID:
    statement_id = uuid.uuid4()
    session.add(Statement(
        id=statement_id, kind="fund_transfer",
        amount_minor=body.amount_minor, currency=body.currency,
        virtual_iban=body.virtual_iban, correlation_id=body.wallet_id,
        source_ref=body.bank_reference,
    ))
    try:
        await session.flush()
    except Exception as e:
        if "statements_kind_source_ref_unique" in str(e):
            raise BankTransferDuplicate() from e
        raise
    await outbox.enqueue(
        session,
        aggregate_id=statement_id,
        type_="settlement.completed",
        payload={
            "statement_id": str(statement_id),
            "kind": "fund_transfer",
            "amount_minor": body.amount_minor,
            "currency": body.currency,
            "wallet_id": str(body.wallet_id),
            "virtual_iban": body.virtual_iban,
        },
    )
    return statement_id
```

- [ ] **Step 3: Wire route + add test**

Route in `api/routes.py`:
```python
from api.controllers.bank_transfer_controller import router as BankTransferRouter
app.include_router(BankTransferRouter, prefix="/bank-transfers", tags=["BankTransfers"])
```

Test (`tests/test_bank_transfer_controller.py`):

```python
import uuid
from fastapi.testclient import TestClient
from api.main import app


def test_bank_transfer_creates_statement_and_dedupes(db_session):
    client = TestClient(app)
    body = {
        "virtual_iban": "SA00",
        "amount_minor": 10000,
        "currency": "SAR",
        "bank_reference": "ref-" + uuid.uuid4().hex,
        "wallet_id": str(uuid.uuid4()),
    }
    r1 = client.post("/bank-transfers", json=body)
    r2 = client.post("/bank-transfers", json=body)
    assert r1.status_code == 200
    assert "statement_id" in r1.json()
    assert r2.status_code == 409
```

- [ ] **Step 4: Run tests**

```bash
poetry run pytest tests/test_bank_transfer_controller.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add repos/omnibus
git commit -m "feat(omnibus): POST /bank-transfers admin endpoint with bank_reference dedup"
```

### Task 3.8: Wire broker + outbox drain on startup

**Files:**
- Modify: `repos/omnibus/api/main.py`

- [ ] **Step 1: Add lifespan handler**

Replace `repos/omnibus/api/main.py`:

```python
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
    run("api.main:app", host="0.0.0.0", port=8082, reload=False)  # reload=False so the drain task survives
```

- [ ] **Step 2: Manual smoke test**

```bash
cd repos/omnibus
poetry run poe api_service &
sleep 3
curl -X POST http://localhost:8082/bank-transfers -H "Content-Type: application/json" \
  -d '{"virtual_iban":"SA00","amount_minor":1000,"currency":"SAR","bank_reference":"bk-001","wallet_id":"00000000-0000-0000-0000-000000000001"}'
# Open RabbitMQ UI at http://localhost:15672 (guest/guest) and verify a message lands on the iron_wallet exchange with routing key omnibus.settlement.completed.
kill %1
```

- [ ] **Step 3: Commit**

```bash
git add repos/omnibus/api/main.py
git commit -m "feat(omnibus): start broker + outbox drain on FastAPI lifespan"
```

---

## Phase 4 — Investment-Wallet service

Wallet is the most complex service. It orchestrates top-up, consumes settlement events, runs its own outbox, and enforces state transitions.

### Task 4.1: All wallet models + migration

**Files:**
- Replace: `repos/investment-wallet/resources/wallets/wallet_model.py` (scaffold has a stub)
- Create: `repos/investment-wallet/resources/top_ups/top_up_model.py`
- Create: `repos/investment-wallet/resources/fund_transfers/fund_transfer_model.py`
- Create: `repos/investment-wallet/resources/processed_events/model.py`
- Create: `repos/investment-wallet/resources/outbox/model.py`
- Create: `repos/investment-wallet/resources/idempotency_keys/model.py`
- Modify: `repos/investment-wallet/db/models/models.py`

- [ ] **Step 1: Copy the canonical models from Omnibus/Payment-Gateway where applicable**

```bash
cp repos/omnibus/resources/outbox/model.py repos/investment-wallet/resources/outbox/model.py
cp repos/payment_gateway/resources/idempotency_keys/model.py repos/investment-wallet/resources/idempotency_keys/model.py
mkdir -p repos/investment-wallet/resources/{top_ups,fund_transfers,processed_events}
```

- [ ] **Step 2: Replace wallet model**

`resources/wallets/wallet_model.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.models.model_base import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    balance_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 3: `top_up_model.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, CheckConstraint, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.models.model_base import Base


class TopUp(Base):
    __tablename__ = "top_ups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    charge_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('PENDING','PROCESSING','PAID','FAILED')", name="top_ups_status_check"),
        Index("top_ups_wallet_status_idx", "wallet_id", "status"),
    )
```

- [ ] **Step 4: `fund_transfer_model.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.models.model_base import Base


class FundTransfer(Base):
    __tablename__ = "fund_transfers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PAID")
    bank_reference: Mapped[str] = mapped_column(String, nullable=False)
    statement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: `processed_events/model.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.models.model_base import Base


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 6: Register models**

`repos/investment-wallet/db/models/models.py`:

```python
# pylint: disable=unused-import
from resources.wallets.wallet_model import Wallet
from resources.top_ups.top_up_model import TopUp
from resources.fund_transfers.fund_transfer_model import FundTransfer
from resources.processed_events.model import ProcessedEvent
from resources.outbox.model import OutboxEvent
from resources.idempotency_keys.model import IdempotencyKey
```

- [ ] **Step 7: Migration**

```bash
cd repos/investment-wallet
ALEMBIC_DB_NAME=investment_wallet poetry run alembic revision --autogenerate -m "001 initial"
ALEMBIC_DB_NAME=investment_wallet poetry run alembic upgrade head
```

- [ ] **Step 8: Commit**

```bash
git add repos/investment-wallet
git commit -m "feat(wallet): wallets, top_ups, fund_transfers, processed_events, outbox, idempotency_keys + migration"
```

### Task 4.2: State-machine helper + tests

**Files:**
- Create: `repos/investment-wallet/infra/state_machine.py`
- Create: `repos/investment-wallet/tests/test_state_machine.py`
- Create: `repos/investment-wallet/tests/conftest.py` (same pattern as other services)
- Create: `repos/investment-wallet/infra/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Copy conftest + create test DB**

```bash
cp repos/omnibus/tests/conftest.py repos/investment-wallet/tests/conftest.py
# Then change the URL default in conftest.py to the wallet test DB:
#   cockroachdb+asyncpg://root@localhost:26257/investment_wallet_test?sslmode=disable
docker exec database /cockroach/cockroach sql --insecure -e "CREATE DATABASE IF NOT EXISTS investment_wallet_test"
```

- [ ] **Step 2: Write failing test**

`tests/test_state_machine.py`:

```python
import uuid
import pytest
from sqlalchemy import select

from resources.wallets.wallet_model import Wallet
from resources.top_ups.top_up_model import TopUp
from infra.state_machine import guarded_transition, IllegalStateTransition


@pytest.mark.asyncio
async def test_transition_succeeds_when_status_matches(db_session):
    wallet = Wallet(id=uuid.uuid4(), user_id=uuid.uuid4(), balance_minor=0, currency="SAR")
    db_session.add(wallet)
    topup = TopUp(id=uuid.uuid4(), wallet_id=wallet.id, amount_minor=100, currency="SAR", status="PENDING")
    db_session.add(topup)
    await db_session.flush()

    await guarded_transition(db_session, TopUp, topup.id, expected="PENDING", new="PROCESSING")
    refreshed = await db_session.scalar(select(TopUp).where(TopUp.id == topup.id))
    assert refreshed.status == "PROCESSING"


@pytest.mark.asyncio
async def test_transition_raises_on_illegal(db_session):
    wallet = Wallet(id=uuid.uuid4(), user_id=uuid.uuid4(), balance_minor=0, currency="SAR")
    db_session.add(wallet)
    topup = TopUp(id=uuid.uuid4(), wallet_id=wallet.id, amount_minor=100, currency="SAR", status="PENDING")
    db_session.add(topup)
    await db_session.flush()

    with pytest.raises(IllegalStateTransition):
        await guarded_transition(db_session, TopUp, topup.id, expected="PROCESSING", new="PAID")
```

- [ ] **Step 3: Run, expect fail (module missing)**

```bash
poetry run pytest tests/test_state_machine.py -v
```

- [ ] **Step 4: Implement**

`infra/state_machine.py`:

```python
import uuid
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession


class IllegalStateTransition(Exception):
    pass


async def guarded_transition(session: AsyncSession, model, row_id: uuid.UUID, *, expected: str, new: str) -> None:
    result = await session.execute(
        update(model).where(model.id == row_id, model.status == expected).values(status=new).returning(model.id)
    )
    if result.scalar_one_or_none() is None:
        raise IllegalStateTransition(f"{model.__name__}({row_id}) not in state {expected!r}")
```

- [ ] **Step 5: Run, expect pass**

```bash
poetry run pytest tests/test_state_machine.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add repos/investment-wallet
git commit -m "feat(wallet): state-machine guard with legal/illegal transition tests"
```

### Task 4.3: Copy idempotency helper, add events + broker

**Files:**
- Create: `repos/investment-wallet/infra/idempotency.py` (copy from payment_gateway)
- Create: `repos/investment-wallet/infra/broker.py` (copy from omnibus)
- Create: `repos/investment-wallet/infra/events.py`
- Create: `repos/investment-wallet/infra/outbox.py` (copy from omnibus)
- Create: `repos/investment-wallet/infra/http_client.py`

- [ ] **Step 1: Copies**

```bash
cp repos/payment_gateway/infra/idempotency.py repos/investment-wallet/infra/idempotency.py
cp repos/omnibus/infra/broker.py repos/investment-wallet/infra/broker.py
cp repos/omnibus/infra/outbox.py repos/investment-wallet/infra/outbox.py
```

- [ ] **Step 2: Events**

`infra/events.py`:

```python
RK_TOP_UP_PAID = "wallet.top_up.paid"
RK_FUND_TRANSFER_PAID = "wallet.fund_transfer.paid"
EXCHANGE = "iron_wallet"
CONSUMER_QUEUE = "wallet.settlements"
CONSUMER_BINDING = "omnibus.settlement.*"
DLQ_NAME = "wallet.settlements.dlq"
```

- [ ] **Step 3: HTTP client to Payment-Gateway**

`infra/http_client.py`:

```python
import os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

PAYMENT_GATEWAY_URL = os.getenv("PAYMENT_GATEWAY_URL", "http://localhost:8081")


class PaymentGatewayClient:
    def __init__(self, base_url: str = PAYMENT_GATEWAY_URL) -> None:
        self._base_url = base_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4))
    async def create_charge(self, *, amount_minor: int, currency: str, metadata: dict, idempotency_key: str) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/charges",
                json={"amount_minor": amount_minor, "currency": currency, "metadata": metadata},
                headers={"Idempotency-Key": idempotency_key},
            )
            resp.raise_for_status()
            return resp.json()
```

- [ ] **Step 4: Commit**

```bash
git add repos/investment-wallet/infra
git commit -m "feat(wallet): infra helpers — idempotency, broker, outbox, events, http client"
```

### Task 4.4: `top_up_service.create` + tests

**Files:**
- Create: `repos/investment-wallet/resources/top_ups/top_up_schema.py`
- Create: `repos/investment-wallet/resources/top_ups/top_up_dal.py`
- Create: `repos/investment-wallet/resources/top_ups/top_up_service.py`
- Create: `repos/investment-wallet/resources/wallets/wallet_dal.py`
- Create: `repos/investment-wallet/tests/test_top_up_service.py`

- [ ] **Step 1: Schemas**

```python
# top_up_schema.py
import uuid
from pydantic import BaseModel, Field


class CreateTopUpRequest(BaseModel):
    wallet_id: uuid.UUID
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)


class TopUpResponse(BaseModel):
    top_up_id: uuid.UUID
    status: str
```

- [ ] **Step 2: DAL**

```python
# top_up_dal.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from resources.top_ups.top_up_model import TopUp


async def insert_pending(session: AsyncSession, *, wallet_id, amount_minor, currency) -> TopUp:
    t = TopUp(id=uuid.uuid4(), wallet_id=wallet_id, amount_minor=amount_minor, currency=currency, status="PENDING")
    session.add(t)
    await session.flush()
    return t


async def set_charge_id(session: AsyncSession, top_up_id: uuid.UUID, charge_id: uuid.UUID) -> None:
    t = await session.get(TopUp, top_up_id)
    assert t is not None
    t.charge_id = charge_id


async def set_failed(session: AsyncSession, top_up_id: uuid.UUID, reason: str) -> None:
    t = await session.get(TopUp, top_up_id)
    assert t is not None
    t.status = "FAILED"
    t.failure_reason = reason
```

- [ ] **Step 3: Failing test**

`tests/test_top_up_service.py`:

```python
import uuid
import pytest
from unittest.mock import AsyncMock
from sqlalchemy import select

from resources.wallets.wallet_model import Wallet
from resources.top_ups.top_up_model import TopUp
from resources.top_ups.top_up_service import TopUpService
from resources.top_ups.top_up_schema import CreateTopUpRequest


@pytest.mark.asyncio
async def test_create_top_up_transitions_to_processing_when_charge_accepted(db_session):
    wallet = Wallet(id=uuid.uuid4(), user_id=uuid.uuid4(), balance_minor=0, currency="SAR")
    db_session.add(wallet)
    await db_session.flush()

    pg = AsyncMock()
    pg.create_charge.return_value = {
        "charge_id": str(uuid.uuid4()), "status": "ACCEPTED", "provider_payment_id": "pay_x"
    }
    svc = TopUpService(session=db_session, payment_gateway=pg)
    resp = await svc.create(
        CreateTopUpRequest(wallet_id=wallet.id, amount_minor=1000, currency="SAR"),
        idempotency_key="k1",
    )
    assert resp.status == "PROCESSING"
    row = await db_session.scalar(select(TopUp).where(TopUp.id == resp.top_up_id))
    assert row.status == "PROCESSING"


@pytest.mark.asyncio
async def test_create_top_up_transitions_to_failed_when_charge_rejected(db_session):
    wallet = Wallet(id=uuid.uuid4(), user_id=uuid.uuid4(), balance_minor=0, currency="SAR")
    db_session.add(wallet)
    await db_session.flush()

    pg = AsyncMock()
    pg.create_charge.return_value = {"charge_id": str(uuid.uuid4()), "status": "REJECTED", "provider_payment_id": None}
    svc = TopUpService(session=db_session, payment_gateway=pg)
    resp = await svc.create(
        CreateTopUpRequest(wallet_id=wallet.id, amount_minor=1000, currency="SAR"),
        idempotency_key="k2",
    )
    assert resp.status == "FAILED"
```

- [ ] **Step 4: Implement service**

`resources/top_ups/top_up_service.py`:

```python
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from infra import idempotency
from infra.state_machine import guarded_transition
from resources.top_ups import top_up_dal
from resources.top_ups.top_up_model import TopUp
from resources.top_ups.top_up_schema import CreateTopUpRequest, TopUpResponse


@dataclass
class TopUpService:
    session: AsyncSession
    payment_gateway: object  # has async create_charge(...)

    async def create(self, req: CreateTopUpRequest, idempotency_key: str) -> TopUpResponse:
        idem = await idempotency.start(self.session, idempotency_key, req.model_dump(mode="json"))
        if not idem.new and idem.cached_body is not None:
            return TopUpResponse(**idem.cached_body)

        top_up = await top_up_dal.insert_pending(
            self.session, wallet_id=req.wallet_id, amount_minor=req.amount_minor, currency=req.currency
        )
        charge = await self.payment_gateway.create_charge(
            amount_minor=req.amount_minor,
            currency=req.currency,
            metadata={"top_up_id": str(top_up.id)},
            idempotency_key=f"topup-{top_up.id}",
        )
        await top_up_dal.set_charge_id(self.session, top_up.id, uuid.UUID(charge["charge_id"]))
        if charge["status"] == "ACCEPTED":
            await guarded_transition(self.session, TopUp, top_up.id, expected="PENDING", new="PROCESSING")
            response = TopUpResponse(top_up_id=top_up.id, status="PROCESSING")
        else:
            await top_up_dal.set_failed(self.session, top_up.id, reason="provider_rejected")
            response = TopUpResponse(top_up_id=top_up.id, status="FAILED")

        await idempotency.complete(
            self.session, idempotency_key, status=200, body=response.model_dump(mode="json"), resource_id=top_up.id
        )
        return response
```

- [ ] **Step 5: Run tests, expect pass**

```bash
poetry run pytest tests/test_top_up_service.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add repos/investment-wallet
git commit -m "feat(wallet): TopUpService.create — idempotent, state-machine-driven, calls payment gateway"
```

### Task 4.5: `/top-ups` controller

**Files:**
- Create: `repos/investment-wallet/api/controllers/top_up_controller.py`
- Modify: `repos/investment-wallet/api/routes.py`
- Create: `repos/investment-wallet/tests/test_top_up_controller.py`

- [ ] **Step 1: Controller**

```python
# api/controllers/top_up_controller.py
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import session_dependency
from infra.idempotency import IdempotencyConflict, IdempotencyInProgress
from infra.http_client import PaymentGatewayClient
from resources.top_ups.top_up_schema import CreateTopUpRequest, TopUpResponse
from resources.top_ups.top_up_service import TopUpService

router = APIRouter()

_pg_client = PaymentGatewayClient()


async def _session():
    async for s in session_dependency("investment_wallet"):
        yield s


@router.post("", response_model=TopUpResponse)
async def create_top_up(
    req: CreateTopUpRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(_session),
):
    svc = TopUpService(session=session, payment_gateway=_pg_client)
    try:
        return await svc.create(req, idempotency_key=idempotency_key)
    except IdempotencyConflict:
        raise HTTPException(422, "Idempotency-Key reused with different body")
    except IdempotencyInProgress:
        raise HTTPException(409, "Request with this Idempotency-Key is in progress")
```

- [ ] **Step 2: Wire route**

```python
# api/routes.py
from api.controllers.top_up_controller import router as TopUpRouter
from api.controllers.test_controller import router as TestRouter


def init_routes(app):
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])
    app.include_router(TopUpRouter, prefix="/top-ups", tags=["TopUps"])
    return app
```

- [ ] **Step 3: Smoke test — app loads, route is registered**

`tests/test_top_up_controller.py`:

```python
from fastapi.testclient import TestClient
from api.main import app


def test_route_registered():
    client = TestClient(app)
    # validation error (missing Idempotency-Key header) — proves the route exists and is wired.
    r = client.post("/top-ups", json={})
    assert r.status_code in (400, 422)
```

*Note:* the controller-level integration test for the happy path is intentionally skipped. FastAPI's `Depends(session_dependency)` creates a session against the real `investment_wallet` DB, not the test DB — overriding that cleanly requires `app.dependency_overrides`, which adds ceremony without adding evidence. The service test in Task 4.4 already covers the business logic; an E2E smoke script in Task 6.1 proves the controller wires correctly at runtime.

- [ ] **Step 4: Commit**

```bash
git add repos/investment-wallet
git commit -m "feat(wallet): POST /top-ups controller + smoke test"
```

### Task 4.6: Settlement consumer

**Files:**
- Create: `repos/investment-wallet/api/consumers/__init__.py`
- Create: `repos/investment-wallet/api/consumers/settlement_consumer.py`
- Create: `repos/investment-wallet/tests/test_settlement_consumer.py`

- [ ] **Step 1: Consumer**

```python
# api/consumers/settlement_consumer.py
import json
import uuid

import aio_pika
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from infra import outbox
from infra.state_machine import guarded_transition, IllegalStateTransition
from resources.top_ups.top_up_model import TopUp
from resources.wallets.wallet_model import Wallet
from resources.fund_transfers.fund_transfer_model import FundTransfer
from resources.processed_events.model import ProcessedEvent


async def handle_settlement(sm: async_sessionmaker, envelope: dict) -> None:
    event_id = uuid.UUID(envelope["id"])
    payload = envelope["payload"]

    async with sm() as session:
        dedup = (
            insert(ProcessedEvent)
            .values(event_id=event_id, event_type=envelope["type"])
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        result = await session.execute(dedup)
        if result.rowcount == 0:
            await session.commit()
            return

        if payload["kind"] == "top_up":
            correlation = uuid.UUID(payload["correlation_id"])
            top_up = await session.scalar(select(TopUp).where(TopUp.id == correlation))
            if top_up is None:
                # orphan — rollback dedup so DLQ sees it, raise
                await session.rollback()
                raise RuntimeError(f"unknown top_up {correlation}")
            await guarded_transition(session, TopUp, top_up.id, expected="PROCESSING", new="PAID")
            wallet = await session.scalar(select(Wallet).where(Wallet.id == top_up.wallet_id))
            assert wallet is not None
            wallet.balance_minor += payload["amount_minor"]
            await outbox.enqueue(
                session,
                aggregate_id=top_up.id,
                type_="top_up.paid",
                payload={"top_up_id": str(top_up.id), "wallet_id": str(wallet.id), "amount_minor": payload["amount_minor"]},
            )
        elif payload["kind"] == "fund_transfer":
            wallet_id = uuid.UUID(payload["wallet_id"])
            wallet = await session.scalar(select(Wallet).where(Wallet.id == wallet_id))
            if wallet is None:
                await session.rollback()
                raise RuntimeError(f"unknown wallet {wallet_id}")
            ft = FundTransfer(
                id=uuid.uuid4(), wallet_id=wallet.id, amount_minor=payload["amount_minor"],
                currency=payload["currency"], bank_reference=payload.get("virtual_iban", ""), statement_id=uuid.UUID(payload["statement_id"]),
            )
            session.add(ft)
            wallet.balance_minor += payload["amount_minor"]
            await outbox.enqueue(
                session,
                aggregate_id=ft.id,
                type_="fund_transfer.paid",
                payload={"fund_transfer_id": str(ft.id), "wallet_id": str(wallet.id), "amount_minor": payload["amount_minor"]},
            )
        else:
            await session.rollback()
            raise RuntimeError(f"unknown kind {payload['kind']}")
        await session.commit()


async def run_consumer(sm: async_sessionmaker, connection_url: str, queue_name: str, binding: str, exchange_name: str, dlq_name: str) -> None:
    conn = await aio_pika.connect_robust(connection_url)
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=10)
    dlq = await channel.declare_queue(dlq_name, durable=True)
    queue = await channel.declare_queue(
        queue_name, durable=True,
        arguments={"x-dead-letter-exchange": "", "x-dead-letter-routing-key": dlq.name, "x-delivery-limit": 5},
    )
    exchange = await channel.declare_exchange(exchange_name, type=aio_pika.ExchangeType.TOPIC, durable=True)
    await queue.bind(exchange, routing_key=binding)

    async with queue.iterator() as it:
        async for message in it:
            async with message.process(requeue=True, reject_on_redelivered=False):
                envelope = json.loads(message.body)
                try:
                    await handle_settlement(sm, envelope)
                except IllegalStateTransition:
                    # State mismatch — nack with requeue to retry later
                    raise
                except RuntimeError:
                    # Unknown correlation — reject, let DLQ capture it
                    await message.reject(requeue=False)
                    return
```

- [ ] **Step 2: Unit test (handler only — feeds stub envelope)**

`tests/test_settlement_consumer.py`:

```python
import uuid
import pytest
from sqlalchemy import select

from api.consumers.settlement_consumer import handle_settlement
from resources.wallets.wallet_model import Wallet
from resources.top_ups.top_up_model import TopUp


@pytest.mark.asyncio
async def test_handle_settlement_credits_wallet_and_marks_paid(db_session_factory):
    wallet_id = uuid.uuid4()
    top_up_id = uuid.uuid4()
    async with db_session_factory() as s:
        s.add(Wallet(id=wallet_id, user_id=uuid.uuid4(), balance_minor=0, currency="SAR"))
        s.add(TopUp(id=top_up_id, wallet_id=wallet_id, amount_minor=1000, currency="SAR", status="PROCESSING"))
        await s.commit()

    envelope = {
        "id": str(uuid.uuid4()),
        "type": "settlement.completed",
        "payload": {"kind": "top_up", "correlation_id": str(top_up_id), "amount_minor": 1000, "statement_id": str(uuid.uuid4()), "currency": "SAR"},
    }
    await handle_settlement(db_session_factory, envelope)

    async with db_session_factory() as s:
        refreshed = await s.scalar(select(TopUp).where(TopUp.id == top_up_id))
        assert refreshed.status == "PAID"
        w = await s.scalar(select(Wallet).where(Wallet.id == wallet_id))
        assert w.balance_minor == 1000


@pytest.mark.asyncio
async def test_handle_settlement_is_idempotent(db_session_factory):
    wallet_id = uuid.uuid4()
    top_up_id = uuid.uuid4()
    async with db_session_factory() as s:
        s.add(Wallet(id=wallet_id, user_id=uuid.uuid4(), balance_minor=0, currency="SAR"))
        s.add(TopUp(id=top_up_id, wallet_id=wallet_id, amount_minor=500, currency="SAR", status="PROCESSING"))
        await s.commit()

    envelope = {
        "id": str(uuid.uuid4()),
        "type": "settlement.completed",
        "payload": {"kind": "top_up", "correlation_id": str(top_up_id), "amount_minor": 500, "statement_id": str(uuid.uuid4()), "currency": "SAR"},
    }
    await handle_settlement(db_session_factory, envelope)
    await handle_settlement(db_session_factory, envelope)  # replay

    async with db_session_factory() as s:
        w = await s.scalar(select(Wallet).where(Wallet.id == wallet_id))
        assert w.balance_minor == 500  # credited exactly once
```

Add `db_session_factory` fixture to conftest.py:

```python
@pytest_asyncio.fixture
async def db_session_factory():
    # like db_session but returns the sessionmaker itself
    import os
    url = os.getenv("TEST_DATABASE_URL", "cockroachdb+asyncpg://root@localhost:26257/investment_wallet_test?sslmode=disable")
    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
```

- [ ] **Step 3: Run, expect pass**

```bash
poetry run pytest tests/test_settlement_consumer.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add repos/investment-wallet
git commit -m "feat(wallet): settlement consumer — state guard, wallet credit, outbox, idempotent replay"
```

### Task 4.7: Wire broker + outbox drain + consumer on startup

**Files:**
- Modify: `repos/investment-wallet/api/main.py`

- [ ] **Step 1: Lifespan**

```python
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
from infra.events import CONSUMER_QUEUE, CONSUMER_BINDING, EXCHANGE, DLQ_NAME, RK_TOP_UP_PAID, RK_FUND_TRANSFER_PAID
from infra.outbox import run_drain_loop

_broker = Broker()
_tasks: list[asyncio.Task] = []


def _rk(type_: str) -> str:
    return {"top_up.paid": RK_TOP_UP_PAID, "fund_transfer.paid": RK_FUND_TRANSFER_PAID}.get(type_, f"wallet.{type_}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _broker.start(EXCHANGE)
    sm = get_sessionmaker("investment_wallet")
    _tasks.append(asyncio.create_task(run_drain_loop(sm, _broker, _rk)))
    _tasks.append(asyncio.create_task(run_consumer(sm, RABBITMQ_URL, CONSUMER_QUEUE, CONSUMER_BINDING, EXCHANGE, DLQ_NAME)))
    yield
    for t in _tasks:
        t.cancel()
    await _broker.stop()


app: FastAPI = init_routes(FastAPI(title="IronWallet Investment-Wallet", lifespan=lifespan))

if __name__ == "__main__":
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    run("api.main:app", host="0.0.0.0", port=8083, reload=False)
```

- [ ] **Step 2: Commit**

```bash
git add repos/investment-wallet/api/main.py
git commit -m "feat(wallet): start broker, outbox drain, settlement consumer on lifespan"
```

---

## Phase 5 — Gateway

### Task 5.1: Gateway forwarding

**Files:**
- Create: `repos/gateway/infra/http_client.py`
- Create: `repos/gateway/api/controllers/top_up_controller.py`
- Create: `repos/gateway/api/controllers/fund_transfer_controller.py`
- Modify: `repos/gateway/api/routes.py`

- [ ] **Step 1: Http client helpers**

```python
# infra/http_client.py
import os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

WALLET_URL = os.getenv("WALLET_URL", "http://localhost:8083")
OMNIBUS_URL = os.getenv("OMNIBUS_URL", "http://localhost:8082")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4))
async def forward(method: str, url: str, json: dict | None = None, headers: dict | None = None) -> httpx.Response:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.request(method, url, json=json, headers=headers)
        r.raise_for_status()
        return r
```

- [ ] **Step 2: Top-up controller (forward)**

```python
# api/controllers/top_up_controller.py
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from infra.http_client import forward, WALLET_URL

router = APIRouter()


@router.post("")
async def forward_top_up(request: Request, idempotency_key: str = Header(alias="Idempotency-Key")):
    body = await request.json()
    resp = await forward("POST", f"{WALLET_URL}/top-ups", json=body, headers={"Idempotency-Key": idempotency_key})
    return JSONResponse(status_code=resp.status_code, content=resp.json())
```

- [ ] **Step 3: Fund-transfer controller (admin stand-in)**

```python
# api/controllers/fund_transfer_controller.py
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from infra.http_client import forward, OMNIBUS_URL

router = APIRouter()


@router.post("")
async def forward_bank_transfer(request: Request):
    body = await request.json()
    resp = await forward("POST", f"{OMNIBUS_URL}/bank-transfers", json=body)
    return JSONResponse(status_code=resp.status_code, content=resp.json())
```

- [ ] **Step 4: Wire routes**

```python
# api/routes.py
from api.controllers.top_up_controller import router as TopUpRouter
from api.controllers.fund_transfer_controller import router as FundTransferRouter
from api.controllers.test_controller import router as TestRouter


def init_routes(app):
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])
    app.include_router(TopUpRouter, prefix="/top-ups", tags=["TopUps"])
    app.include_router(FundTransferRouter, prefix="/bank-transfers", tags=["BankTransfers"])
    return app
```

- [ ] **Step 5: Commit**

```bash
git add repos/gateway
git commit -m "feat(gateway): forward /top-ups and /bank-transfers with retry"
```

---

## Phase 6 — End-to-end smoke + docs

### Task 6.1: End-to-end happy-path smoke

**Files:**
- Create: `examples/top-up.sh`
- Create: `examples/fund-transfer.sh`

- [ ] **Step 1: Top-up script**

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1) create a wallet by inserting directly (no wallet controller in POC)
WALLET_ID=$(docker exec database /cockroach/cockroach sql --insecure -d investment_wallet -e "
  INSERT INTO wallets (id, user_id, balance_minor, currency) VALUES (gen_random_uuid(), gen_random_uuid(), 0, 'SAR')
  RETURNING id;
" --format csv | tail -n 1)

# 2) POST via gateway
IDEM=$(uuidgen)
curl -s -X POST http://localhost:8084/top-ups \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $IDEM" \
  -d "{\"wallet_id\":\"$WALLET_ID\",\"amount_minor\":10000,\"currency\":\"SAR\"}" | jq
sleep 3
# 3) Check balance after settlement
docker exec database /cockroach/cockroach sql --insecure -d investment_wallet -e "SELECT balance_minor FROM wallets WHERE id='$WALLET_ID';"
```

- [ ] **Step 2: Fund-transfer script**

```bash
#!/usr/bin/env bash
set -euo pipefail
WALLET_ID=$(docker exec database /cockroach/cockroach sql --insecure -d investment_wallet -e "
  INSERT INTO wallets (id, user_id, balance_minor, currency) VALUES (gen_random_uuid(), gen_random_uuid(), 0, 'SAR')
  RETURNING id;
" --format csv | tail -n 1)
REF="bk-$(uuidgen)"
curl -s -X POST http://localhost:8084/bank-transfers \
  -H "Content-Type: application/json" \
  -d "{\"virtual_iban\":\"SA000000001\",\"amount_minor\":5000,\"currency\":\"SAR\",\"bank_reference\":\"$REF\",\"wallet_id\":\"$WALLET_ID\"}" | jq
sleep 2
docker exec database /cockroach/cockroach sql --insecure -d investment_wallet -e "SELECT balance_minor FROM wallets WHERE id='$WALLET_ID';"
```

- [ ] **Step 3: Run both scripts end-to-end**

Start all four services (each in a separate terminal), then:

```bash
chmod +x examples/*.sh
./examples/top-up.sh
./examples/fund-transfer.sh
```

Expected: both print a balance matching the top-up / transfer amount.

- [ ] **Step 4: Commit**

```bash
git add examples
git commit -m "docs: happy-path E2E smoke scripts for top-up and fund-transfer"
```

### Task 6.2: README + run instructions

**Files:**
- Modify: `readme.md`

- [ ] **Step 1: Append a "Running the POC" section with exact commands**

Append to `readme.md`:

```markdown
## Running the POC

### One-time setup

    make up
    make install
    docker exec database /cockroach/cockroach sql --insecure -e "CREATE DATABASE IF NOT EXISTS payment_gateway_test; CREATE DATABASE IF NOT EXISTS omnibus_test; CREATE DATABASE IF NOT EXISTS investment_wallet_test"

### Start services (one terminal each)

    cd repos/payment_gateway && poetry run poe api_service
    cd repos/omnibus         && poetry run poe api_service
    cd repos/investment-wallet && poetry run poe api_service
    cd repos/gateway         && poetry run poe api_service

### Smoke test

    ./examples/top-up.sh
    ./examples/fund-transfer.sh

### Tests

    for s in payment_gateway omnibus investment-wallet; do (cd repos/$s && poetry run pytest -v); done
```

- [ ] **Step 2: Commit**

```bash
git add readme.md
git commit -m "docs: running-the-POC instructions"
```

### Task 6.3: EDGE_CASES.md and FUTURE_WORK.md

**Files:**
- Create: `docs/EDGE_CASES.md`
- Create: `docs/FUTURE_WORK.md`

- [ ] **Step 1: EDGE_CASES.md — copy spec section 13, expand as useful**

Paste the list from spec Section 13 with light prose around each item (one paragraph each).

- [ ] **Step 2: FUTURE_WORK.md — copy spec section 17 with light prose**

Paste the list from spec Section 17 with a one-line rationale for each bullet.

- [ ] **Step 3: Commit**

```bash
git add docs
git commit -m "docs: EDGE_CASES and FUTURE_WORK writeups"
```

---

## Final verification

- [ ] `make up && make install` succeeds from a fresh clone.
- [ ] All 4 services start without error.
- [ ] `examples/top-up.sh` shows balance credited within 3s.
- [ ] `examples/fund-transfer.sh` shows balance credited within 2s.
- [ ] `pytest` passes in payment_gateway, omnibus, investment-wallet.
- [ ] Duplicate Idempotency-Key returns identical response at `/top-ups`.
- [ ] RabbitMQ management UI shows `iron_wallet` exchange + `wallet.settlements` queue bound.
- [ ] Design doc + edge cases + future work live under `docs/`.

---

## Self-review checklist (before execution)

- Spec §1–§4 services/flows → Tasks 2.x, 3.x, 4.x, 5.x.
- Spec §5 data model → Tasks 2.1, 3.2, 4.1 cover every table.
- Spec §6 state machine → Task 4.2 helper + Task 4.4 transitions.
- Spec §7 idempotency → Task 2.3 helper + every service uses it.
- Spec §8 outbox → Task 3.5 (omnibus) + Task 4.3 (wallet copy) + drains in 3.8, 4.7.
- Spec §9 RabbitMQ topology → events.py constants in omnibus + wallet, consumer declares queue+DLQ in Task 4.6.
- Spec §10 error handling → tenacity retries in 2.2 provider, 4.3 http client, 5.1 gateway; state-machine guard + processed_events handle partial-failure cases.
- Spec §11 webhook security → Task 3.6 HMAC verification tests.
- Spec §12 mocks → Task 2.2 MockMoyasar + Task 3.7 admin endpoint for bank.
- Spec §13 edge cases → Task 6.3 writeup + tests for dup webhook, dup idem key.
- Spec §14 testing → ~10 tests across 2.3, 2.4, 2.5, 3.6, 3.7, 4.2, 4.4, 4.5, 4.6.
- Spec §15 layout → file map at top of plan matches.
- Spec §16 deliverables → design doc ✓, plan ✓, examples ✓, README ✓, edge cases ✓, future work ✓. (Excalidraw is manual work for the candidate.)
- Spec §17 future work → Task 6.3 writeup.
