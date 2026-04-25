import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from resources.statements.statement_model import Statement
from resources.processed_webhooks.model import ProcessedWebhook
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
