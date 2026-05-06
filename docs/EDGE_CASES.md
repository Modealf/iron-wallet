# Edge cases

How the POC handles the failure modes distributed flows hit in practice.

## Duplicate client request

A retry or double-tap with the same `Idempotency-Key` short-circuits in the wallet's idempotency table: same hash + `completed` → replays stored response; different body → 422; `in_progress` → 409. No duplicate `top_up`, no second charge.

## Webhook arrives before wallet finished PROCESSING

With a fast mock provider, `settlement.completed` can reach the wallet consumer before its own `POST /charges` has returned. The state-machine guard rejects the early `PROCESSING → PAID` transition, the consumer nacks with requeue, and RabbitMQ redelivers up to 5 times via `x-delivery-limit`. By then the wallet has caught up and the transition succeeds.

## Webhook delivered twice

Real providers retry on any non-2xx. Omnibus dedups by `(provider, event_id)` in the same transaction as the statement insert, so a duplicate hits the unique constraint, rolls back, and returns 200 without republishing.

## Provider confirms but event publish fails

The outbox decouples the business write from the broker hop. If the broker is down, `published_at` stays null and the row is retried on the next 500 ms tick. The credit is delayed, never lost.

## Conflicting top-ups for the same wallet

Two settlements landing at the same instant both try to credit `balance_minor`. Cockroach `SERIALIZABLE` + row-level updates inside the consumer serialize them — one wins, the other gets a retryable serialization error and the consumer requeues. Both increments land. No lost update.

## Delayed bank transfer

The fund-transfer flow has no pre-state. Whenever the bank notifies omnibus, omnibus inserts a statement keyed by `bank_reference` and publishes; the wallet creates the `fund_transfer` keyed by `statement_id`. Arbitrary delays are tolerated.

## Settlement event with unknown correlation_id

If a settlement carries a `correlation_id` with no local `top_up` (data drift, deleted aggregate), the consumer logs and rejects **without** requeue — straight to the DLQ for manual reconcile. Distinct from "right top_up, wrong state" which nacks **with** requeue. Mixing them would either spam the DLQ with transient failures or hide genuine drift.

## Concurrent same-key requests on the idempotency claim

Two same-key requests at the same instant: Cockroach serializes the writes; one wins, the other gets a `40001` and surfaces as a 500 instead of the spec's 409. Data integrity is preserved (no duplicate `top_up`, no double charge); only the HTTP status of the loser is briefly wrong. Fix tracked in `FUTURE_WORK.md`.

## Partial failure after charge creation

If `POST /charges` returns ACCEPTED but the wallet's transaction fails before commit, the wallet rolls back its `top_up` while the charge already persists at the payment gateway. A client retry generates a fresh `top_up_id` and a second charge; the original webhook lands at omnibus with a `correlation_id` that no longer maps locally → DLQ. Manual reconcile. Fix tracked in `FUTURE_WORK.md` (register intended `top_up_id` upstream of the charge call).
