"""Render on-screen text (TikTok / Reels caption style) as a transparent PNG.

The PNG is laid over every frame of the clip, so the text can never move,
flicker or fade. Text fill and outline are fully opaque; only the soft drop
shadow behind the letters is partly transparent (as in native TikTok text).
"""
from __future__ import annotations

import colorsys
import os
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
OUTLINE = (12, 12, 12, 255)

# Font families modelled on the reference screenshots.
FAMILIES = {
    # TikTok "Classic": white text, thin dark outline, soft shadow.
    "classic": dict(head=("TikTokSans-Bold.ttf", 84), body=("TikTokSans-SemiBold.ttf", 50),
                    cta=("TikTokSans-SemiBold.ttf", 43), upper=False, stroke=0.075),
    # Tall condensed headline + body ("Nobody Believes..." / "Life hacks from...").
    "condensed": dict(head=("LeagueGothic-Regular.ttf", 120), body=("LeagueGothic-Regular.ttf", 78),
                      cta=("LeagueGothic-Regular.ttf", 64), upper=False, stroke=0.06, max_width=0.62),
    # Heavy Impact-style headline over classic body text.
    "impact": dict(head=("Anton-Regular.ttf", 94), body=("TikTokSans-SemiBold.ttf", 50),
                   cta=("TikTokSans-SemiBold.ttf", 43), upper=False, stroke=0.07),
    # All caps Montserrat ("I STOPPED DOING THESE 5 THINGS...").
    "caps": dict(head=("Montserrat-ExtraBold.ttf", 74), body=("Montserrat-Bold.ttf", 42),
                 cta=("Montserrat-Bold.ttf", 37), upper=True, stroke=0.07),
}
FALLBACK_FONT = "TikTokSans-Bold.ttf"  # for glyphs a family lacks (e.g. the ↓ arrow)

PALETTE = {
    "white": (255, 255, 255),
    "cream": (255, 243, 218),
    "butter": (255, 222, 89),
    "blush": (255, 186, 206),
    "peach": (255, 196, 150),
    "sky": (160, 212, 255),
    "mint": (164, 240, 198),
    "lilac": (212, 192, 255),
    "gold": (245, 198, 105),
}


@dataclass
class Hook:
    headline: str
    body: str            # may contain "\n" (line break) or "\n\n" (paragraph gap)
    cta: str = ""


@dataclass
class TextStyle:
    family: str = "classic"
    scale: float = 1.0
    head_color: str = "white"
    body_color: str = "white"
    cta_label: bool = False        # CTA in a solid white box (like "Here's what I do instead ↓")
    max_width: float = 0.0         # fraction of frame width (0 = family default)


@dataclass
class Block:
    img: Image.Image               # tight RGBA crop of the text block
    w: int
    h: int
    meta: dict = field(default_factory=dict)


_font_cache: dict = {}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    key = (name, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    return _font_cache[key]


_cmaps: dict = {}


def _has_glyph(f: ImageFont.FreeTypeFont, ch: str) -> bool:
    """True if the font really contains the character (missing ones would draw as a box)."""
    path = f.path
    if path not in _cmaps:
        from fontTools.ttLib import TTFont
        _cmaps[path] = set(TTFont(path).getBestCmap())
    return ord(ch) in _cmaps[path]


def _runs(text: str, f: ImageFont.FreeTypeFont, fb: ImageFont.FreeTypeFont):
    """Split text into (font, chunk) runs, using the fallback for missing glyphs."""
    runs = []
    for ch in text:
        use = f if (ch.isspace() or _has_glyph(f, ch)) else fb
        if runs and runs[-1][0] is use:
            runs[-1][1] += ch
        else:
            runs.append([use, ch])
    return runs


def _line_width(text, f, fb, stroke):
    return sum(r[0].getlength(r[1]) for r in _runs(text, f, fb)) + 2 * stroke


def _wrap(text: str, f, fb, stroke, max_w: float) -> list[str]:
    """Greedy wrap, then re-balance so lines are similar lengths (like the references)."""
    out = []
    for para_line in text.split("\n"):
        words = para_line.split()
        if not words:
            out.append("")
            continue
        lines = _greedy(words, f, fb, stroke, max_w)
        if len(lines) > 1:  # balance: shrink width while line count stays the same
            lo, hi = max_w * 0.45, max_w
            for _ in range(12):
                mid = (lo + hi) / 2
                if len(_greedy(words, f, fb, stroke, mid)) > len(lines):
                    lo = mid
                else:
                    hi = mid
            lines = _greedy(words, f, fb, stroke, hi)
        out += lines
    return out


def _greedy(words, f, fb, stroke, max_w):
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if cur and _line_width(t, f, fb, stroke) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def render_block(hook: Hook, style: TextStyle) -> Block:
    fam = FAMILIES[style.family]
    s = style.scale
    max_w = W * (style.max_width or fam.get("max_width", 0.78))
    rows = []  # (kind, text, font, fallback, stroke, color)

    def add(kind, text, spec, color):
        name, base = spec
        if fam["upper"]:
            text = text.upper()
        size = max(10, round(base * s))
        limit = min(max_w * 1.10, W * 0.82) if kind == "head" else max_w  # keep clear of the screen edges
        while True:
            f = font(name, size)
            fb = font(FALLBACK_FONT, round(size * (0.82 if style.family == "condensed" else 0.95)))
            stroke = max(2, round(size * fam["stroke"]))
            lines = _wrap(text, f, fb, stroke, limit)
            if kind != "head" or len(lines) == 1 or size <= round(base * s * 0.84):
                break
            size -= 2  # headlines read best on one line: shrink a little before wrapping
        for line in lines:
            rows.append((kind, line, f, fb, stroke, color))

    head_rgb = PALETTE[style.head_color]
    body_rgb = PALETTE[style.body_color]
    if hook.headline:
        add("head", hook.headline, fam["head"], head_rgb)
    if hook.body:
        add("body", hook.body, fam["body"], body_rgb)
    if hook.cta:
        add("cta", hook.cta, fam["cta"], body_rgb)

    # Vertical layout.
    pad = 40  # room for outline + shadow around the block
    layout = []
    y = pad
    prev = None
    for kind, text, f, fb, stroke, color in rows:
        asc, desc = f.getmetrics()
        lh = round((asc + desc) * (1.02 if fam is FAMILIES["condensed"] else 1.10))
        if prev and prev != kind:
            y += round(f.size * (0.30 if kind == "body" else 0.55))
        if text == "":
            y += round(lh * 0.45)
            prev = kind
            continue
        is_label = kind == "cta" and style.cta_label
        box_pad = (round(f.size * 0.42), round(f.size * 0.22)) if is_label else (0, 0)
        width = _line_width(text, f, fb, 0 if is_label else stroke) + 2 * box_pad[0]
        layout.append(dict(kind=kind, text=text, f=f, fb=fb, stroke=stroke, color=color,
                           y=y + box_pad[1], lh=lh, w=width, label=is_label, box_pad=box_pad))
        y += lh + 2 * box_pad[1]
        prev = kind
    block_h = y + pad
    block_w = int(max(r["w"] for r in layout) + 2 * pad)

    text_layer = Image.new("RGBA", (block_w, block_h), (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", (block_w, block_h), (0, 0, 0, 0))
    dt, ds = ImageDraw.Draw(text_layer), ImageDraw.Draw(shadow_layer)
    cx = block_w / 2
    for r in layout:
        f, fb, text = r["f"], r["fb"], r["text"]
        asc = f.getmetrics()[0]
        base_y = r["y"] + asc
        if r["label"]:
            bw = r["w"]
            x0 = cx - bw / 2
            bpx, bpy = r["box_pad"]
            dt.rounded_rectangle([x0, r["y"] - bpy, x0 + bw, r["y"] + r["lh"] + bpy - round(r["lh"] * 0.08)],
                                 radius=round(f.size * 0.18), fill=(255, 255, 255, 255))
            _draw_runs(dt, x0 + bpx, base_y, text, f, fb, (17, 17, 17, 255), 0, None)
            continue
        x0 = cx - (r["w"] - 2 * r["stroke"]) / 2
        _draw_runs(ds, x0, base_y + max(2, round(f.size * 0.05)), text, f, fb, (0, 0, 0, 170), r["stroke"], (0, 0, 0, 170))
        _draw_runs(dt, x0, base_y, text, f, fb, (*r["color"], 255), r["stroke"], OUTLINE)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(max(3, round(6 * s))))
    img = Image.alpha_composite(shadow_layer, text_layer)
    bbox = img.getbbox() or (0, 0, block_w, block_h)
    img = img.crop(bbox)
    return Block(img=img, w=img.width, h=img.height, meta=dict(lines=[r["text"] for r in layout]))


def _draw_runs(draw, x, base_y, text, f, fb, fill, stroke, stroke_fill):
    for rf, chunk in _runs(text, f, fb):
        kw = dict(font=rf, fill=fill, anchor="ls")
        if stroke:
            kw.update(stroke_width=stroke, stroke_fill=stroke_fill)
        draw.text((x, base_y), chunk, **kw)
        x += rf.getlength(chunk)


# ---------------------------------------------------------------- colours

def _rel_lum(rgb) -> float:
    def c(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)


def contrast(a, b) -> float:
    la, lb = sorted((_rel_lum(a), _rel_lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def scene_colors(frames: list[np.ndarray], rect=None) -> dict:
    """Dominant hue of the scene and mean colour behind the text area."""
    hues, weights, means = [], [], []
    for f in frames[:: max(1, len(frames) // 8)]:
        small = f[::8, ::8, ::-1].reshape(-1, 3).astype(np.float32) / 255.0  # RGB
        mx, mn = small.max(1), small.min(1)
        sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
        mask = (sat > 0.18) & (mx > 0.18)
        if mask.any():
            px = small[mask]
            hsv = np.array([colorsys.rgb_to_hsv(*p) for p in px[:: max(1, len(px) // 400)]])
            hues += list(hsv[:, 0])
            weights += list(hsv[:, 1])
        if rect:
            x0, y0, x1, y1 = (int(v) for v in rect)
            region = f[max(0, y0):y1, max(0, x0):x1, ::-1]
            if region.size:
                means.append(region.reshape(-1, 3).mean(0))
    dom = None
    if hues:
        ang = np.array(hues) * 2 * np.pi
        wt = np.array(weights)
        dom = (np.arctan2((np.sin(ang) * wt).sum(), (np.cos(ang) * wt).sum()) / (2 * np.pi)) % 1.0
    bg = tuple(int(v) for v in np.mean(means, 0)) if means else (128, 128, 128)
    return {"dominant_hue": dom, "bg_rgb": bg, "bg_lum": _rel_lum(bg)}


def matched_colors(scene: dict) -> list[str]:
    """Pastels that harmonise with the scene, best first.

    Prefers the colour opposite the scene's dominant hue (it pops without
    clashing), then analogous tints; never picks one that blends into the
    background behind the text.
    """
    hue_of = {k: colorsys.rgb_to_hsv(*(c / 255 for c in v))[0] for k, v in PALETTE.items()
              if k not in ("white", "cream")}
    dom = scene["dominant_hue"]
    bg = scene["bg_rgb"]
    scored = []
    for name, h in hue_of.items():
        if dom is None:
            harmony = 0.5
        else:
            d = min(abs(h - dom), 1 - abs(h - dom))          # 0..0.5
            harmony = 1 - abs(d - 0.5) * 2 if d > 0.25 else 0.6 - d  # complementary best, analogous ok
        sep = contrast(PALETTE[name], bg)
        scored.append((harmony + 0.25 * min(sep, 4) / 4, name))
    return [n for _, n in sorted(scored, reverse=True)]
