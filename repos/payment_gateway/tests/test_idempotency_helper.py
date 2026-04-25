import hashlib
import json
import pytest
from datetime import datetime, timezone, timedelta

from infra.idempotency import hash_body, IdempotencyConflict, IdempotencyInProgress


def test_hash_body_stable_for_equal_dicts():
    a = hash_body({"amount": 100, "currency": "SAR"})
    b = hash_body({"currency": "SAR", "amount": 100})
    assert a == b


def test_hash_body_differs_for_different_bodies():
    assert hash_body({"x": 1}) != hash_body({"x": 2})


# The DB-backed flow is exercised by integration tests in test_charge_service.
