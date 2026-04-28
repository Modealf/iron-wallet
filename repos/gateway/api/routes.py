from fastapi.middleware.cors import CORSMiddleware

from api.controllers.test_controller import router as TestRouter
from api.controllers.top_up_controller import router as TopUpRouter
from api.controllers.fund_transfer_controller import router as FundTransferRouter
from api.controllers.wallet_controller import router as WalletRouter


def init_routes(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])
    app.include_router(TopUpRouter, prefix="/top-ups", tags=["Top-Ups"])
    app.include_router(FundTransferRouter, prefix="/bank-transfers", tags=["Fund Transfers"])
    app.include_router(WalletRouter, prefix="/wallets", tags=["Wallets"])

    return app
