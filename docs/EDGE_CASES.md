# Edge cases

This document expands the edge-case bullets from the design doc (§13) into how the IronWallet POC actually handles each scenario at runtime. The list is non-exhaustive; the focus is on cases that distributed flows tend to hit in practice — duplicate requests, out-of-order events, partial failures, and orphan messages.

## Duplicate client request

A client retrying after a flaky network or a double tap on a mobile button will resend the same `POST /top-ups` body, possibly with the same `Idempotency-Key` header. The wallet service writes to its `idempotency_keys` table inside the same transaction as the `top_up` insert, so the second call short-circuits: a matching key + matching request hash with a `completed` row replays the stored response, a different body returns 422 (client bug), and an in-progress entry returns 409. No duplicate top-up row is ever created, no second charge ever lands at the payment gateway.

## Webhook arrives before wallet finished PROCESSING

With a fast mock provider it is possible for `settlement.completed` to be emitted by Omnibus and reach the wallet consumer before the wallet's own `POST /charges` round trip has returned and flipped the `top_up` from `PENDING` to `PROCESSING`. The state machine guard (`UPDATE ... WHERE status = 'PROCESSING' RETURNING id`) returns zero rows, the consumer raises `IllegalStateTransition`, and the message is nacked with requeue. RabbitMQ redelivers up to five times — by then the wallet has caught up, the transition succeeds, and the wallet is credited. After five failed redeliveries the message lands in the DLQ for manual reconcile.

## Webhook delivered twice

Real payment providers retry webhooks on any non-2xx, and Omnibus is the receiver. The first delivery inserts a row into `processed_webhooks` keyed by `(provider, event_id)` inside the same transaction as the statement insert and the outbox event. A second delivery hits the unique constraint, the transaction rolls back, Omnibus returns 200, and no duplicate settlement event is published. The `statements` unique index on `(kind, source_ref)` is a second line of defence at the table level.

## Provider confirms but event publish fails

The outbox pattern decouples the business write from the broker hop: Omnibus commits the statement and an `outbox_events` row in one transaction, then a background drain task polls unpublished rows and publishes them to RabbitMQ with `FOR UPDATE SKIP LOCKED`. If the broker is down or the publish fails, `published_at` stays null and the row is retried on the next 500 ms tick. The wallet credit is never lost — at most it is delayed until the broker recovers.

## Conflicting top-up requests for the same wallet

Two requests landing on the same wallet at the same time both attempt to credit `balance_minor`. CockroachDB's default `SERIALIZABLE` isolation, combined with row-level updates inside the wallet's settlement consumer, prevents lost updates: one transaction wins, the other gets a retryable serialization error and the consumer requeues the message. Both top-ups eventually reflect in the balance, and neither overwrites the other's increment.

## Delayed bank transfer

A user can initiate a bank transfer to their virtual IBAN at any moment, with no prior coordination with the wallet. The fund-transfer flow is fully event-driven from the Omnibus side — when the bank notifies Omnibus (mocked via `POST /bank-transfers`), Omnibus inserts a statement keyed by `bank_reference` and publishes a `settlement.completed` event with `kind=fund_transfer`. The wallet consumer creates a fresh `fund_transfers` row keyed by `statement_id` and credits the balance. There is no pre-state to invalidate, so arbitrary delays are tolerated.

## Settlement event with unknown correlation_id

If a top-up settlement arrives with a `correlation_id` that does not match any `top_up` row in the wallet DB (data corruption, a bug in metadata propagation, or a settlement for a deleted aggregate), the consumer logs a warning and nacks **without** requeue so the message goes straight to the DLQ for manual reconcile. This is deliberately distinct from the "right top_up, wrong state" case, which nacks **with** requeue because a retry might succeed once the wallet catches up. Mixing the two would either spam the DLQ with transient state-machine failures or hide genuine data drift.
