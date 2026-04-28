from api.controllers.test_controller import router as TestRouter
from api.controllers.top_up_controller import router as TopUpRouter
from api.controllers.wallet_controller import router as WalletRouter


def init_routes(app):
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])
    app.include_router(TopUpRouter, prefix="/top-ups", tags=["TopUps"])
    app.include_router(WalletRouter, prefix="/wallets", tags=["Wallets"])

    return app
