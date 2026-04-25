# Diagram Brief — Top-Up Flow

A standalone description of what a diagram of the top-up flow should communicate. The agent receiving this should pick the diagram type, layout, and visual style it judges most effective.

---

## Audience and goal

A senior backend engineer reviewing a fintech take-home will look at this diagram for under a minute. From it they should walk away with:

1. **What each of our services is** and what it owns.
2. **How a single top-up request flows** through them, end to end.
3. **The split between synchronous response and asynchronous settlement** — and why both exist.
4. **Where the "source of truth" for actual money lives.**

If the diagram answers those four things clearly, it succeeds.

---

## The system

Four internal services plus a message broker. Each service has its own database (CockroachDB, postgres-compatible). The diagram should make all of this visible at a glance.

### Gateway
- Edge layer. No DB. Forwards client HTTP to the right internal service. Exposes `POST /top-ups` and `POST /bank-transfers` to clients.

### Investment-Wallet
- The orchestrator and user-facing brain.
- Tables it owns: `wallets`, `top_ups`, `fund_transfers`, `idempotency_keys`, `processed_events`, `outbox_events`.
- Endpoint exposed internally: `POST /top-ups`.
- Consumes the event `settlement.completed` from RabbitMQ.
- Publishes `top_up.paid` and `fund_transfer.paid` to RabbitMQ via its outbox.

### Payment-Gateway (one of our services, *not* a database)
- Wraps the external payment provider (Moyasar). Records every charge attempt.
- Tables: `charges`, `idempotency_keys`.
- Endpoint exposed internally: `POST /charges`.
- Calls the external provider over HTTPS.

### Provider (mocked Moyasar)
- External in real life, mocked in this POC. Returns a `payment_id` immediately, then fires a HMAC-signed webhook to Omnibus a moment later.

### Omnibus
- The bank-side ledger. Knows when money has actually landed in IronWallet's bank account. **`statements` is the source of truth for "did money actually arrive?"** — every other table downstream of it is a derived view.
- Tables: `statements`, `processed_webhooks`, `outbox_events`, `idempotency_keys`.
- Endpoints: `POST /webhooks/moyasar` (receives provider webhooks) and `POST /bank-transfers` (admin entry, mocked).
- Publishes `settlement.completed` to RabbitMQ via its outbox.

### RabbitMQ
- Topic exchange `iron_wallet`. Carries `settlement.completed` from Omnibus to the Wallet consumer, plus a DLQ (`wallet.settlements.dlq`) for failures.

---

## The flow (one top-up request, start to finish)

The diagram should walk this path in some readable order. The reader should be able to trace it from step 1 to the end.

1. **Client → Gateway.** `POST /top-ups` with an `Idempotency-Key` header.
2. **Gateway → Investment-Wallet.** Forwards as-is.
3. **Investment-Wallet, in one DB transaction:** claims the idempotency key and inserts a `top_up` row with status `PENDING`. Then synchronously calls Payment-Gateway.
4. **Payment-Gateway, in one DB transaction:** claims its own idempotency key (derived from the `top_up_id`), inserts a `charge` row with status `CREATED`. Calls the external provider.
5. **Provider returns `payment_id` immediately** and schedules a signed webhook to fire later (≈1 second). Payment-Gateway marks `charge` `ACCEPTED` and returns. Investment-Wallet transitions `top_up` `PENDING → PROCESSING` (state-machine guarded) and **returns `200 PROCESSING` to the client.** This is the end of the synchronous path.
6. **Async, ~1 second later:** the provider's signed webhook lands at Omnibus. Omnibus verifies the HMAC, dedups by `event_id`, and in one DB transaction inserts a `statement` plus an `outbox_event`.
7. **Omnibus's outbox publisher** drains the new row and publishes `settlement.completed` to RabbitMQ.
8. **The Wallet consumer** reads the event, dedups by `event_id`, transitions `top_up` `PROCESSING → PAID` (state-machine guarded), credits the wallet's `balance_minor`, and writes its own outbox event `top_up.paid`. **This is the end of the asynchronous settlement path** — the user's wallet now reflects the money.

---

## Concepts the diagram should make obvious

These are the insights a reader should take away. The diagram doesn't need to spell every one of these out, but the visual structure should support them:

- **Each service owns its own DB.** No shared tables. Cross-service data only travels via HTTP responses or RabbitMQ events.
- **Two communication modes coexist.** Synchronous HTTP for commands (the request chain Client → Gateway → Wallet → Payment-Gateway → Provider). Asynchronous events for state reconciliation (Provider → Omnibus → RabbitMQ → Wallet). They are visually distinct.
- **Two "endings" for one request.** The client gets a response (`200 PROCESSING`) before the money has actually settled. The wallet balance only updates later, when the async settlement event arrives. This gap is the eventual-consistency story the system is built around.
- **`statements` is the source of truth for money.** Wallet balances and `top_ups` rows are projections of statements. If they ever disagree, the bank-side ledger wins.
- **Idempotency lives at every external boundary** — client → wallet, wallet → payment-gateway, provider → omnibus webhook, omnibus → wallet event. Each hop has its own dedup key in its own DB.

---

## What this diagram is not

- Not a UML sequence diagram with lifelines. (That format obscures what each service *is*.)
- Not a pure flowchart. (That format obscures service boundaries.)
- Not just a static box-and-line architecture diagram. (That format obscures the flow.)

It is a hybrid: an architecture diagram with the request walked across it. The chooser may pick whatever shape best supports both views — boxes with sub-content, swimlanes with annotations, layered cards, numbered annotations, or anything that works.

---

## Aesthetic preference

Warm, professional, calm — Anthropic blog vibe. Cream-ish background, dark-gray strokes, soft pastel fills only where they help separate services. No neon, no harsh blacks, no clip art. Hand-drawn Excalidraw style is welcome but not required.

---

## Reference

A first attempt at this exists in the repo as `docs/diagrams/top-up-architecture.svg` and `docs/diagrams/top-up-flow.svg`. Look at them for context, but feel free to deviate — the goal is for *your* diagram to communicate the four insights above better than either.
