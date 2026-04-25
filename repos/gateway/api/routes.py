from api.controllers.test_controller import router as TestRouter
from api.controllers.top_up_controller import router as TopUpRouter
from api.controllers.fund_transfer_controller import router as FundTransferRouter


def init_routes(app):
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])
    app.include_router(TopUpRouter, prefix="/top-ups", tags=["Top-Ups"])
    app.include_router(FundTransferRouter, prefix="/bank-transfers", tags=["Fund Transfers"])

    return app
