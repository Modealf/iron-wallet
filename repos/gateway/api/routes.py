from api.controllers.test_controller import router as TestRouter


def init_routes(app):
    app.include_router(TestRouter, prefix="/tests", tags=["Test"])

    return app
