from api.controllers.test_controller import router as TestRouter
from api.controllers.top_up_controller import router as TopUpRouter


def init_routes(app):
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])
    app.include_router(TopUpRouter, prefix="/top-ups", tags=["TopUps"])

    return app
