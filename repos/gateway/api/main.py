from fastapi import FastAPI
from uvicorn import run
from api.routes import init_routes


app: FastAPI = init_routes(
    FastAPI(
        title="IronWallet Gateway Service",
        description="it is a service that abstract all `IronWallet` internal services and serve the clients ( Mobile app / Web app )",
    )
)


if __name__ == "__main__":

    run(
        "api.main:app",
        host="0.0.0.0",
        port=8081,
        reload=True,
    )
