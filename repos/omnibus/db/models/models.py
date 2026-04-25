""" Model base """
# Register All models inside the resources folder
# pylint: disable=unused-import

from resources.statements.statement_model import Statement
from resources.processed_webhooks.model import ProcessedWebhook
from resources.outbox.model import OutboxEvent
from resources.idempotency_keys.model import IdempotencyKey
