"""
VoodooBot English Platform Logo Generator
Creates 512x512, 256x256, and 200x200 logo variants using PIL/Pillow.
"""

import os
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Ensure assets directory exists
ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(ASSETS_DIR, exist_ok=True)

# ── Color palette ──────────────────────────────────────────────────────────────
BG_TOP       = (13,   0,  21)   # #0D0015 — near-black purple
BG_BOTTOM    = (26,   0,  48)   # #1A0030 — deep purple
GLOW_OUTER   = (60,   0, 120)   # dim purple ring
GLOW_MID     = (102,  51, 204)  # #6633CC
GLOW_CORE    = (153,  51, 255)  # #9933FF
STAR_COLOR   = (200, 160, 255)  # soft lavender sparkle
TEXT_MAIN    = (255, 255, 255)  # white
TEXT_ENGLISH = (180, 100, 255)  # purple/violet
TEXT_OUTLINE = (120,  40, 200)  # darker purple outline


# ── Utility helpers ────────────────────────────────────────────────────────────

def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def vertical_gradient(draw, width, height, top_color, bottom_color):
    """Fill rectangle with a top-to-bottom linear gradient."""
    for y in range(height):
        t = y / (height - 1)
        color = lerp_color(top_color, bottom_color, t)
        draw.line([(0, y), (width, y)], fill=color)


def radial_glow(img, cx, cy, radius, color, alpha_max=180, steps=60):
    """Paint a radial glow by stacking alpha-blended filled circles."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(steps, 0, -1):
        r = int(radius * i / steps)
        a = int(alpha_max * (1 - i / steps) ** 1.5)
        d.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(*color, a),
        )
    img.alpha_composite(overlay)


def draw_circle_outline(draw, cx, cy, r, color, width=2):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=width)


def draw_star(draw, cx, cy, r_outer, r_inner, points, color, rotation=0):
    """Draw a multi-point star polygon."""
    verts = []
    for i in range(points * 2):
        angle = math.radians(rotation + i * 180 / points - 90)
        r = r_outer if i % 2 == 0 else r_inner
        verts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(verts, fill=color)


def draw_sparkle(draw, cx, cy, size, color):
    """Simple 4-point diamond sparkle."""
    pts = [
        (cx,          cy - size),
        (cx + size//4, cy),
        (cx,          cy + size),
        (cx - size//4, cy),
    ]
    draw.polygon(pts, fill=color)


def draw_text_with_outline(draw, x, y, text, font, fill, outline, outline_width=3, anchor="mm"):
    """Draw text with a coloured outline by rendering offset copies first."""
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=outline, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


def draw_voodoo_doll(img_rgba, cx, cy, scale=1.0):
    """
    Draw a minimal mystical voodoo-doll / skull shape using simple PIL shapes.
    The doll is fully made of ellipses and rectangles — no external assets.
    """
    d = ImageDraw.Draw(img_rgba)
    s = scale

    # ── Skull ─────────────────────────────────────────────────────────────────
    skull_rx, skull_ry = int(28 * s), int(32 * s)
    # Outer glow
    for expand in [14, 10, 6]:
        glow_alpha = 60 + (14 - expand) * 8
        d.ellipse(
            [cx - skull_rx - expand, cy - skull_ry - expand,
             cx + skull_rx + expand, cy + skull_ry + expand],
            fill=(*GLOW_MID, glow_alpha),
        )
    # Main skull shape (head)
    d.ellipse(
        [cx - skull_rx, cy - skull_ry, cx + skull_rx, cy + skull_ry],
        fill=(240, 230, 255),
    )
    # Jaw / lower face flat bottom
    jaw_top = cy + int(14 * s)
    jaw_h   = int(14 * s)
    jaw_w   = int(22 * s)
    d.rectangle(
        [cx - jaw_w, jaw_top, cx + jaw_w, jaw_top + jaw_h],
        fill=(200, 185, 240),
    )

    # Eye sockets (dark ellipses)
    eye_y  = cy - int(8 * s)
    eye_ox = int(11 * s)
    eye_rx, eye_ry = int(8 * s), int(9 * s)
    for ex in [-eye_ox, eye_ox]:
        # glow behind eye
        d.ellipse(
            [cx + ex - eye_rx - 3, eye_y - eye_ry - 3,
             cx + ex + eye_rx + 3, eye_y + eye_ry + 3],
            fill=(*GLOW_CORE, 120),
        )
        d.ellipse(
            [cx + ex - eye_rx, eye_y - eye_ry,
             cx + ex + eye_rx, eye_y + eye_ry],
            fill=(*GLOW_CORE, 220),
        )
        # tiny pupil glint
        d.ellipse(
            [cx + ex - 3, eye_y - 3, cx + ex + 3, eye_y + 3],
            fill=(255, 255, 255, 180),
        )

    # Nose socket
    nose_y = cy + int(6 * s)
    d.ellipse(
        [cx - int(5 * s), nose_y - int(5 * s),
         cx + int(5 * s), nose_y + int(5 * s)],
        fill=(160, 120, 210, 200),
    )

    # Teeth marks
    teeth_y = jaw_top + int(4 * s)
    for tx in range(-2, 3):
        tx_px = cx + tx * int(7 * s)
        d.rectangle(
            [tx_px - int(2 * s), teeth_y,
             tx_px + int(2 * s), teeth_y + int(7 * s)],
            fill=(120, 90, 180),
        )

    # ── Body (simple rounded rectangle) ───────────────────────────────────────
    body_top  = jaw_top + jaw_h + int(4 * s)
    body_bot  = body_top + int(38 * s)
    body_w    = int(18 * s)
    d.rounded_rectangle(
        [cx - body_w, body_top, cx + body_w, body_bot],
        radius=int(8 * s),
        fill=(200, 185, 240),
        outline=(*GLOW_MID, 200),
        width=2,
    )

    # Cross stitch / X marks on body
    stitch_y = body_top + int(14 * s)
    stitch_r = int(5 * s)
    d.line([(cx - stitch_r, stitch_y - stitch_r),
            (cx + stitch_r, stitch_y + stitch_r)], fill=(*GLOW_CORE, 255), width=2)
    d.line([(cx + stitch_r, stitch_y - stitch_r),
            (cx - stitch_r, stitch_y + stitch_r)], fill=(*GLOW_CORE, 255), width=2)

    # ── Arms ──────────────────────────────────────────────────────────────────
    arm_y   = body_top + int(10 * s)
    arm_len = int(24 * s)
    arm_h   = int(10 * s)
    for side in [-1, 1]:
        arm_x_start = cx + side * body_w
        arm_x_end   = arm_x_start + side * arm_len
        d.rounded_rectangle(
            [min(arm_x_start, arm_x_end), arm_y - arm_h // 2,
             max(arm_x_start, arm_x_end), arm_y + arm_h // 2],
            radius=int(4 * s),
            fill=(200, 185, 240),
        )

    # ── Legs ──────────────────────────────────────────────────────────────────
    leg_top = body_bot - int(6 * s)
    leg_w   = int(8 * s)
    leg_h   = int(22 * s)
    leg_gap = int(5 * s)
    for side in [-1, 1]:
        lx = cx + side * (leg_w // 2 + leg_gap // 2)
        d.rounded_rectangle(
            [lx - leg_w // 2, leg_top,
             lx + leg_w // 2, leg_top + leg_h],
            radius=int(5 * s),
            fill=(200, 185, 240),
        )

    # ── Top pin / needle ──────────────────────────────────────────────────────
    pin_tip_y  = cy - skull_ry - int(22 * s)
    pin_base_y = cy - skull_ry - int(2 * s)
    d.line([(cx, pin_tip_y), (cx, pin_base_y)], fill=(255, 220, 80), width=int(3 * s))
    # pin head (small circle)
    pin_r = int(5 * s)
    d.ellipse(
        [cx - pin_r, pin_tip_y - pin_r, cx + pin_r, pin_tip_y + pin_r],
        fill=(255, 220, 80),
    )
    # pin glow
    d.ellipse(
        [cx - pin_r - 4, pin_tip_y - pin_r - 4,
         cx + pin_r + 4, pin_tip_y + pin_r + 4],
        outline=(255, 200, 0, 160), width=2,
    )


# ── Core logo composer ─────────────────────────────────────────────────────────

def make_logo(size: int) -> Image.Image:
    W = H = size
    scale = size / 512  # relative to the canonical 512 px design

    # Start with RGBA so we can use alpha blending for glows
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # 1. Background gradient
    vertical_gradient(draw, W, H, BG_TOP, BG_BOTTOM)

    # 2. Central radial glow (behind everything)
    cx, cy = W // 2, H // 2
    radial_glow(img, cx, int(cy * 0.55), int(120 * scale), GLOW_MID,  alpha_max=120)
    radial_glow(img, cx, int(cy * 0.55), int( 60 * scale), GLOW_CORE, alpha_max=100)

    # 3. Decorative concentric mystic circles
    draw = ImageDraw.Draw(img)
    for i, (r, alpha) in enumerate([(230, 30), (190, 40), (155, 55), (120, 70)]):
        r = int(r * scale)
        a = alpha
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.ellipse([cx - r, cy - r, cx + r, cy + r],
                   outline=(*GLOW_MID, a), width=max(1, int(2 * scale)))
        img.alpha_composite(overlay)

    draw = ImageDraw.Draw(img)

    # 4. Sparkle / star field
    rng = random.Random(42)
    sparkle_positions = [
        (int(W * 0.12), int(H * 0.15)),
        (int(W * 0.85), int(H * 0.12)),
        (int(W * 0.08), int(H * 0.72)),
        (int(W * 0.90), int(H * 0.78)),
        (int(W * 0.20), int(H * 0.88)),
        (int(W * 0.78), int(H * 0.88)),
        (int(W * 0.50), int(H * 0.08)),
        (int(W * 0.35), int(H * 0.92)),
        (int(W * 0.65), int(H * 0.10)),
        (int(W * 0.15), int(H * 0.45)),
        (int(W * 0.87), int(H * 0.48)),
    ]
    for (sx, sy) in sparkle_positions:
        sz = rng.randint(int(4 * scale), int(10 * scale))
        alpha = rng.randint(120, 220)
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        draw_star(od, sx, sy, sz, sz // 3, 4, (*STAR_COLOR, alpha), rotation=rng.uniform(0, 45))
        img.alpha_composite(overlay)

    draw = ImageDraw.Draw(img)

    # 5. Voodoo doll icon (upper centre)
    doll_cx = cx
    doll_cy = int(H * 0.27)
    draw_voodoo_doll(img, doll_cx, doll_cy, scale=scale * 0.95)

    draw = ImageDraw.Draw(img)

    # 6. Text — "VOODOO"
    #    Try to load a bold system font; fall back to default.
    font_voodoo = None
    font_english = None
    candidate_fonts = [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    voodoo_size  = int(96 * scale)
    english_size = int(36 * scale)
    for path in candidate_fonts:
        if os.path.exists(path):
            try:
                font_voodoo  = ImageFont.truetype(path, voodoo_size)
                font_english = ImageFont.truetype(path, english_size)
                break
            except Exception:
                continue

    if font_voodoo is None:
        font_voodoo  = ImageFont.load_default()
        font_english = ImageFont.load_default()

    text_y_voodoo  = int(H * 0.665)
    text_y_english = int(H * 0.800)

    # Glow behind "VOODOO" text
    radial_glow(img, cx, text_y_voodoo, int(140 * scale), GLOW_MID,  alpha_max=80)
    radial_glow(img, cx, text_y_voodoo, int( 70 * scale), GLOW_CORE, alpha_max=60)

    draw = ImageDraw.Draw(img)
    outline_px = max(2, int(4 * scale))
    draw_text_with_outline(draw, cx, text_y_voodoo, "VOODOO",
                           font_voodoo, TEXT_MAIN, TEXT_OUTLINE,
                           outline_width=outline_px)

    # Decorative line under VOODOO
    line_half = int(110 * scale)
    line_y    = text_y_voodoo + int(52 * scale)
    draw.line([(cx - line_half, line_y), (cx + line_half, line_y)],
              fill=(*GLOW_CORE, 200), width=max(1, int(2 * scale)))

    # Small diamonds at line ends
    for lx in [cx - line_half, cx + line_half]:
        draw_sparkle(draw, lx, line_y, int(7 * scale), (*GLOW_CORE, 220))

    # "ENGLISH"
    draw_text_with_outline(draw, cx, text_y_english, "ENGLISH",
                           font_english, TEXT_ENGLISH, TEXT_OUTLINE,
                           outline_width=max(1, int(2 * scale)))

    # Thin border frame
    border_inset = int(10 * scale)
    draw.rounded_rectangle(
        [border_inset, border_inset, W - border_inset, H - border_inset],
        radius=int(28 * scale),
        outline=(*GLOW_MID, 100),
        width=max(1, int(2 * scale)),
    )

    # Convert to RGB for final PNG (no transparency needed at top level)
    final = Image.new("RGB", (W, H), (0, 0, 0))
    final.paste(img.convert("RGB"))
    return final


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    sizes = [
        (512, "voodoo_logo.png"),
        (256, "voodoo_logo_256.png"),
        (200, "voodoo_avatar.png"),
    ]
    for size, filename in sizes:
        print(f"Generating {filename} ({size}x{size})…")
        img = make_logo(size)
        out_path = os.path.join(ASSETS_DIR, filename)
        img.save(out_path, "PNG", optimize=True)
        print(f"  Saved → {out_path}")
    print("Done.")


if __name__ == "__main__":
    main()
