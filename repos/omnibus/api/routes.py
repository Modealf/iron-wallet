from api.controllers.test_controller import router as TestRouter
from api.controllers.webhook_controller import router as WebhookRouter
from api.controllers.bank_transfer_controller import router as BankTransferRouter


def init_routes(app):
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])
    app.include_router(WebhookRouter, prefix="/webhooks", tags=["Webhooks"])
    app.include_router(BankTransferRouter, prefix="/bank-transfers", tags=["BankTransfers"])
    return app
