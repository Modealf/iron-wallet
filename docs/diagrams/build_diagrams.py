#!/usr/bin/env python3
"""
Generate four .excalidraw scene files for IronWallet docs (written to ./Excalidraw):

  - top-up-architecture.excalidraw   (top-up flow over the architecture)
  - architecture.excalidraw          (at-rest system architecture)
  - fund-transfer-flow.excalidraw    (fund-transfer flow with numbered steps)
  - top-up-state-machine.excalidraw  (top_up row state machine)

Shared visual language:
  warm cream bg #f8f6f3, dark gray strokes #4a4a4a, soft service-card fills,
  hand-drawn roughness, system-ui body, monospace for code-like content.
"""
import json, random, time, os

random.seed(2026)

NOW = int(time.time() * 1000)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "Excalidraw")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------- color palette (from top-up brief) ----------
TEAL    = "#9dd4c7"   # Investment-Wallet header
BLUE    = "#a8c5e6"   # Payment-Gateway header
BEIGE_L = "#f4e4c1"   # Provider mock
BEIGE_D = "#e9d8c4"   # RabbitMQ
GRAY    = "#e8e6e3"   # Omnibus
WHITE   = "#ffffff"
CREAM   = "#f8f6f3"   # canvas bg
INK     = "#1a1a1a"
STROKE  = "#4a4a4a"
MUTED   = "#5a5a5a"
MUTED2  = "#6a6a6a"
GOLD    = "#b08400"   # source-of-truth star
ROSE    = "#e6b3b3"   # FAILED state hint
MINT    = "#cfe7d6"   # PAID state hint

# ---------- element factory ----------
_id = [0]
def nid():
    _id[0] += 1
    return f"el-{_id[0]:05d}"

def seed():
    return random.randint(1, 2_000_000_000)

DEFAULTS = {
    "angle": 0,
    "strokeColor": STROKE,
    "backgroundColor": "transparent",
    "fillStyle": "solid",
    "strokeWidth": 2,
    "strokeStyle": "solid",
    "roughness": 1,
    "opacity": 100,
    "groupIds": [],
    "frameId": None,
    "roundness": None,
    "boundElements": None,
    "updated": NOW,
    "link": None,
    "locked": False,
    "isDeleted": False,
}

def base(extra):
    d = {"id": nid(), "seed": seed(), "version": 1, "versionNonce": seed()}
    d.update(DEFAULTS)
    d.update(extra)
    return d

def rect(x, y, w, h, *, fill="transparent", stroke=STROKE,
         dashed=False, rounded=True, sw=2, opacity=100):
    return base({
        "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke,
        "backgroundColor": fill,
        "fillStyle": "solid",
        "strokeStyle": "dashed" if dashed else "solid",
        "strokeWidth": sw,
        "opacity": opacity,
        "roundness": {"type": 3} if rounded else None,
    })

def ellipse(cx, cy, r, *, fill=INK, stroke=INK, sw=1, dashed=False):
    return base({
        "type": "ellipse",
        "x": cx - r, "y": cy - r, "width": 2*r, "height": 2*r,
        "strokeColor": stroke,
        "backgroundColor": fill,
        "fillStyle": "solid",
        "strokeWidth": sw,
        "strokeStyle": "dashed" if dashed else "solid",
        "roundness": None,
        "roughness": 0,
    })

# fontFamily: 1 hand (Virgil), 2 Helvetica, 3 Cascadia mono, 5 Excalifont
def text(x, y, content, *, size=14, family=1, color=INK,
         align="left", w=None, h=None):
    if w is None:
        w = max(40, int(len(content) * size * 0.55))
    if h is None:
        h = int(size * 1.25)
    return base({
        "type": "text",
        "x": x, "y": y, "width": w, "height": h,
        "text": content,
        "originalText": content,
        "fontSize": size,
        "fontFamily": family,
        "textAlign": align,
        "verticalAlign": "top",
        "baseline": int(size * 0.85),
        "containerId": None,
        "lineHeight": 1.25,
        "strokeColor": color,
        "roughness": 1,
    })

def arrow(points, *, dashed=False, sw=2, color=STROKE, head=True):
    x0, y0 = points[0]
    rel = [[px - x0, py - y0] for px, py in points]
    return base({
        "type": "arrow",
        "x": x0, "y": y0,
        "width": max(1, max(abs(p[0]) for p in rel)),
        "height": max(1, max(abs(p[1]) for p in rel)),
        "strokeColor": color,
        "backgroundColor": "transparent",
        "strokeStyle": "dashed" if dashed else "solid",
        "strokeWidth": sw,
        "roundness": {"type": 2},
        "points": rel,
        "lastCommittedPoint": None,
        "startBinding": None,
        "endBinding": None,
        "startArrowhead": None,
        "endArrowhead": "arrow" if head else None,
    })

def numbered(elements, cx, cy, n, *, r=12):
    elements.append(ellipse(cx, cy, r))
    elements.append(text(cx - 6, cy - 8, str(n), size=14, family=1,
                         color=WHITE, w=12, h=16, align="center"))

def card(elements, x, y, w, h, name, header_fill, *, sections, name_size=18):
    """A standard service card: white body, colored header band, sections list."""
    elements.append(rect(x, y, w, h, fill=WHITE))
    elements.append(rect(x, y, w, 44, fill=header_fill))
    elements.append(text(x, y + 12, name, size=name_size, family=1,
                         w=w, h=22, align="center"))
    cy = y + 56
    for label, items in sections:
        elements.append(text(x + 16, cy, label, size=10, family=1,
                             color=MUTED, w=200, h=14))
        cy += 18
        for item in items:
            # tuple: (text, monospace?) or string (mono default for items)
            if isinstance(item, tuple):
                content, mono = item
            else:
                content, mono = item, True
            fam = 3 if mono else 1
            elements.append(text(x + 16, cy, content, size=12,
                                 family=fam, w=w - 32, h=16))
            cy += 18
        cy += 8

def write_scene(filename, elements, *, bg=CREAM):
    scene = {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": {"gridSize": None, "viewBackgroundColor": bg},
        "files": {},
    }
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w") as f:
        json.dump(scene, f, indent=2)
    print(f"  wrote {len(elements):>3} elements -> {filename}")

# ====================================================================
# DIAGRAM 1 — System architecture (at rest)
# ====================================================================
def build_architecture():
    el = []
    # Title
    el.append(text(450, 30, "System Architecture",
                   size=28, family=1, w=600, h=36, align="center"))
    el.append(text(370, 70,
                   "services, their tables, and how they connect — at rest",
                   size=14, family=1, color=MUTED2, w=760, h=20, align="center"))

    # Internal boundary (dashed rounded rectangle)
    el.append(rect(220, 120, 1180, 870, fill="transparent",
                   dashed=True, sw=2))
    el.append(text(240, 132, "IronWallet (internal)",
                   size=13, family=1, color=MUTED, w=240, h=18))

    # ---------- Internal services ----------
    # Gateway (left, no DB)
    card(el, 260, 240, 170, 130, "Gateway", WHITE,
         name_size=16,
         sections=[("FORWARDS", [
             "POST /top-ups",
             "POST /bank-transfers",
         ])])

    # Investment-Wallet (top center)
    card(el, 480, 170, 320, 320, "Investment-Wallet", TEAL,
         sections=[
             ("TABLES", [
                 "wallets, top_ups, fund_transfers",
                 "idempotency_keys, processed_events",
                 "outbox_events",
             ]),
             ("ENDPOINT", [(("POST /top-ups"), True)]),
             ("EVENTS", [
                 "↓ consume settlement.completed",
                 "↑ publish top_up.paid",
                 "↑ publish fund_transfer.paid",
             ]),
         ])

    # Payment-Gateway (top right)
    card(el, 880, 220, 240, 240, "Payment-Gateway", BLUE,
         sections=[
             ("TABLES", ["charges, idempotency_keys"]),
             ("ENDPOINT", ["POST /charges"]),
             ("CALLS", [("external provider (Moyasar)", False)]),
         ])

    # RabbitMQ (bottom left)
    card(el, 480, 620, 260, 220, "RabbitMQ", BEIGE_D,
         sections=[
             ("TOPIC EXCHANGE", ["iron_wallet"]),
             ("QUEUES", [
                 "wallet.settlements",
                 "wallet.settlements.dlq",
             ]),
         ])

    # Omnibus (bottom right) — extra detail because brief calls out star
    OB_X, OB_Y, OB_W, OB_H = 880, 590, 340, 320
    el.append(rect(OB_X, OB_Y, OB_W, OB_H, fill=WHITE))
    el.append(rect(OB_X, OB_Y, OB_W, 44, fill=GRAY))
    el.append(text(OB_X, OB_Y + 12, "Omnibus", size=18, family=1,
                   w=OB_W, h=22, align="center"))
    cy = OB_Y + 56
    el.append(text(OB_X + 16, cy, "ENDPOINTS", size=10, family=1, color=MUTED, w=120, h=14))
    el.append(text(OB_X + 16, cy + 18, "POST /webhooks/moyasar", size=12, family=3, w=260, h=16))
    el.append(text(OB_X + 16, cy + 36, "POST /bank-transfers", size=12, family=3, w=260, h=16))
    cy += 64
    el.append(text(OB_X + 16, cy, "TABLES", size=10, family=1, color=MUTED, w=120, h=14))
    el.append(text(OB_X + 16, cy + 18, "statements", size=12, family=3, w=100, h=16))
    el.append(text(OB_X + 108, cy + 16, "★", size=16, family=1, color=GOLD, w=16, h=20))
    el.append(text(OB_X + 130, cy + 18, "source of truth",
                   size=12, family=1, color=MUTED2, w=180, h=16))
    el.append(text(OB_X + 16, cy + 36, "processed_webhooks, outbox_events",
                   size=12, family=3, w=300, h=16))
    el.append(text(OB_X + 16, cy + 54, "idempotency_keys", size=12, family=3, w=200, h=16))
    cy += 82
    el.append(text(OB_X + 16, cy, "EVENTS", size=10, family=1, color=MUTED, w=120, h=14))
    el.append(text(OB_X + 16, cy + 18, "↑ publish settlement.completed",
                   size=12, family=3, w=300, h=16))

    # ---------- External actors (outside the dashed box) ----------
    # Client (left)
    el.append(rect(60, 280, 130, 110, fill=WHITE))
    el.append(text(60, 304, "Client", size=16, family=1, w=130, h=22, align="center"))
    el.append(text(60, 332, "mobile / web app", size=12, family=1,
                   color=MUTED2, w=130, h=18, align="center"))
    el.append(text(60, 360, "external", size=11, family=1,
                   color=MUTED2, w=130, h=16, align="center"))

    # Provider / Moyasar (right of payment-gateway, outside box)
    el.append(rect(1430, 270, 150, 140, fill=BEIGE_L))
    el.append(text(1430, 290, "Provider", size=15, family=1, w=150, h=20, align="center"))
    el.append(text(1430, 312, "(Moyasar)", size=12, family=1,
                   color=MUTED2, w=150, h=18, align="center"))
    el.append(text(1430, 348, "external — mocked", size=11, family=1,
                   color=MUTED2, w=150, h=16, align="center"))
    el.append(text(1430, 368, "card payments", size=11, family=1,
                   color=MUTED2, w=150, h=16, align="center"))

    # User's bank (right of omnibus, outside box)
    el.append(rect(1430, 640, 150, 140, fill=WHITE))
    el.append(text(1430, 660, "User's bank", size=15, family=1, w=150, h=20, align="center"))
    el.append(text(1430, 696, "external — mocked", size=11, family=1,
                   color=MUTED2, w=150, h=16, align="center"))
    el.append(text(1430, 716, "bank-transfer", size=11, family=1,
                   color=MUTED2, w=150, h=16, align="center"))
    el.append(text(1430, 732, "notifications", size=11, family=1,
                   color=MUTED2, w=150, h=16, align="center"))

    # ---------- Sync HTTP edges (solid) ----------
    # Client → Gateway
    el.append(arrow([(190, 332), (260, 332)]))
    # Gateway → IW
    el.append(arrow([(430, 280), (480, 280)]))
    # Gateway → Omnibus  (curve down-right around RabbitMQ)
    el.append(arrow([(345, 370), (350, 460), (820, 720), (880, 720)]))
    # IW → PG
    el.append(arrow([(800, 320), (880, 320)]))
    # PG → Provider
    el.append(arrow([(1120, 320), (1430, 320)]))
    # Provider → Omnibus  (HMAC webhook, curves down-left to top of Omnibus)
    el.append(arrow([(1505, 410), (1500, 540), (1200, 590)]))
    # Bank → Omnibus
    el.append(arrow([(1430, 700), (1220, 700)]))

    # ---------- Async event edges (dashed) ----------
    # Omnibus → RabbitMQ (publish settlement.completed)
    el.append(arrow([(880, 770), (740, 770)], dashed=True))
    # RabbitMQ → Investment-Wallet (consume)
    el.append(arrow([(610, 620), (450, 530), (560, 490)], dashed=True))
    # IW → RabbitMQ (publish top_up.paid / fund_transfer.paid)
    el.append(arrow([(640, 490), (640, 560), (650, 620)], dashed=True))

    # ---------- Edge labels ----------
    el.append(text(195, 308, "/top-ups\n/bank-transfers",
                   size=11, family=3, color=MUTED, w=80, h=28))
    el.append(text(440, 256, "/top-ups", size=11, family=3, color=MUTED, w=80, h=14))
    el.append(text(800, 296, "/charges", size=11, family=3, color=MUTED, w=80, h=14))
    el.append(text(1190, 296, "create payment",
                   size=11, family=1, color=MUTED, w=120, h=14))
    el.append(text(1340, 470, "HMAC webhook",
                   size=11, family=1, color=MUTED, w=120, h=14))
    el.append(text(1240, 678, "/bank-transfers",
                   size=11, family=3, color=MUTED, w=120, h=14))
    el.append(text(425, 460, "/bank-transfers (admin)",
                   size=10, family=3, color=MUTED, w=200, h=14))

    # async-edge labels (italic, near arrows)
    el.append(text(770, 750, "settlement.completed",
                   size=11, family=3, color=MUTED, w=180, h=14))
    el.append(text(440, 470, "consume",
                   size=11, family=1, color=MUTED, w=80, h=14))
    el.append(text(660, 540, "publish",
                   size=11, family=1, color=MUTED, w=80, h=14))

    # ---------- Legend (bottom) ----------
    LX, LY, LW, LH = 60, 1010, 760, 130
    el.append(rect(LX, LY, LW, LH, fill=WHITE))
    el.append(text(LX + 20, LY + 14, "Legend", size=16, family=1, w=200, h=22))
    # solid
    el.append(arrow([(LX + 30, LY + 60), (LX + 110, LY + 60)]))
    el.append(text(LX + 130, LY + 50, "solid", size=13, family=1, w=80, h=18))
    el.append(text(LX + 130, LY + 70, "synchronous HTTP",
                   size=12, family=1, color=MUTED, w=240, h=18))
    # dashed
    el.append(arrow([(LX + 30, LY + 110), (LX + 110, LY + 110)], dashed=True))
    el.append(text(LX + 130, LY + 100, "dashed", size=13, family=1, w=80, h=18))
    el.append(text(LX + 130, LY + 120, "asynchronous event (RabbitMQ)",
                   size=12, family=1, color=MUTED, w=300, h=18))
    # dashed boundary
    el.append(rect(LX + 360, LY + 50, 32, 22, fill="transparent", dashed=True, sw=1.5))
    el.append(text(LX + 400, LY + 50, "internal boundary",
                   size=12, family=1, color=MUTED, w=240, h=18))
    # star
    el.append(text(LX + 400, LY + 76, "★", size=14, family=1, color=GOLD, w=16, h=18))
    el.append(text(LX + 420, LY + 76, "source of truth (statements)",
                   size=12, family=1, color=MUTED, w=300, h=18))
    # databases note
    el.append(text(LX + 400, LY + 100, "every service owns its DB — no shared tables",
                   size=12, family=1, color=MUTED, w=400, h=18))

    write_scene("architecture.excalidraw", el)


# ====================================================================
# DIAGRAM 2 — Fund-transfer flow
# ====================================================================
def build_fund_transfer():
    el = []
    el.append(text(400, 30, "Fund-Transfer Flow",
                   size=28, family=1, w=700, h=36, align="center"))
    el.append(text(360, 70,
                   "no payment provider — bank notifies, we credit the wallet",
                   size=14, family=1, color=MUTED2, w=780, h=20, align="center"))

    # ---------- Linear chain ----------
    # User
    el.append(rect(50, 320, 130, 110, fill=WHITE))
    el.append(text(50, 340, "User", size=18, family=1, w=130, h=22, align="center"))
    el.append(text(50, 372, "their banking app",
                   size=12, family=1, color=MUTED2, w=130, h=18, align="center"))
    el.append(text(50, 394, "out of band",
                   size=11, family=1, color=MUTED2, w=130, h=16, align="center"))

    # User's bank (external)
    el.append(rect(240, 320, 160, 110, fill=WHITE))
    el.append(text(240, 340, "User's bank", size=16, family=1,
                   w=160, h=22, align="center"))
    el.append(text(240, 370, "external — mocked",
                   size=12, family=1, color=MUTED2, w=160, h=18, align="center"))
    el.append(text(240, 390, "wires money in",
                   size=11, family=1, color=MUTED2, w=160, h=16, align="center"))

    # Omnibus card
    OB_X, OB_Y, OB_W, OB_H = 460, 220, 340, 320
    el.append(rect(OB_X, OB_Y, OB_W, OB_H, fill=WHITE))
    el.append(rect(OB_X, OB_Y, OB_W, 44, fill=GRAY))
    el.append(text(OB_X, OB_Y + 12, "Omnibus", size=18, family=1,
                   w=OB_W, h=22, align="center"))
    cy = OB_Y + 56
    el.append(text(OB_X + 16, cy, "ENDPOINT", size=10, family=1, color=MUTED, w=120, h=14))
    el.append(text(OB_X + 16, cy + 18, "POST /bank-transfers",
                   size=12, family=3, w=260, h=16))
    cy += 50
    el.append(text(OB_X + 16, cy, "ONE DB TXN", size=10, family=1, color=MUTED, w=140, h=14))
    el.append(text(OB_X + 16, cy + 18, "• dedup on bank_reference",
                   size=12, family=1, w=300, h=16))
    el.append(text(OB_X + 16, cy + 36, "• insert statement (kind=fund_transfer)",
                   size=12, family=1, w=300, h=16))
    el.append(text(OB_X + 16, cy + 54, "• write outbox_event",
                   size=12, family=1, w=300, h=16))
    cy += 82
    el.append(text(OB_X + 16, cy, "TABLES", size=10, family=1, color=MUTED, w=120, h=14))
    el.append(text(OB_X + 16, cy + 18, "statements",
                   size=12, family=3, w=100, h=16))
    el.append(text(OB_X + 108, cy + 16, "★", size=16, family=1, color=GOLD, w=16, h=20))
    el.append(text(OB_X + 128, cy + 18, "source of truth",
                   size=12, family=1, color=MUTED2, w=180, h=16))
    el.append(text(OB_X + 16, cy + 36, "processed_webhooks, outbox_events",
                   size=12, family=3, w=300, h=16))

    # RabbitMQ
    card(el, 870, 280, 240, 200, "RabbitMQ", BEIGE_D,
         sections=[
             ("EXCHANGE", ["iron_wallet"]),
             ("QUEUE", ["wallet.settlements"]),
         ])

    # Investment-Wallet
    IW_X, IW_Y, IW_W, IW_H = 1180, 200, 320, 360
    el.append(rect(IW_X, IW_Y, IW_W, IW_H, fill=WHITE))
    el.append(rect(IW_X, IW_Y, IW_W, 44, fill=TEAL))
    el.append(text(IW_X, IW_Y + 12, "Investment-Wallet", size=18, family=1,
                   w=IW_W, h=22, align="center"))
    cy = IW_Y + 56
    el.append(text(IW_X + 16, cy, "CONSUMER", size=10, family=1, color=MUTED, w=140, h=14))
    el.append(text(IW_X + 16, cy + 18, "settlement.completed",
                   size=12, family=3, w=240, h=16))
    cy += 50
    el.append(text(IW_X + 16, cy, "DOES (one DB txn)",
                   size=10, family=1, color=MUTED, w=200, h=14))
    el.append(text(IW_X + 16, cy + 18, "• dedup on event_id",
                   size=12, family=1, w=280, h=16))
    el.append(text(IW_X + 16, cy + 36, "• insert fund_transfer (PAID)",
                   size=12, family=1, w=280, h=16))
    el.append(text(IW_X + 16, cy + 54, "• credit wallet balance_minor",
                   size=12, family=1, w=280, h=16))
    el.append(text(IW_X + 16, cy + 72, "• write outbox: fund_transfer.paid",
                   size=12, family=1, w=300, h=16))
    cy += 100
    el.append(text(IW_X + 16, cy, "STATE", size=10, family=1, color=MUTED, w=120, h=14))
    el.append(text(IW_X + 16, cy + 18, "PAID only",
                   size=13, family=3, color=INK, w=200, h=18))
    el.append(text(IW_X + 16, cy + 38, "no PENDING / PROCESSING gating",
                   size=11, family=1, color=MUTED2, w=300, h=16))

    # ---------- Numbered arrows ----------
    # 1. User → Bank (out of band, dashed)
    el.append(arrow([(180, 360), (240, 360)], dashed=True))
    numbered(el, 210, 340, 1)

    # 2. Bank → Omnibus (sync HTTP)
    el.append(arrow([(400, 360), (460, 360)]))
    numbered(el, 430, 340, 2)

    # 3. Omnibus internal — small annotation arrow within card (skipped — body shows it)

    # 3 (renumber): Omnibus → RabbitMQ (publish via outbox, dashed)
    el.append(arrow([(800, 380), (870, 380)], dashed=True))
    numbered(el, 835, 360, 3)

    # 4. RabbitMQ → Wallet (consume, dashed)
    el.append(arrow([(1110, 380), (1180, 380)], dashed=True))
    numbered(el, 1145, 360, 4)

    # ---------- "What's missing" callout (the absent Payment-Gateway) ----------
    GH_X, GH_Y, GH_W, GH_H = 870, 540, 240, 110
    el.append(rect(GH_X, GH_Y, GH_W, GH_H, fill="transparent",
                   dashed=True, sw=1.5, opacity=60))
    el.append(text(GH_X, GH_Y + 12, "no Payment-Gateway",
                   size=14, family=1, color=MUTED, w=GH_W, h=20, align="center"))
    el.append(text(GH_X, GH_Y + 36, "no Provider",
                   size=14, family=1, color=MUTED, w=GH_W, h=20, align="center"))
    el.append(text(GH_X, GH_Y + 60, "no card capture",
                   size=14, family=1, color=MUTED, w=GH_W, h=20, align="center"))
    el.append(text(GH_X, GH_Y + 84, "money already at bank",
                   size=11, family=1, color=MUTED2, w=GH_W, h=18, align="center"))
    # Strike-through hint line
    el.append(arrow([(GH_X + 20, GH_Y + 22), (GH_X + GH_W - 20, GH_Y + 22)],
                    head=False, sw=1, color=MUTED))
    el.append(arrow([(GH_X + 20, GH_Y + 46), (GH_X + GH_W - 20, GH_Y + 46)],
                    head=False, sw=1, color=MUTED))
    el.append(arrow([(GH_X + 20, GH_Y + 70), (GH_X + GH_W - 20, GH_Y + 70)],
                    head=False, sw=1, color=MUTED))

    # ---------- Flow steps panel ----------
    FX, FY, FW, FH = 50, 700, 1120, 280
    el.append(rect(FX, FY, FW, FH, fill=WHITE))
    el.append(text(FX + 20, FY + 14, "Flow steps",
                   size=18, family=1, w=200, h=24))
    steps = [
        ("User opens their banking app and wires money to the virtual IBAN "
         "IronWallet gave them. Out of band — IronWallet isn't involved yet."),
        ("Bank notifies Omnibus that money arrived. POC: mocked admin "
         "endpoint POST /bank-transfers with { virtual_iban, amount, "
         "bank_reference, wallet_id }."),
        ("Omnibus, in one DB txn: dedups on bank_reference (UNIQUE(kind, "
         "source_ref) on statements), inserts statement(kind='fund_transfer'), "
         "writes outbox_event."),
        ("Outbox publisher drains the row to RabbitMQ as settlement.completed "
         "with kind='fund_transfer' in the payload."),
        ("Wallet consumer reads the event, dedups by event_id, inserts "
         "fund_transfer (status=PAID), credits balance_minor, writes "
         "outbox: fund_transfer.paid."),
    ]
    cy = FY + 56
    for i, s in enumerate(steps, 1):
        numbered(el, FX + 36, cy, i)
        # wrap by char count
        words = s.split(" ")
        line = ""
        lines = []
        for w in words:
            if not line:
                line = w
            elif len(line) + 1 + len(w) <= 110:
                line += " " + w
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        for j, ln in enumerate(lines):
            el.append(text(FX + 64, cy - 10 + j * 20, ln,
                           size=13, family=1, w=FW - 80, h=18))
        cy += 22 * len(lines) + 10

    # ---------- Legend (bottom right) ----------
    LX, LY, LW, LH = 1200, 700, 290, 180
    el.append(rect(LX, LY, LW, LH, fill=WHITE))
    el.append(text(LX + 20, LY + 14, "Legend", size=16, family=1, w=180, h=22))
    el.append(arrow([(LX + 30, LY + 64), (LX + 110, LY + 64)]))
    el.append(text(LX + 130, LY + 54, "solid", size=13, family=1, w=80, h=18))
    el.append(text(LX + 130, LY + 74, "sync HTTP",
                   size=12, family=1, color=MUTED, w=200, h=18))
    el.append(arrow([(LX + 30, LY + 114), (LX + 110, LY + 114)], dashed=True))
    el.append(text(LX + 130, LY + 104, "dashed", size=13, family=1, w=80, h=18))
    el.append(text(LX + 130, LY + 124, "async / out of band",
                   size=12, family=1, color=MUTED, w=240, h=18))
    el.append(text(LX + 20, LY + 154, "★", size=14, family=1, color=GOLD, w=16, h=18))
    el.append(text(LX + 40, LY + 154, "source of truth (statements)",
                   size=12, family=1, color=MUTED, w=260, h=18))

    write_scene("fund-transfer-flow.excalidraw", el)


# ====================================================================
# DIAGRAM 3 — Top-up state machine
# ====================================================================
def build_state_machine():
    el = []
    el.append(text(400, 30, "Top-Up State Machine",
                   size=28, family=1, w=700, h=36, align="center"))
    el.append(text(330, 70,
                   "every legal transition for a top_up row in Investment-Wallet",
                   size=14, family=1, color=MUTED2, w=840, h=20, align="center"))

    # ---------- Initial dot ----------
    INIT_X, INIT_Y = 110, 240
    el.append(ellipse(INIT_X, INIT_Y, 12, fill=INK, stroke=INK))
    el.append(text(INIT_X - 30, INIT_Y + 22, "(start)",
                   size=11, family=1, color=MUTED, w=80, h=16, align="center"))

    # ---------- States ----------
    # Non-terminal states: single border, white fill, soft accent header? Keep simple.
    # PENDING (top-left)
    PEND_X, PEND_Y = 220, 200
    el.append(rect(PEND_X, PEND_Y, 200, 90, fill=WHITE))
    el.append(text(PEND_X, PEND_Y + 24, "PENDING", size=18, family=3,
                   color=INK, w=200, h=24, align="center"))
    el.append(text(PEND_X, PEND_Y + 54, "row created, idempotency",
                   size=11, family=1, color=MUTED, w=200, h=14, align="center"))
    el.append(text(PEND_X, PEND_Y + 70, "key claimed", size=11, family=1,
                   color=MUTED, w=200, h=14, align="center"))

    # PROCESSING (mid-left)
    PROC_X, PROC_Y = 220, 460
    el.append(rect(PROC_X, PROC_Y, 200, 90, fill=WHITE))
    el.append(text(PROC_X, PROC_Y + 24, "PROCESSING", size=18, family=3,
                   color=INK, w=200, h=24, align="center"))
    el.append(text(PROC_X, PROC_Y + 54, "PG accepted; awaiting",
                   size=11, family=1, color=MUTED, w=200, h=14, align="center"))
    el.append(text(PROC_X, PROC_Y + 70, "settlement webhook",
                   size=11, family=1, color=MUTED, w=200, h=14, align="center"))

    # PAID (terminal — doubled border, mint tint)
    PAID_X, PAID_Y = 720, 460
    # outer border
    el.append(rect(PAID_X - 6, PAID_Y - 6, 212, 102, fill="transparent", sw=2))
    # inner box (filled)
    el.append(rect(PAID_X, PAID_Y, 200, 90, fill=MINT))
    el.append(text(PAID_X, PAID_Y + 22, "PAID", size=18, family=3,
                   color=INK, w=200, h=24, align="center"))
    el.append(text(PAID_X, PAID_Y + 50, "terminal", size=11, family=1,
                   color=MUTED, w=200, h=14, align="center"))
    el.append(text(PAID_X, PAID_Y + 66, "balance credited",
                   size=11, family=1, color=MUTED, w=200, h=14, align="center"))

    # FAILED (terminal — doubled border, rose tint)
    FAIL_X, FAIL_Y = 720, 200
    el.append(rect(FAIL_X - 6, FAIL_Y - 6, 212, 102, fill="transparent", sw=2))
    el.append(rect(FAIL_X, FAIL_Y, 200, 90, fill=ROSE))
    el.append(text(FAIL_X, FAIL_Y + 22, "FAILED", size=18, family=3,
                   color=INK, w=200, h=24, align="center"))
    el.append(text(FAIL_X, FAIL_Y + 50, "terminal", size=11, family=1,
                   color=MUTED, w=200, h=14, align="center"))
    el.append(text(FAIL_X, FAIL_Y + 66, "no money moved",
                   size=11, family=1, color=MUTED, w=200, h=14, align="center"))

    # ---------- Transitions ----------
    # Initial → PENDING
    el.append(arrow([(122, 240), (220, 240)]))
    el.append(text(125, 215, "create top_up + idem key",
                   size=11, family=3, color=MUTED, w=220, h=14))

    # PENDING → PROCESSING
    el.append(arrow([(320, 290), (320, 460)]))
    el.append(text(330, 360, "PG returns ACCEPTED",
                   size=12, family=1, color=INK, w=200, h=16))
    el.append(text(330, 378, "(provider authorized)",
                   size=11, family=1, color=MUTED, w=200, h=14))

    # PENDING → FAILED
    el.append(arrow([(420, 245), (720, 245)]))
    el.append(text(490, 220, "PG returns REJECTED",
                   size=12, family=1, color=INK, w=240, h=16))
    el.append(text(490, 256, "(provider declined)",
                   size=11, family=1, color=MUTED, w=240, h=14))

    # PROCESSING → PAID
    el.append(arrow([(420, 505), (720, 505)]))
    el.append(text(478, 478, "settlement.completed received",
                   size=12, family=1, color=INK, w=300, h=16))
    el.append(text(478, 514, "(dedup, credit balance)",
                   size=11, family=1, color=MUTED, w=280, h=14))

    # PROCESSING → FAILED  (diagonal up-right)
    el.append(arrow([(420, 470), (560, 410), (650, 350), (720, 295)]))
    el.append(text(560, 380, "settlement timeout /",
                   size=11, family=1, color=MUTED, w=180, h=14))
    el.append(text(560, 396, "explicit failure",
                   size=11, family=1, color=MUTED, w=180, h=14))

    # ---------- SQL guard panel ----------
    GX, GY, GW, GH = 60, 640, 880, 220
    el.append(rect(GX, GY, GW, GH, fill=WHITE))
    el.append(text(GX + 20, GY + 14, "Every transition is guarded in SQL",
                   size=16, family=1, w=600, h=22))
    el.append(text(GX + 20, GY + 38, "If the row is in a different state already, zero rows return → IllegalStateTransition",
                   size=12, family=1, color=MUTED, w=GW - 40, h=18))
    # SQL block
    el.append(rect(GX + 20, GY + 70, GW - 40, 110, fill=CREAM, sw=1))
    sql_lines = [
        "UPDATE top_ups",
        "   SET status = $new",
        " WHERE id = $id",
        "   AND status = $expected",
        "RETURNING id;",
    ]
    for i, ln in enumerate(sql_lines):
        el.append(text(GX + 36, GY + 82 + i * 18, ln,
                       size=13, family=3, color=INK, w=GW - 80, h=18))
    el.append(text(GX + 20, GY + 192, "→ zero rows means: dedup table caught it OR retry-and-no-op. "
                   "Re-applying a settlement to a PAID row is a no-op.",
                   size=12, family=1, color=MUTED2, w=GW - 40, h=18))

    # ---------- Legend ----------
    LX, LY, LW, LH = 980, 640, 460, 220
    el.append(rect(LX, LY, LW, LH, fill=WHITE))
    el.append(text(LX + 20, LY + 14, "Legend",
                   size=16, family=1, w=200, h=22))
    # initial dot
    el.append(ellipse(LX + 36, LY + 60, 8, fill=INK, stroke=INK))
    el.append(text(LX + 60, LY + 52, "initial-state marker",
                   size=12, family=1, w=300, h=18))
    # plain box
    el.append(rect(LX + 24, LY + 84, 28, 22, fill=WHITE))
    el.append(text(LX + 60, LY + 86, "non-terminal state",
                   size=12, family=1, w=300, h=18))
    # doubled box
    el.append(rect(LX + 22, LY + 122, 32, 26, fill="transparent"))
    el.append(rect(LX + 26, LY + 126, 24, 18, fill=MINT))
    el.append(text(LX + 60, LY + 124, "terminal state (doubled border)",
                   size=12, family=1, w=400, h=18))
    el.append(text(LX + 20, LY + 162, "PAID is mint, FAILED is rose — easy color split",
                   size=11, family=1, color=MUTED, w=420, h=18))
    el.append(text(LX + 20, LY + 184, "Guarded UPDATE = second line of defense behind event dedup",
                   size=11, family=1, color=MUTED, w=420, h=18))

    write_scene("top-up-state-machine.excalidraw", el)


# ====================================================================
# DIAGRAM 4 — Top-up architecture & flow
# ====================================================================
def build_top_up():
    el = []
    el.append(text(450, 30, "Top-Up — Architecture & Flow",
                   size=28, family=1, w=600, h=36, align="center"))
    el.append(text(330, 70,
                   "services own their tables; numbered arrows trace one top-up request through the system",
                   size=14, family=1, color=MUTED2, w=840, h=20, align="center"))

    # ---------- Top row: synchronous request chain ----------
    # Client (simple white box)
    el.append(rect(40, 180, 120, 90, fill=WHITE))
    el.append(text(40, 200, "Client", size=16, family=1, w=120, h=22, align="center"))
    el.append(text(40, 226, "mobile / web app",
                   size=12, family=1, color=MUTED2, w=120, h=18, align="center"))

    # Gateway (small card)
    card(el, 200, 160, 160, 130, "Gateway", WHITE,
         name_size=16,
         sections=[("FORWARDS", [
             "POST /top-ups",
             "POST /bank-transfers",
         ])])

    # Investment-Wallet (large teal-headed card)
    card(el, 400, 110, 340, 320, "Investment-Wallet", TEAL,
         sections=[
             ("ENDPOINT", ["POST /top-ups"]),
             ("TABLES", [
                 "wallets, top_ups, fund_transfers",
                 "idempotency_keys, processed_events",
                 "outbox_events",
             ]),
             ("EVENTS", [
                 "↓ consume settlement.completed",
                 "↑ publish top_up.paid",
             ]),
         ])

    # Payment-Gateway (medium blue-headed card)
    card(el, 780, 150, 240, 240, "Payment-Gateway", BLUE,
         sections=[
             ("ENDPOINT", ["POST /charges"]),
             ("TABLES", ["charges, idempotency_keys"]),
             ("CALLS", [("external provider (Moyasar)", False)]),
         ])

    # Provider (mock) — small beige box, no header band
    PR_X, PR_Y = 1080, 190
    el.append(rect(PR_X, PR_Y, 220, 160, fill=BEIGE_L))
    el.append(text(PR_X, PR_Y + 18, "Provider (mock)",
                   size=16, family=1, w=220, h=22, align="center"))
    el.append(text(PR_X, PR_Y + 58, "Moyasar",
                   size=13, family=1, color=MUTED, w=220, h=18, align="center"))
    el.append(text(PR_X, PR_Y + 82, "returns payment_id",
                   size=13, family=1, color=MUTED, w=220, h=18, align="center"))
    el.append(text(PR_X, PR_Y + 106, "fires signed webhook",
                   size=13, family=1, color=MUTED, w=220, h=18, align="center"))

    # ---------- Bottom row: async settlement loop ----------
    # RabbitMQ
    card(el, 540, 620, 260, 200, "RabbitMQ", BEIGE_D,
         sections=[
             ("TOPIC EXCHANGE", ["iron_wallet"]),
             ("QUEUES", [
                 "wallet.settlements",
                 "wallet.settlements.dlq",
             ]),
         ])

    # Omnibus (large gray-headed card with star)
    OB_X, OB_Y, OB_W, OB_H = 900, 600, 340, 320
    el.append(rect(OB_X, OB_Y, OB_W, OB_H, fill=WHITE))
    el.append(rect(OB_X, OB_Y, OB_W, 44, fill=GRAY))
    el.append(text(OB_X, OB_Y + 12, "Omnibus", size=18, family=1,
                   w=OB_W, h=22, align="center"))
    cy = OB_Y + 56
    el.append(text(OB_X + 16, cy, "ENDPOINTS",
                   size=10, family=1, color=MUTED, w=120, h=14))
    el.append(text(OB_X + 16, cy + 18, "POST /webhooks/moyasar",
                   size=12, family=3, w=260, h=16))
    el.append(text(OB_X + 16, cy + 36, "POST /bank-transfers",
                   size=12, family=3, w=260, h=16))
    cy += 64
    el.append(text(OB_X + 16, cy, "TABLES",
                   size=10, family=1, color=MUTED, w=120, h=14))
    el.append(text(OB_X + 16, cy + 18, "statements",
                   size=12, family=3, w=100, h=16))
    el.append(text(OB_X + 108, cy + 16, "★",
                   size=16, family=1, color=GOLD, w=16, h=20))
    el.append(text(OB_X + 130, cy + 18, "source of truth",
                   size=12, family=1, color=MUTED2, w=180, h=16))
    el.append(text(OB_X + 16, cy + 36, "processed_webhooks, outbox_events",
                   size=12, family=3, w=300, h=16))
    el.append(text(OB_X + 16, cy + 54, "idempotency_keys",
                   size=12, family=3, w=200, h=16))
    cy += 82
    el.append(text(OB_X + 16, cy, "EVENTS",
                   size=10, family=1, color=MUTED, w=120, h=14))
    el.append(text(OB_X + 16, cy + 18, "↑ publish settlement.completed",
                   size=12, family=3, w=300, h=16))

    # ---------- Numbered arrows ----------
    # 1. Client → Gateway
    el.append(arrow([(160, 225), (200, 225)]))
    numbered(el, 180, 207, 1)
    # 2. Gateway → IW
    el.append(arrow([(360, 225), (400, 225)]))
    numbered(el, 380, 207, 2)
    # 3. IW → PG
    el.append(arrow([(740, 270), (780, 270)]))
    numbered(el, 760, 252, 3)
    # 4. PG → Provider
    el.append(arrow([(1020, 270), (1080, 270)]))
    numbered(el, 1050, 252, 4)
    # 5. Provider → Omnibus (dashed, sweeps right then back in)
    el.append(arrow(
        [(1190, 350), (1330, 410), (1370, 490), (1300, 570), (1190, 600)],
        dashed=True))
    numbered(el, 1370, 480, 5)
    # 6. Omnibus → RabbitMQ
    el.append(arrow([(900, 720), (800, 720)]))
    numbered(el, 850, 702, 6)
    # 7. RabbitMQ → IW (dashed, sweeps left and up)
    el.append(arrow(
        [(620, 620), (440, 560), (380, 500), (440, 450), (500, 430)],
        dashed=True))
    numbered(el, 380, 525, 7)

    # ---------- Flow steps panel ----------
    FX, FY, FW, FH = 30, 940, 1020, 320
    el.append(rect(FX, FY, FW, FH, fill=WHITE))
    el.append(text(FX + 20, FY + 14, "Flow steps", size=18, family=1, w=200, h=24))

    steps = [
        "Client POSTs /top-ups with Idempotency-Key. Gateway just forwards.",
        "Wallet claims the idempotency key and inserts a top_up row "
        "(status PENDING) — both in one DB transaction.",
        "Wallet calls Payment-Gateway. PG claims its own idem key (derived from "
        "top_up_id), inserts a charge row (status CREATED).",
        "PG forwards to the external provider (Moyasar mocked).",
        "Provider returns payment_id immediately; schedules a signed webhook to "
        "fire later. PG marks charge ACCEPTED and returns to Wallet, which "
        "transitions top_up PENDING → PROCESSING and 200s the client.",
        "Async: provider's signed webhook arrives at Omnibus. Omnibus verifies "
        "HMAC, dedups by event_id, inserts a statement and an outbox_event in "
        "one txn.",
        "Omnibus's outbox publisher drains the row to RabbitMQ as "
        "settlement.completed.",
        "Wallet consumer reads the event, dedups by event_id, transitions "
        "top_up PROCESSING → PAID, credits the wallet balance, and writes its "
        "own outbox event top_up.paid.",
    ]
    cy = FY + 56
    for i, s in enumerate(steps, 1):
        numbered(el, FX + 36, cy, i)
        words = s.split(" ")
        line, lines = "", []
        for w in words:
            if not line:
                line = w
            elif len(line) + 1 + len(w) <= 105:
                line += " " + w
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        for j, ln in enumerate(lines):
            el.append(text(FX + 64, cy - 10 + j * 20, ln,
                           size=13, family=1, w=FW - 80, h=18))
        cy += 22 * len(lines) + 8

    # ---------- Arrow style legend (bottom right) ----------
    LX, LY, LW, LH = 1080, 940, 390, 200
    el.append(rect(LX, LY, LW, LH, fill=WHITE))
    el.append(text(LX + 20, LY + 14, "Arrow style", size=18, family=1, w=200, h=24))
    el.append(arrow([(LX + 30, LY + 64), (LX + 110, LY + 64)]))
    el.append(text(LX + 130, LY + 54, "solid arrow",
                   size=13, family=1, w=140, h=18))
    el.append(text(LX + 130, LY + 74, "synchronous HTTP call",
                   size=12, family=1, color=MUTED, w=240, h=18))
    el.append(arrow([(LX + 30, LY + 114), (LX + 110, LY + 114)], dashed=True))
    el.append(text(LX + 130, LY + 104, "dashed arrow",
                   size=13, family=1, w=140, h=18))
    el.append(text(LX + 130, LY + 124, "asynchronous (webhook / event)",
                   size=12, family=1, color=MUTED, w=260, h=18))
    el.append(text(LX + 20, LY + 160, "★", size=14, family=1, color=GOLD, w=16, h=18))
    el.append(text(LX + 40, LY + 160, "source of truth (statements)",
                   size=12, family=1, color=MUTED, w=300, h=18))

    write_scene("top-up-architecture.excalidraw", el)


# ====================================================================
if __name__ == "__main__":
    print("Building diagrams in", OUT_DIR)
    build_top_up()
    build_architecture()
    build_fund_transfer()
    build_state_machine()
    print("Done.")
