from fastapi.testclient import TestClient
from api.main import app


def test_route_registered():
    client = TestClient(app)
    # Validation error (missing Idempotency-Key header / empty body) — proves
    # the route exists and is wired correctly.
    r = client.post("/top-ups", json={})
    assert r.status_code in (400, 422)
