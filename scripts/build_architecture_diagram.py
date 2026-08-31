#!/usr/bin/env python3
"""Render the Devpost architecture diagram for The Universal Bounty Fleet (Engine V2)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 2800, 1936
BG = (12, 10, 9)
SURFACE = (28, 25, 23)
SURFACE2 = (36, 32, 30)
BORDER = (41, 37, 36)
INK = (250, 250, 249)
MUTED = (120, 113, 108)
VOLT = (192, 255, 112)
DANGER = (225, 29, 46)
PENDING = (232, 195, 106)
DEEP = (5, 4, 3)

OUT = Path(__file__).resolve().parents[1] / "docs" / "Universal_Bounty_Fleet_Architecture.png"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        ("/System/Library/Fonts/HelveticaNeue.ttc", 0 if not bold else 1),
        (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
            if bold
            else "/System/Library/Fonts/Supplemental/Arial.ttf",
            None,
        ),
    )
    for path, index in candidates:
        try:
            if index is None:
                return ImageFont.truetype(path, size)
            return ImageFont.truetype(path, size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def mono(size: int) -> ImageFont.FreeTypeFont:
    for path in ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Supplemental/Courier New.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return font(size)


F_KICK = mono(20)
F_TITLE = font(50, bold=True)
F_SUB = font(22)
F_GEAP = mono(16)
F_H1 = font(24, bold=True)
F_H2 = font(20, bold=True)
F_BODY = font(18)
F_TINY = font(16)
F_FOOT = mono(16)


def rr(draw, box, fill, outline=None, radius=16, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, s, fnt, fill=INK, anchor="lt"):
    draw.text(xy, s, font=fnt, fill=fill, anchor=anchor)


def center_text(draw, cx, y, s, fnt, fill=INK):
    text(draw, (cx, y), s, fnt, fill=fill, anchor="mt")


def arrow_down(draw, x, y0, y1):
    draw.line((x, y0, x, y1 - 12), fill=VOLT, width=3)
    draw.polygon([(x, y1), (x - 7, y1 - 14), (x + 7, y1 - 14)], fill=VOLT)


def arrow_right(draw, x0, x1, y):
    draw.line((x0, y, x1 - 12, y), fill=VOLT, width=3)
    draw.polygon([(x1, y), (x1 - 14, y - 7), (x1 - 14, y + 7)], fill=VOLT)


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, W, 168), fill=DEEP)
    draw.rectangle((0, 168, W, 172), fill=VOLT)
    text(draw, (64, 32), "FORTIFIED ENTERPRISE FLEET  ·  ENGINE V2", F_KICK, VOLT)
    text(draw, (64, 68), "The Universal Bounty Fleet", F_TITLE, INK)
    text(
        draw,
        (64, 126),
        "Cloud Run gateway  +  Hourly Sweeper  ·  Gemini / Vertex  ·  Firestore  ·  OrbStack  ·  GitHub stigmergy",
        F_SUB,
        MUTED,
    )
    text(draw, (W - 64, 84), "odin-500008  ·  us-central1", F_GEAP, MUTED, anchor="rt")

    # Sources
    src_y, src_h = 196, 118
    left_w = 1320
    gap = 36
    rr(draw, (64, src_y, 64 + left_w, src_y + src_h), SURFACE, BORDER)
    text(draw, (88, src_y + 18), "NATIVE CONTROL PLANE", F_GEAP, MUTED)
    text(draw, (88, src_y + 48), "GitHub", F_H1, INK)
    text(
        draw,
        (88, src_y + 82),
        "Issues  ·  GraphQL bounty search  ·  /try  ·  Draft PRs  ·  Reviews  ·  Humans hold merge",
        F_BODY,
        MUTED,
    )

    rr(draw, (64 + left_w + gap, src_y, 2736, src_y + src_h), SURFACE, BORDER)
    text(draw, (64 + left_w + gap + 24, src_y + 18), "MAINTAINER FEEDBACK", F_GEAP, MUTED)
    text(draw, (64 + left_w + gap + 24, src_y + 48), "Gmail IMAP inbox", F_H1, INK)
    text(
        draw,
        (64 + left_w + gap + 24, src_y + 82),
        "UNSEEN CI / review mail  ·  correlated to open PRs in bounty_memory",
        F_BODY,
        MUTED,
    )

    arrow_down(draw, 64 + left_w // 2, src_y + src_h, 346)
    arrow_down(draw, 64 + left_w + gap + 668, src_y + src_h, 346)

    # Two planes
    plane_y, plane_h = 350, 720
    left_x = 64
    right_x = 64 + left_w + gap
    right_w = 2736 - right_x

    rr(draw, (left_x, plane_y, left_x + left_w, plane_y + plane_h), SURFACE, VOLT, width=2)
    text(draw, (left_x + 24, plane_y + 18), "AGENT GATEWAY  ·  AGENT RUNTIME", F_GEAP, VOLT)
    text(draw, (left_x + 24, plane_y + 48), "Cloud Run  ·  bounty-fleet-gateway", F_H1, INK)
    text(
        draw,
        (left_x + 24, plane_y + 86),
        "Stateless FastAPI  ·  HMAC-SHA256  ·  Firestore delivery-id lock",
        F_BODY,
        INK,
    )
    text(
        draw,
        (left_x + 24, plane_y + 114),
        "issues → Intake    pull_request → Victory Auditor",
        F_BODY,
        MUTED,
    )
    text(
        draw,
        (left_x + 24, plane_y + 144),
        "bounty-fleet-gateway-113376683730.us-central1.run.app",
        F_GEAP,
        MUTED,
    )

    # Three scoped agents inside gateway
    inner_y = plane_y + 186
    inner_h = 210
    inner_gap = 16
    inner_w = (left_w - 48 - 2 * inner_gap) // 3
    agents = [
        ("INTAKE", VOLT, ["issues:comment", "Sniper + escrow", "Stake /try"]),
        ("EXECUTOR", PENDING, ["contents:write", "Draft PR save-state", "Never merges"]),
        ("AUDITOR", DANGER, ["reviews only", "Cannot write code", "Fail-closed gate"]),
    ]
    for i, (name, accent, lines) in enumerate(agents):
        x = left_x + 24 + i * (inner_w + inner_gap)
        rr(draw, (x, inner_y, x + inner_w, inner_y + inner_h), SURFACE2, BORDER, radius=14)
        draw.rounded_rectangle((x, inner_y, x + 8, inner_y + inner_h), radius=4, fill=accent)
        text(draw, (x + 20, inner_y + 18), name, F_H2, accent)
        yy = inner_y + 58
        for line in lines:
            text(draw, (x + 20, yy), line, F_BODY, INK)
            yy += 36

    rr(draw, (left_x + 24, inner_y + inner_h + 24, left_x + left_w - 24, plane_y + plane_h - 24), SURFACE2, BORDER)
    text(draw, (left_x + 48, inner_y + inner_h + 42), "MODEL ARMOR ANALOG  ·  3-PILLAR MURDER BOARD", F_GEAP, DANGER)
    text(draw, (left_x + 48, inner_y + inner_h + 78), "1  Crypto integrity — no mock BLS / dummy proofs", F_BODY, INK)
    text(draw, (left_x + 48, inner_y + inner_h + 110), "2  Authorization — no commented-out require_auth()", F_BODY, INK)
    text(draw, (left_x + 48, inner_y + inner_h + 142), "3  Assertions — no skipped or assert True tests", F_BODY, INK)
    text(
        draw,
        (left_x + 48, inner_y + inner_h + 180),
        "Gemini structured audit on Vertex. Static AND semantic must pass.",
        F_TINY,
        MUTED,
    )

    # Right plane — V2 sweeper
    rr(draw, (right_x, plane_y, right_x + right_w, plane_y + plane_h), SURFACE, VOLT, width=2)
    text(draw, (right_x + 24, plane_y + 18), "AGENT RUNTIME  ·  ENGINE V2", F_GEAP, VOLT)
    text(draw, (right_x + 24, plane_y + 48), "Hourly Sweeper  ·  bounty sweep", F_H1, INK)
    text(
        draw,
        (right_x + 24, plane_y + 86),
        "Monolithic 6-phase pipeline. Max 4 concurrent leads. Max 1 per repo.",
        F_BODY,
        INK,
    )
    text(
        draw,
        (right_x + 24, plane_y + 114),
        "Strategies: orbstack_container  ·  teamwork_swarm  ·  hybrid",
        F_BODY,
        MUTED,
    )

    phases = [
        ("0", "PRE GC"),
        ("1", "INBOX"),
        ("2", "ESCORT"),
        ("3", "SYNC"),
        ("4", "INTAKE"),
        ("5", "EXEC"),
        ("6", "POST GC"),
    ]
    phase_y = plane_y + 160
    phase_h = 88
    phase_gap = 8
    phase_w = (right_w - 48 - 6 * phase_gap) // 7
    for i, (num, name) in enumerate(phases):
        x = right_x + 24 + i * (phase_w + phase_gap)
        accent = VOLT if name in ("INTAKE", "EXEC") else PENDING if name in ("INBOX", "ESCORT", "SYNC") else MUTED
        rr(draw, (x, phase_y, x + phase_w, phase_y + phase_h), SURFACE2, accent, radius=12, width=1)
        center_text(draw, x + phase_w // 2, phase_y + 18, num, F_GEAP, MUTED)
        center_text(draw, x + phase_w // 2, phase_y + 46, name, F_TINY, INK)

    engine_y = phase_y + phase_h + 28
    engines = [
        ("InboxEngine", "IMAP UNSEEN mail → PR flags"),
        ("EscortEngine", "CI rollups, skip Vercel/Netlify, 14-day stall"),
        ("SyncEngine", "Merged PRs → bounty_settlements ledger"),
        ("IntakeEngine", "GraphQL GrantFox / Stellar / EVM + Sniper"),
        ("ExecutorEngine", "OrbStack --rm sandbox, PathGuard, draft PR"),
    ]
    ey = engine_y
    for title, body in engines:
        rr(draw, (right_x + 24, ey, right_x + right_w - 24, ey + 62), SURFACE2, BORDER, radius=12)
        text(draw, (right_x + 44, ey + 10), title, F_H2, VOLT)
        text(draw, (right_x + 44, ey + 36), body, F_TINY, INK)
        ey += 70

    text(
        draw,
        (right_x + 24, plane_y + plane_h - 36),
        "PathGuard blocks keeper_daemon / odin / matt-berserker. Postflight GC always runs.",
        F_TINY,
        MUTED,
    )

    # Shared memory
    mem_y, mem_h = 1106, 150
    arrow_down(draw, left_x + left_w // 2, plane_y + plane_h, mem_y)
    arrow_down(draw, right_x + right_w // 2, plane_y + plane_h, mem_y)
    draw.line((left_x + left_w // 2, mem_y - 12, right_x + right_w // 2, mem_y - 12), fill=VOLT, width=3)

    rr(draw, (64, mem_y, 2736, mem_y + mem_h), SURFACE, VOLT, width=2)
    text(draw, (88, mem_y + 18), "MEMORY BANK", F_GEAP, VOLT)
    text(draw, (88, mem_y + 48), "Firestore  ·  shared across Gateway + V2 Sweeper", F_H1, INK)
    text(
        draw,
        (88, mem_y + 86),
        "bounty_memory/{id}   bounty_leads   bounty_settlements   swarm_coordinator/state   swarm_operations",
        F_BODY,
        INK,
    )
    text(
        draw,
        (88, mem_y + 116),
        "merge_allowed = (auditor APPROVE)  AND  NOT cheat_detected     ·     JSONL fallback when offline",
        F_TINY,
        MUTED,
    )

    arrow_down(draw, W // 2, mem_y + mem_h, 1292)

    # Console + payouts
    con_y, con_h = 1296, 140
    rr(draw, (64, con_y, 1760, con_y + con_h), SURFACE, BORDER)
    text(draw, (88, con_y + 16), "OBSERVABILITY  ·  THE CAMERA", F_GEAP, VOLT)
    text(draw, (88, con_y + 48), "/console  live board", F_H1, INK)
    text(
        draw,
        (88, con_y + 86),
        "PENDING / BLOCKED / CLEARED   ·   /ops  /history  /claims  /archive",
        F_BODY,
        INK,
    )
    text(
        draw,
        (88, con_y + 114),
        "Served from Cloud Run  or  bounty console  against the same Memory Bank",
        F_TINY,
        MUTED,
    )

    rr(draw, (1796, con_y, 2736, con_y + con_h), SURFACE, BORDER)
    text(draw, (1820, con_y + 16), "PAYOUT ROUTING", F_GEAP, VOLT)
    text(draw, (1820, con_y + 48), "EVM + Stellar + Solana", F_H1, INK)
    text(draw, (1820, con_y + 86), "Stamped on every /try and draft PR", F_BODY, INK)
    text(draw, (1820, con_y + 114), "No god-token. Auditor cannot write contents.", F_TINY, MUTED)

    arrow_down(draw, W // 2, con_y + con_h, 1472)

    # Identity / isolation strip
    iso_y, iso_h = 1476, 132
    boxes = [
        ("IDENTITY", "Per-agent GitHub scopes. Auditor reviews only."),
        ("PATHGUARD", "Non-bypassable sandbox. No symlink / firmlink escape."),
        ("ORBSTACK", "Ephemeral --rm containers. CPU / RAM / PID / 300s TTL."),
        ("COORDINATOR", "swarm_coordinator/state after every sweep."),
    ]
    box_w = (2672 - 3 * 24) // 4
    for i, (title, body) in enumerate(boxes):
        x = 64 + i * (box_w + 24)
        rr(draw, (x, iso_y, x + box_w, iso_y + iso_h), SURFACE, BORDER)
        text(draw, (x + 20, iso_y + 18), title, F_GEAP, VOLT)
        text(draw, (x + 20, iso_y + 56), body, F_BODY, INK)

    draw.rectangle((0, 1668, W, H), fill=DEEP)
    labels = [
        "REGISTRY",
        "GATEWAY",
        "RUNTIME",
        "MEMORY BANK",
        "IDENTITY",
        "MODEL ARMOR",
        "OBSERVABILITY",
    ]
    slot = W // len(labels)
    for i, label in enumerate(labels):
        cx = slot * i + slot // 2
        pill_w, pill_h = 210, 34
        rr(draw, (cx - pill_w // 2, 1710, cx + pill_w // 2, 1710 + pill_h), SURFACE2, VOLT, radius=17, width=1)
        center_text(draw, cx, 1727, label, F_GEAP, VOLT)

    text(
        draw,
        (W // 2, 1800),
        "universal_bounty_fleet  (Cloud Run camera)   +   universal_bounty_v2  (Hourly Sweeper / OrbStack)",
        F_FOOT,
        MUTED,
        anchor="mm",
    )
    text(
        draw,
        (W // 2, 1848),
        "ALL THINGS AGENTIC  ·  NO GOD-TOKEN  ·  HUMANS HOLD MERGE",
        F_FOOT,
        MUTED,
        anchor="mm",
    )
    text(
        draw,
        (W // 2, 1900),
        "CLI  bounty sweep | intake | exec | escort | sync | inbox | status | console",
        F_FOOT,
        VOLT,
        anchor="mm",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(OUT)


if __name__ == "__main__":
    main()
