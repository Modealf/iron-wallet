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
                # Orphan — rollback dedup so DLQ sees it, raise.
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
                payload={
                    "top_up_id": str(top_up.id),
                    "wallet_id": str(wallet.id),
                    "amount_minor": payload["amount_minor"],
                },
            )
        elif payload["kind"] == "fund_transfer":
            wallet_id = uuid.UUID(payload["wallet_id"])
            wallet = await session.scalar(select(Wallet).where(Wallet.id == wallet_id))
            if wallet is None:
                await session.rollback()
                raise RuntimeError(f"unknown wallet {wallet_id}")
            ft = FundTransfer(
                id=uuid.uuid4(),
                wallet_id=wallet.id,
                amount_minor=payload["amount_minor"],
                currency=payload["currency"],
                bank_reference=payload.get("virtual_iban", ""),
                statement_id=uuid.UUID(payload["statement_id"]),
            )
            session.add(ft)
            wallet.balance_minor += payload["amount_minor"]
            await outbox.enqueue(
                session,
                aggregate_id=ft.id,
                type_="fund_transfer.paid",
                payload={
                    "fund_transfer_id": str(ft.id),
                    "wallet_id": str(wallet.id),
                    "amount_minor": payload["amount_minor"],
                },
            )
        else:
            await session.rollback()
            raise RuntimeError(f"unknown kind {payload['kind']}")
        await session.commit()


async def run_consumer(
    sm: async_sessionmaker,
    connection_url: str,
    queue_name: str,
    binding: str,
    exchange_name: str,
    dlq_name: str,
) -> None:
    conn = await aio_pika.connect_robust(connection_url)
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=10)
    dlq = await channel.declare_queue(dlq_name, durable=True)
    queue = await channel.declare_queue(
        queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": dlq.name,
            "x-delivery-limit": 5,
        },
    )
    exchange = await channel.declare_exchange(
        exchange_name, type=aio_pika.ExchangeType.TOPIC, durable=True
    )
    await queue.bind(exchange, routing_key=binding)

    async with queue.iterator() as it:
        async for message in it:
            async with message.process(requeue=True, reject_on_redelivered=False):
                envelope = json.loads(message.body)
                try:
                    await handle_settlement(sm, envelope)
                except IllegalStateTransition:
                    # State mismatch — nack with requeue to retry later.
                    raise
                except RuntimeError:
                    # Unknown correlation — reject, let DLQ capture it.
                    await message.reject(requeue=False)
                    return
