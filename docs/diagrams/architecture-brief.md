# Diagram Brief — System Architecture (at rest)

A standalone description of an at-rest architecture diagram. The agent receiving this should pick the diagram type, layout, and visual style it judges most effective.

---

## Audience and goal

A senior backend engineer skimming a fintech take-home will look at this for under 30 seconds. They should walk away knowing:

1. **Which services exist** in the system.
2. **What each service owns** — its tables and the endpoints it exposes.
3. **How services connect** — which edges are synchronous HTTP and which are asynchronous events.
4. **What's internal vs external.**

This is the "front cover" — the first diagram a reviewer should see. It does **not** trace any specific request; it shows the system at rest.

---

## The system

Four internal services plus a message broker, all backed by CockroachDB (postgres-compatible). Each service has its own database — no shared tables.

### Gateway
Edge router. No DB. Forwards external client HTTP into the right internal service. Exposes `POST /top-ups` and `POST /bank-transfers` to clients.

### Investment-Wallet
The orchestrator and user-facing brain.
- Tables: `wallets`, `top_ups`, `fund_transfers`, `idempotency_keys`, `processed_events`, `outbox_events`.
- Internal endpoint: `POST /top-ups`.
- Consumes: `settlement.completed` from RabbitMQ.
- Publishes: `top_up.paid`, `fund_transfer.paid` (via outbox).

### Payment-Gateway (one of our services, not a database)
Wraps the external payment provider (Moyasar). Records every charge attempt.
- Tables: `charges`, `idempotency_keys`.
- Internal endpoint: `POST /charges`.
- Calls: external provider over HTTPS.

### Omnibus
The bank-side ledger. Receives notifications when money actually lands in the IronWallet bank account — both card-payment webhooks (from the provider) and bank-transfer notifications (from the user's bank).
- Tables: `statements` (★ source of truth for money), `processed_webhooks`, `outbox_events`, `idempotency_keys`.
- Endpoints: `POST /webhooks/moyasar`, `POST /bank-transfers`.
- Publishes: `settlement.completed` (via outbox).

### RabbitMQ
Topic exchange `iron_wallet`. Carries state-change events between services. Has a queue `wallet.settlements` (consumed by Wallet) and a DLQ for poison messages.

### External
- **Client** (mobile / web app) — calls in via Gateway.
- **Provider (Moyasar)** — external payment processor; mocked in this POC. Receives charge requests from Payment-Gateway, fires signed webhooks back to Omnibus.
- **User's bank** — external; mocked in this POC. Sends bank-transfer notifications to Omnibus.

---

## How they connect

- **Synchronous HTTP edges:**
  - Client → Gateway (any client request)
  - Gateway → Investment-Wallet (top-ups)
  - Gateway → Omnibus (admin bank-transfer)
  - Investment-Wallet → Payment-Gateway (charges)
  - Payment-Gateway → Provider (creating payments)
  - Provider → Omnibus (HMAC-signed webhooks)
  - Bank → Omnibus (notifications)

- **Asynchronous event edges (RabbitMQ):**
  - Omnibus → RabbitMQ → Investment-Wallet (settlement.completed)
  - Investment-Wallet → RabbitMQ (top_up.paid, fund_transfer.paid — no consumers in the POC, but the bus is wired so future services can subscribe)

---

## Concepts to make obvious

- **Each service owns its own database** — no shared schema, no cross-service queries.
- **Two communication modes coexist** — sync HTTP for commands, async events for state reconciliation. They should be visually distinct.
- **Internal vs external boundaries** — clear separation between IronWallet's services and external systems (Provider, Bank, Client).
- **Source of truth is `statements` in Omnibus** — every other money-related table is a derived view downstream of it.

---

## What this diagram is not

- Not a sequence diagram tracing a single request — that's the job of the flow diagrams.
- Not a deployment diagram — it's not about where things run, just what they are and how they connect.
- Not a class or ER diagram.

---

## Aesthetic preference

Warm cream background, Anthropic-blog feel. Calm, professional. Soft service-card fills only where they help separate boundaries; muted dark strokes; system-ui font.

---

## Reference

`docs/diagrams/top-up-architecture-brief.md` describes a different diagram (architecture + top-up flow) in the same series. It establishes the visual language; this diagram should feel like a sibling.
