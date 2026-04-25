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
