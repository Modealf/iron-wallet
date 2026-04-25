from fastapi.testclient import TestClient

from api.main import app


def test_charges_route_is_mounted_and_validates_body():
    """
    Smoke-test that POST /charges is wired up. With no body, FastAPI returns 422
    from request validation before any DB work happens — proves routing without
    needing the test DB. Behavior is covered by tests/test_charge_service.py.
    """
    client = TestClient(app)
    r = client.post("/charges", headers={"Idempotency-Key": "k"})
    assert r.status_code == 422
