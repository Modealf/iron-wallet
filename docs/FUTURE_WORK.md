# Future work

These items are deliberately out of scope for the POC (design doc §17). The POC's goal was to demonstrate the core flow, idempotency, and state management end-to-end across four services; everything below is a real follow-on but adds operational or implementation cost without changing the core architecture.

## Redis as a read-through cache in front of idempotency lookups

The `idempotency_keys` table is hit on every client-facing write. At low POC volumes a Postgres-compatible row read is fine, but at scale the same key gets queried repeatedly by retries within a few seconds of each other. A Redis read-through cache fronting the table — populated on write, invalidated on TTL — would absorb that retry storm and keep the database focused on durable writes. Skipped here because adding Redis to the dependency set, plus the cache-invalidation rules, was not load-bearing for the proof of concept.

## Dedicated outbox-publisher worker per service with leader election

The current outbox drain is an asyncio task running inside each API process. That is fine for a single-replica POC, but for HA deployment the publisher should be a separate process so API latency is decoupled from broker availability, and `FOR UPDATE SKIP LOCKED` should be combined with leader election (e.g. a Cockroach-backed lease) so that scaling the API tier horizontally does not multiply outbox traffic. This is mostly a packaging/ops change and was deferred to keep the run-locally story to "one process per service".

## Real Moyasar / ANB adapters behind the existing ports

The payment provider and bank are mocked behind `PaymentProviderPort` and `BankPort`. Swapping in real Moyasar (for charges) and real ANB statement ingestion (for fund transfers) is a matter of writing two adapter classes and wiring them up via configuration — no business logic changes. Skipped because real provider credentials, sandbox accounts, and webhook reachability from a local dev environment are out of scope for a take-home.

## AuthN/AuthZ (JWT, per-wallet ACLs)

The spec assumes users are already authenticated and authorized. The Gateway forwards the `Idempotency-Key` header but does no token verification, and the wallet service has no per-wallet ACL check. A production deployment would terminate JWT at the Gateway, propagate a verified user context, and enforce that `wallet_id` belongs to the caller before any state mutation. Deferred because the take-home brief explicitly scoped auth out.

## Downstream consumers of `wallet.*.paid` events

The wallet publishes `top_up.paid` and `fund_transfer.paid` to RabbitMQ but nothing currently consumes them — they are emitted purely so that real downstream systems (push notifications, audit log, analytics warehouse, KYC re-checks) can be plugged in without touching the wallet service. Adding even one such consumer was outside the POC's scope, but the contract is in place so it's cheap to do later.

## Per-service observability (OpenTelemetry traces across HTTP + RabbitMQ)

A correlation_id flows through the system manually for debugging, but there are no distributed traces. Wiring OpenTelemetry into FastAPI, the HTTP client, and the aio-pika consumer/producer would give a single span tree per top-up across all four services and the broker hop. This is essential before any production rollout but adds a non-trivial collector + backend setup that was not justified for ten tests' worth of demonstration.

## Horizontal scale: partition outbox_events, multiple consumers per queue

For higher throughput, `outbox_events` would be partitioned by `aggregate_id` so independent publishers can drain disjoint shards in parallel without contention. Similarly, the wallet settlements queue could be consumed by multiple workers with message-key-based routing so that events for the same wallet land on the same consumer (preserving per-wallet ordering) while different wallets fan out. The POC runs a single consumer per service, which is fine until traffic reaches a few hundred events per second.

## Retry-on-serialization-failure middleware for the idempotency claim

Two concurrent requests with the same `Idempotency-Key` hit `INSERT ... ON CONFLICT DO NOTHING` simultaneously. CockroachDB serializes the writes; the loser receives a `40001` (serialization failure) instead of the spec-mandated 409. A small FastAPI middleware that re-runs the request handler on `serialization_failure` would let the second attempt see the now-committed row and replay it as an idempotent hit. Data correctness is unaffected today (no double top-up, no double charge); only the HTTP status of the loser is wrong in this rare race.

## Stronger typing for status fields

`top_up.status`, `charge.status`, and `idempotency_keys.state` are stored as plain strings with `CheckConstraint` at the table level. Application code uses raw string literals everywhere. Migrating these to `Enum` (or `typing.Literal`) plus a `TypeAdapter` for serialization would catch typos at edit time and make state-machine transitions self-documenting. Skipped here because the constraint already prevents bad values at write time, and the lift across four services adds churn for a POC.

## Singleton AsyncClient + connection pool tuning

The Gateway and the Wallet's HTTP client both create a fresh `httpx.AsyncClient` per request, paying TCP/TLS setup cost on every forwarded call. A module-level singleton with explicit `limits` (max connections, keepalive) would meaningfully reduce p99 latency at any real load. The same applies to the SQLAlchemy engines, which currently use defaults (`pool_size=5`, no timeout) — fine for one user clicking a button, not fine for a real test.

## Chaos tests (kill consumer mid-process, network partitions)

The integration tests cover happy paths and a handful of failure modes (duplicate webhook, duplicate idempotency key, provider rejection), but they do not exercise the system under deliberate disruption — killing the consumer between dedup write and state transition, partitioning the broker mid-ack, dropping packets between wallet and payment gateway. The state machine + outbox + processed-events triad is designed to survive these, but proving it requires a chaos harness (Toxiproxy, Pumba, or similar) that was out of scope.
