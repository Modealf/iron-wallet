# Diagram Brief — Top-Up State Machine

A standalone description of the state machine for a `top_up` row in Investment-Wallet's database. The agent receiving this should pick the diagram type, layout, and visual style.

---

## Audience and goal

After looking at this for ~15 seconds the reviewer should know:

1. **Every state** a top-up can be in.
2. **Every legal transition** and what triggers it.
3. **Which states are terminal** (absorbing — no outgoing transitions).
4. **That transitions are guarded in SQL**, which is what makes the system idempotent under retries.

This diagram is small but conceptually dense. It exists because state-machine discipline is the second line of defense behind event-level dedup; if dedup ever fails, the guarded UPDATE prevents a double credit.

---

## The states

| State | Meaning |
|---|---|
| **PENDING** | top-up record just created. Wallet has accepted the client request but hasn't yet contacted Payment-Gateway. |
| **PROCESSING** | Payment-Gateway has accepted the charge. The provider's settlement webhook has not yet arrived. The user can see "processing" in their UI. |
| **PAID** *(terminal)* | Settlement event has been received and applied. Wallet balance has been credited. |
| **FAILED** *(terminal)* | Either the provider rejected the charge, or it never settled. No money moved into the wallet. |

---

## The transitions

| From | To | Triggered by |
|---|---|---|
| (none) | **PENDING** | Wallet successfully claims the idempotency key and inserts the `top_up` row inside one DB transaction. |
| PENDING | **PROCESSING** | Payment-Gateway returns `ACCEPTED` (provider authorized the charge). |
| PENDING | **FAILED** | Payment-Gateway returns `REJECTED` (provider declined the charge). |
| PROCESSING | **PAID** | Wallet's settlement consumer receives `settlement.completed`, dedups, applies. |
| PROCESSING | **FAILED** | Provider settlement timeout / explicit failure event (rare, manual or scheduled reconciliation). |

PAID and FAILED have **no outgoing transitions** — once a top-up enters either, it stays forever.

---

## How transitions are enforced

Every state change goes through the same SQL guard:

```sql
UPDATE top_ups
SET status = $new
WHERE id = $id AND status = $expected
RETURNING id;
```

If the `WHERE` clause doesn't match — because the row is in a different state already — zero rows are returned and the application raises `IllegalStateTransition`. Consumers either retry (transient mismatch, e.g. the settlement event arrived before PROCESSING) or send the message to a DLQ (permanent mismatch, e.g. settlement for a `top_up` that's already PAID — which is a no-op anyway because the consumer's inbound dedup table catches the replay before the SQL even runs).

---

## Concepts to make obvious

- **Two terminal states** (PAID, FAILED), drawn so they look distinct from non-terminal ones.
- **Transitions are guarded by SQL**, not by application-level booleans — this is what makes the system survive dropped connections, duplicate events, and process restarts.
- **Re-applying a settlement to an already-PAID row is a no-op** because the guarded UPDATE matches zero rows. This is the second line of defense behind the consumer's `processed_events` dedup.

---

## What this diagram is not

- Not a flowchart of the broader top-up pipeline (that's the top-up architecture diagram).
- Not a sequence diagram.
- Not a class diagram.

---

## Aesthetic preference

Warm cream background, Anthropic-blog feel. State diagrams traditionally use rounded rectangles or circles for states with labeled arrows for transitions; the agent should pick whatever feels cleanest. Terminal states usually have a doubled border or some visually-distinct treatment. An initial-state marker (filled black dot) feeding into PENDING is conventional.

---

## Reference

`docs/diagrams/top-up-architecture-brief.md` for the larger system context — the state machine sits inside the Investment-Wallet service shown there. The visual language (warm cream, soft strokes) should be consistent across the series.
