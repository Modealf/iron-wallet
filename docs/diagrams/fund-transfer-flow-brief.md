# Diagram Brief — Fund-Transfer Flow

A standalone description of the fund-transfer flow. The agent receiving this should pick the diagram type, layout, and visual style.

---

## Audience and goal

The reviewer, after looking at this for under a minute, should understand:

1. **Fund-transfer is shorter than top-up** — there is no payment provider involved at all.
2. **The user's bank is the entry point** — the user makes a regular bank transfer to their virtual IBAN.
3. **The pipeline has three internal services**: Bank → Omnibus → RabbitMQ → Investment-Wallet.
4. **The bottom half of this flow is identical to top-up's settlement pipeline** — once Omnibus has a statement, the rest is shared infrastructure.

---

## The system

A subset of the larger architecture. Three internal services participate:

### Omnibus
Receives the bank's notification. In production this would be a real bank API integration; in this POC it's mocked via an admin endpoint `POST /bank-transfers`.

### RabbitMQ
Carries the `settlement.completed` event from Omnibus to the Wallet consumer. Same exchange and queue used for top-up settlements.

### Investment-Wallet
Consumes the event. Inserts a `fund_transfer` row directly with status `PAID`. Credits the wallet balance. No PENDING/PROCESSING gating — by the time the bank tells us, the money has already arrived.

The user's bank itself is external (mocked). No payment-gateway, no Moyasar, no card capture.

---

## The flow

1. **User → bank.** Out of band: the user opens their banking app and sends a regular transfer to the virtual IBAN that IronWallet gave them. The money lands in IronWallet's omnibus bank account.
2. **Bank → Omnibus.** The bank notifies Omnibus that money arrived. In production this is via a real bank API or webhook; in this POC it's a mocked `POST /bank-transfers` admin endpoint with `{ virtual_iban, amount, bank_reference, wallet_id }`.
3. **Omnibus, in one DB transaction:** dedups on `bank_reference` (enforced by a `UNIQUE(kind, source_ref)` index on `statements`), inserts a `statement` row with `kind='fund_transfer'`, and writes an `outbox_event`.
4. **Omnibus's outbox publisher** drains the new row to RabbitMQ as `settlement.completed` (with `kind='fund_transfer'` in the payload).
5. **Wallet consumer** reads the event, dedups by `event_id`, inserts a `fund_transfer` row with status `PAID`, credits the wallet's `balance_minor`, and writes its own outbox event `fund_transfer.paid`.

---

## Concepts to make obvious

- **No payment-gateway involvement.** The Payment-Gateway service should be conspicuously absent. This is the simplest path to crediting a wallet.
- **No PENDING/PROCESSING states.** A `fund_transfer` only exists in `PAID` state, because the money has already settled at the bank by the time anyone tells us about it.
- **The settlement pipeline (Omnibus → RabbitMQ → Wallet consumer) is shared with top-up.** Once a `statement` row exists in Omnibus, the rest of the system doesn't care which entry path produced it.
- **`statements` is still the source of truth** — same as top-up.
- **Idempotency lives at two boundaries**: bank → omnibus (by `bank_reference`) and omnibus → wallet (by event id).

---

## What this diagram is not

- Not a duplicate of the top-up flow — emphasize what's *different*: no Payment-Gateway, no Provider, no PENDING/PROCESSING gating.
- Not a sequence diagram with lifelines.

---

## Aesthetic preference

Warm cream background, Anthropic-blog feel. Match whatever visual language is established by sibling diagrams in this series — consistent service colors, consistent stroke weights, same typography.

---

## Reference

`docs/diagrams/architecture-brief.md` for the at-rest system view, and `docs/diagrams/top-up-architecture-brief.md` for the more complex sibling flow. This diagram should feel like a clear "here's what changes when there's no card" companion.
