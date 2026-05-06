# Future work

Items deliberately deferred from the POC. Each adds operational or implementation cost without changing the core architecture.

## Dedicated outbox publisher with leader election

The current drain is an asyncio task inside each API process — fine for a single replica. For HA, run the publisher as a separate process and combine `FOR UPDATE SKIP LOCKED` with a Cockroach-backed lease so scaling the API tier horizontally doesn't multiply outbox traffic.

## Retry-on-serialization-failure middleware

Two concurrent requests with the same `Idempotency-Key` race on the dedup insert; the loser gets a Cockroach `40001` and surfaces as a 500. A small FastAPI middleware that re-runs the handler on serialization failure would let the second attempt see the now-committed row and replay it as a normal idempotent hit, restoring the spec's 409 behavior.

## Per-service observability (OpenTelemetry)

A `correlation_id` flows through manually for debugging, but there are no distributed traces. Wiring OpenTelemetry into FastAPI, httpx, and aio-pika would give a single span tree per top-up across all four services and the broker hop.

## Horizontal scale: partition outbox + multi-consumer routing

At higher throughput, partition `outbox_events` by `aggregate_id` so independent publishers drain disjoint shards. Consume `wallet.settlements` with multiple workers using message-key-based routing so events for the same wallet land on the same consumer (preserving per-wallet ordering).

## Singleton AsyncClient + connection pool tuning

The Gateway and the wallet's HTTP client create a fresh `httpx.AsyncClient` per request — full TCP/TLS setup on every call. A module-level singleton with explicit `limits` would meaningfully reduce p99 latency at load. The SQLAlchemy engines run on defaults too; both deserve sizing for real traffic.

## Downstream consumers of `wallet.*.paid` events

The wallet publishes `top_up.paid` and `fund_transfer.paid` to RabbitMQ but nothing consumes them yet. The contract is in place so push notifications, audit logs, or analytics can plug in without touching the wallet service.

## Chaos tests

Existing tests cover happy paths and the most-confused state transitions. Proving the state-machine + outbox + processed-events triad survives consumer crashes mid-processing, broker partitions, and dropped packets requires a chaos harness (Toxiproxy, Pumba) that wasn't justified for the POC.
