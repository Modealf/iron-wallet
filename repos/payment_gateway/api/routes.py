from api.controllers.charge_controller import router as ChargeRouter
from api.controllers.test_controller import router as TestRouter


def init_routes(app):
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])
    app.include_router(ChargeRouter, prefix="/charges", tags=["Charges"])
    return app
