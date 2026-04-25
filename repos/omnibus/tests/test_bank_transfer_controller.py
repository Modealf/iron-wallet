import uuid
from fastapi.testclient import TestClient
from api.main import app


def test_bank_transfer_creates_statement_and_dedupes(db_session):
    client = TestClient(app)
    body = {
        "virtual_iban": "SA00",
        "amount_minor": 10000,
        "currency": "SAR",
        "bank_reference": "ref-" + uuid.uuid4().hex,
        "wallet_id": str(uuid.uuid4()),
    }
    r1 = client.post("/bank-transfers", json=body)
    r2 = client.post("/bank-transfers", json=body)
    assert r1.status_code == 200
    assert "statement_id" in r1.json()
    assert r2.status_code == 409
