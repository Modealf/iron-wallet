# Diagram Brief — Top-Up Architecture & Flow (Excalidraw)

This is a self-contained spec for generating a system architecture diagram in Excalidraw (or any equivalent tool). The agent receiving this brief needs no other context.

---

## 1. Purpose

Visualize how a single **top-up request** travels through a 4-service fintech backend (an investment wallet system called "IronWallet"). The diagram serves two goals at once:

1. **Show what each service is** — its tables, endpoints, events.
2. **Show how a top-up request flows through them** — using numbered arrows and a step-by-step legend.

It is **not a sequence diagram** and **not a flowchart**. It is an **architecture diagram with the request walked across it as numbered steps.**

---

## 2. Aesthetic / style

**Anthropic Claude–blog feel.** Warm, professional, soft.

- **Background:** warm cream `#f8f6f3`
- **Strokes / outlines:** dark gray `#4a4a4a`, ~2px stroke width
- **Box corners:** rounded, ~12px radius
- **Service-card fills (header band only — the body of the card stays white/cream):**
  - Investment-Wallet → soft teal `#9dd4c7`
  - Payment-Gateway → soft blue `#a8c5e6`
  - Provider (mock) → warm beige `#f4e4c1`
  - Omnibus → light gray `#e8e6e3`
  - RabbitMQ → deeper beige `#e9d8c4`
  - Gateway / Client → white / no fill (neutral, since they hold no DB)
- **Primary text:** near-black `#1a1a1a`
- **Secondary / italic notes:** muted gray `#5a5a5a` to `#6a6a6a`
- **Source-of-truth highlight:** small star `★` in muted gold `#b08400` next to the relevant table
- **Font:** system-ui sans (Helvetica Neue / -apple-system feel). Body 13px, headings 14–16px, titles 22px. Use a monospace face (Menlo / SF Mono) for code-like content (table names, endpoints).

---

## 3. Layout

Canvas is wide-aspect, roughly 1500 × 1180 (units / px).

### Top row (sync request chain) — y ≈ 110–280

Five elements left-to-right, evenly spaced:

1. **Client** (smallest box, white, "mobile / web app" subtitle)
2. **Gateway** (small white card)
3. **Investment-Wallet** (large teal-headered card — the orchestrator, biggest content)
4. **Payment-Gateway** (medium blue-headered card)
5. **Provider (mock)** (small beige card, says "Moyasar — returns payment_id, fires signed webhook")

### Bottom row (async settlement loop) — y ≈ 600–820

Two elements, positioned roughly under the top-row right side:

6. **RabbitMQ** (deeper-beige card, mid-canvas horizontally — sits under the wallet/payment-gateway area)
7. **Omnibus** (large gray-headered card, sits under the provider area on the right)

### Why this layout

- The top row is left-to-right because that's the synchronous request chain.
- The async path comes back **clockwise**: Provider → Omnibus (right side, going down) → RabbitMQ (going left) → back up to Investment-Wallet (left side, going up). This forms a visual loop without crossings.

---

## 4. Per-service card contents

Each "card" (except Client and Provider, which are simple labeled boxes) is structured as:

- **Header band** (colored, with the service name in bold)
- **Body** (white, with three sub-sections separated by small gaps): `ENDPOINT`, `TABLES`, `EVENTS` (or `CALLS` where relevant)

Sub-section labels are small caps (e.g., `ENDPOINTS`, 11px bold gray). Items within are monospace 11.5px.

### Client (simple box, no card)

- Title: **Client**
- Subtitle: *mobile / web app*

### Gateway (small card)

- Header: **Gateway**
- `FORWARDS`
  - `POST /top-ups`
  - `POST /bank-transfers`

### Investment-Wallet (large teal-headed card — the most content)

- Header: **Investment-Wallet**
- `ENDPOINT`
  - `POST /top-ups`
- `TABLES`
  - `wallets, top_ups, fund_transfers`
  - `idempotency_keys, processed_events`
  - `outbox_events`
- `EVENTS`
  - `↓ consume settlement.completed`
  - `↑ publish top_up.paid`

### Payment-Gateway (medium blue-headed card)

- Header: **Payment-Gateway**
- `ENDPOINT`
  - `POST /charges`
- `TABLES`
  - `charges, idempotency_keys`
- `CALLS`
  - `external provider (Moyasar)`

### Provider (mock) (small beige box, no sub-sections)

- Title: **Provider (mock)**
- Subtitle (3 short lines):
  - *Moyasar*
  - *returns payment_id*
  - *fires signed webhook*

### Omnibus (large gray-headed card)

- Header: **Omnibus**
- `ENDPOINTS`
  - `POST /webhooks/moyasar`
  - `POST /bank-transfers`
- `TABLES`
  - **`statements`** ★ *source of truth* ← important highlight
  - `processed_webhooks, outbox_events`
  - `idempotency_keys`
- `EVENTS`
  - `↑ publish settlement.completed`

### RabbitMQ (deeper-beige card)

- Header: **RabbitMQ**
- `TOPIC EXCHANGE`
  - `iron_wallet`
- `QUEUES`
  - `wallet.settlements`
  - `wallet.settlements.dlq`

---

## 5. Arrows (the numbered flow)

Seven arrows total, numbered 1–7. Each carries a small dark-filled circle (~13px radius) with a white digit inside, placed near the arrow midpoint.

**Solid arrow style** = synchronous HTTP. **Dashed arrow style** (`stroke-dasharray: 6,4`) = asynchronous (webhook or queue event).

| # | From | To | Style | What it represents |
|---|------|-----|-------|--------------------|
| 1 | Client right edge | Gateway left edge | solid | `POST /top-ups` |
| 2 | Gateway right edge | Investment-Wallet left edge | solid | forward request |
| 3 | Investment-Wallet right edge | Payment-Gateway left edge | solid | `POST /charges` |
| 4 | Payment-Gateway right edge | Provider left edge | solid | create payment |
| 5 | Provider bottom | Omnibus top (curve down-left, **dashed**) | dashed | signed webhook (~1s later) |
| 6 | Omnibus left edge | RabbitMQ right edge | solid | publish `settlement.completed` (via outbox) |
| 7 | RabbitMQ top | Investment-Wallet bottom (curve up-left, **dashed**) | dashed | consumer reads event |

Arrows 5 and 7 are **curved Bezier paths**, not straight lines, so they form a clean clockwise loop on the right side and back up on the left side without crossing each other.

The numbered circles sit slightly above (or beside) each arrow, with the corresponding number in white text inside.

---

## 6. Step-descriptions panel (bottom-left)

Below the architecture, a panel titled **"Flow steps"** lists each numbered step in plain English. Each entry has the same numbered circle followed by a one-sentence description.

Use these exact descriptions:

1. Client POSTs `/top-ups` with `Idempotency-Key`. Gateway just forwards.
2. Wallet claims the idempotency key and inserts a `top_up` row (status `PENDING`) — both in one DB transaction.
3. Wallet calls Payment-Gateway. PG claims its own idem key (derived from `top_up_id`), inserts a `charge` row (status `CREATED`).
4. PG forwards to the external provider (Moyasar mocked).
5. Provider returns `payment_id` immediately; schedules a signed webhook to fire later. PG marks charge `ACCEPTED` and returns to Wallet, which transitions `top_up` `PENDING → PROCESSING` and `200`s the client.
6. Async: provider's signed webhook arrives at Omnibus. Omnibus verifies HMAC, dedups by `event_id`, inserts a `statement` and an `outbox_event` in one txn.
7. Omnibus's outbox publisher drains the row to RabbitMQ as `settlement.completed`.
8. Wallet consumer reads the event, dedups by `event_id`, transitions `top_up` `PROCESSING → PAID`, credits the wallet balance, and writes its own outbox event `top_up.paid`.

(Yes, there are 8 description lines but only 7 arrows — step 5 is doubled because that one arrow represents both the provider's immediate return *and* the start of the sync unwind back through PG and Wallet.)

---

## 7. Arrow-style legend (bottom-right)

A small key titled **"Arrow style"** with two example lines:

- **solid arrow** → "synchronous HTTP call"
- **dashed arrow** → "asynchronous (webhook / event)"

---

## 8. Title block (top center)

- Title: **Top-Up — Architecture & Flow** (22px, bold)
- Subtitle: *services own their tables; numbered arrows trace one top-up request through the system* (13px, muted)

---

## 9. Constraints / quality bar

- **No clipping.** Every text label fits inside its container with at least 8px of padding on all sides.
- **No crossing arrows.** The two dashed curves (5 and 7) loop on opposite sides of the canvas.
- **Numbered circles** are visually consistent: same size, same dark fill, white digits, sit just above the arrow midpoint.
- **Source-of-truth star** is the only visually-distinct annotation in the table lists — don't add badges to other items.
- **The diagram should print legibly at A4 / Letter landscape.** Avoid font sizes below 11px.

---

## 10. Reference rendering

A reference SVG of this exact diagram exists at `docs/diagrams/top-up-architecture.svg` in the repo. The visual target you're producing should look like a clean, hand-drawn-feel re-rendering of that SVG in Excalidraw style (slightly imperfect strokes, hand-feel fonts) but preserving every layout decision and every text label above.
