import hmac
import hashlib
import json
import uuid
from fastapi.testclient import TestClient

from api.main import app


SECRET = "dev-secret"


def _sign(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_rejects_bad_signature(db_session):
    client = TestClient(app)
    body = b'{"event_id":"evt1"}'
    r = client.post("/webhooks/moyasar", content=body, headers={"X-Signature": "wrong"})
    assert r.status_code == 401


def test_webhook_records_and_dedupes(db_session):
    client = TestClient(app)
    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "payment.paid",
        "payment_id": "pay_x",
        "amount_minor": 5000,
        "currency": "SAR",
        "metadata": {"top_up_id": str(uuid.uuid4())},
    }
    body = json.dumps(payload).encode()
    r1 = client.post("/webhooks/moyasar", content=body, headers={"X-Signature": _sign(body), "Content-Type": "application/json"})
    r2 = client.post("/webhooks/moyasar", content=body, headers={"X-Signature": _sign(body), "Content-Type": "application/json"})

    assert r1.status_code == 200
    assert r1.json() == {"status": "recorded"}
    assert r2.json() == {"status": "duplicate"}
