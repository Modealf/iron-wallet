""" Model base """

# Register All models inside the resources folder
# pylint: disable=unused-import


from resources.wallets.wallet_model import Wallet
from resources.top_ups.top_up_model import TopUp
from resources.fund_transfers.fund_transfer_model import FundTransfer
from resources.processed_events.model import ProcessedEvent
from resources.outbox.model import OutboxEvent
from resources.idempotency_keys.model import IdempotencyKey
