"""Richer on-screen text for reference-matched variants.

Compared with vv_text (one look for the whole block), each piece of text here
has its own font, colour, size and effect, and the text is split into
"reveal units" (headline, body lines, CTA) so it can pop in over time.

Effects: outline (TikTok Classic), shadow, glow (neon), box (solid label
behind each line), pill (label behind the headline only).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from vv_text import FONT_DIR, W, _has_glyph

EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
FALLBACK = "TikTokSans-Bold.ttf"
FEATURES = ["lnum"]  # lining (full-height) numerals, e.g. Playfair draws "52" small by default

COLORS = {
    "white": (255, 255, 255),
    "cream": (255, 243, 218),
    "butter": (255, 222, 89),
    "gold": (245, 198, 105),
    "blush": (255, 186, 206),
    "pink": (255, 122, 176),
    "peach": (255, 196, 150),
    "coral": (255, 128, 102),
    "mint": (164, 240, 198),
    "sky": (160, 212, 255),
    "lilac": (212, 192, 255),
    "black": (17, 17, 17),
    "ink": (12, 12, 12),
}


@dataclass
class Part:
    """How one kind of text (headline / body / cta) is drawn."""
    font: str
    size: int
    color: str = "white"
    case: str = "as"            # as | upper
    effect: str = "outline"     # outline | shadow | glow | box | pill | plain
    stroke: float = 0.07        # outline width as a fraction of font size
    box: str = "white"          # label colour for box / pill
    box_alpha: int = 255
    glow: str = "pink"
    tracking: float = 0.0       # extra letter spacing, fraction of size


@dataclass
class Look:
    name: str
    head: Part
    body: Part
    cta: Part
    timing: str = "static"      # static | stagger | lines | late_cta | head_first
    anim: str = "pop"           # pop | fade | rise
    scale: float = 1.0
    max_width: float = 0.84     # of frame width
    gap: float = 0.28           # space between headline and body, fraction of headline size


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


_emoji_cache: dict = {}


def _is_emoji(ch: str) -> bool:
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF


def _emoji_img(ch: str, size: int) -> Image.Image:
    key = (ch, size)
    if key not in _emoji_cache:
        f = ImageFont.truetype(EMOJI_FONT, 109)  # colour bitmaps only come in this size
        im = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((0, 0), ch, font=f, embedded_color=True)
        im = im.crop(im.getbbox())
        s = size / max(im.size)
        _emoji_cache[key] = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    return _emoji_cache[key]


def _runs(text: str, f, fb):
    """(kind, font, chunk) runs: 'emoji' runs are pasted as bitmaps."""
    runs = []
    for ch in text:
        if ch == "️":
            continue
        if _is_emoji(ch):
            kind, use = "emoji", None
        else:
            kind, use = "text", (f if (ch.isspace() or _has_glyph(f, ch)) else fb)
        if runs and runs[-1][0] == kind and runs[-1][1] is use and kind == "text":
            runs[-1][2] += ch
        else:
            runs.append([kind, use, ch])
    return runs


def _width(text, f, fb, track):
    w = 0.0
    for kind, rf, chunk in _runs(text, f, fb):
        if kind == "emoji":
            w += f.size * 1.05 * len(chunk) + f.size * 0.1
        else:
            w += rf.getlength(chunk, features=FEATURES) + track * len(chunk)
    return w


def _balanced_wrap(text: str, f, fb, track, max_w) -> list[str]:
    out = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            continue
        lines = _greedy(words, f, fb, track, max_w)
        if len(lines) > 1:
            lo, hi = max_w * 0.4, max_w
            for _ in range(14):
                mid = (lo + hi) / 2
                if len(_greedy(words, f, fb, track, mid)) > len(lines):
                    lo = mid
                else:
                    hi = mid
            lines = _greedy(words, f, fb, track, hi)
        out += lines
    return out


def _greedy(words, f, fb, track, max_w):
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if cur and _width(t, f, fb, track) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


@dataclass
class Row:
    kind: str                   # head | body | cta
    unit: int                   # reveal unit index
    text: str
    part: Part
    f: ImageFont.FreeTypeFont
    fb: ImageFont.FreeTypeFont
    y: int = 0
    w: float = 0.0
    lh: int = 0


@dataclass
class Rendered:
    units: list[Image.Image]    # one RGBA image per reveal unit, all block-sized
    unit_kinds: list[str]
    w: int
    h: int
    lines: list[str] = field(default_factory=list)
    offset: tuple[int, int] = (0, 0)  # crop offset applied to every unit


def scaled(look: Look, s: float) -> Look:
    return replace(look, scale=round(look.scale * s, 3))


def _join_body(body: str) -> str:
    return " ".join(body.replace("\n", " ").split())


def layout_rows(text: dict, look: Look) -> list[Row]:
    s = look.scale
    max_w = W * look.max_width
    rows: list[Row] = []
    unit = 0

    def add(kind, raw, part, split_lines):
        nonlocal unit
        if not raw:
            return
        t = raw.upper() if part.case == "upper" else raw
        size = max(12, round(part.size * s))
        f = _font(part.font, size)
        fb = _font(FALLBACK, round(size * 0.95))
        track = part.tracking * size
        pad = 2 * size * (0.45 if part.effect in ("box", "pill") else part.stroke)
        lines = _balanced_wrap(t, f, fb, track, max_w - pad)
        if kind == "head":
            while len(lines) > 1 and size > part.size * s * 0.8:  # keep headlines on one line
                size -= 2
                f, fb = _font(part.font, size), _font(FALLBACK, round(size * 0.95))
                lines = _balanced_wrap(t, f, fb, part.tracking * size, max_w - pad)
        for i, line in enumerate(lines):
            rows.append(Row(kind, unit, line, part, f, fb))
            if split_lines and i < len(lines) - 1:
                unit += 1
        unit += 1

    per_line = look.timing == "lines"
    add("head", text.get("headline", ""), look.head, False)
    add("body", _join_body(text.get("body", "")), look.body, per_line)
    add("cta", _join_body(text.get("cta", "")), look.cta, False)
    return rows


def render(text: dict, look: Look) -> Rendered:
    rows = layout_rows(text, look)
    pad = 60
    y = pad
    prev = None
    for r in rows:
        p = r.part
        asc, desc = r.f.getmetrics()
        boxed = p.effect in ("box", "pill")
        r.lh = round((asc + desc) * (1.22 if boxed else 1.08))
        if prev and prev.kind != r.kind:
            y += round(prev.f.size * (look.gap if prev.kind == "head" else 0.35))
        r.y = y
        r.w = _width(r.text, r.f, r.fb, p.tracking * r.f.size)
        y += r.lh + (round(r.f.size * 0.10) if boxed else 0)
        prev = r
    block_h = y + pad
    block_w = int(max(r.w + 2 * r.f.size * 0.5 for r in rows) + 2 * pad)
    n_units = max(r.unit for r in rows) + 1
    units = [Image.new("RGBA", (block_w, block_h), (0, 0, 0, 0)) for _ in range(n_units)]
    kinds = [""] * n_units
    for r in rows:
        kinds[r.unit] = r.kind
        _draw_row(units[r.unit], r, block_w / 2)
    # crop all units to the common bounding box
    boxes = [u.getbbox() for u in units if u.getbbox()]
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    units = [u.crop((x0, y0, x1, y1)) for u in units]
    return Rendered(units, kinds, x1 - x0, y1 - y0, [r.text for r in rows], (x0, y0))


def _draw_text(draw_img: Image.Image, x: float, base: float, r: Row, fill, stroke=0, stroke_fill=None,
               emoji: bool = False):
    d = ImageDraw.Draw(draw_img)
    track = r.part.tracking * r.f.size
    for kind, rf, chunk in _runs(r.text, r.f, r.fb):
        if kind == "emoji":
            for ch in chunk:
                em = _emoji_img(ch, round(r.f.size * 1.05))
                x += r.f.size * 0.1
                if emoji:  # only on the main pass, not in shadow / glow passes
                    draw_img.alpha_composite(em, (round(x), round(base - em.height * 0.88)))
                x += em.width
            continue
        if track:
            for ch in chunk:
                kw = dict(font=rf, fill=fill, anchor="ls", features=FEATURES)
                if stroke:
                    kw.update(stroke_width=stroke, stroke_fill=stroke_fill)
                d.text((x, base), ch, **kw)
                x += rf.getlength(ch, features=FEATURES) + track
        else:
            kw = dict(font=rf, fill=fill, anchor="ls", features=FEATURES)
            if stroke:
                kw.update(stroke_width=stroke, stroke_fill=stroke_fill)
            d.text((x, base), chunk, **kw)
            x += rf.getlength(chunk, features=FEATURES)


def _draw_row(img: Image.Image, r: Row, cx: float) -> None:
    p = r.part
    size = r.f.size
    asc = r.f.getmetrics()[0]
    color = (*COLORS[p.color], 255)
    x = cx - r.w / 2
    base = r.y + asc
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    if p.effect in ("box", "pill"):
        bx, by = size * 0.42, size * 0.16
        top = r.y - by + size * 0.04
        ImageDraw.Draw(layer).rounded_rectangle(
            [x - bx, top, x + r.w + bx, top + r.lh + by * 0.6], radius=round(size * 0.22),
            fill=(*COLORS[p.box], p.box_alpha))
        _draw_text(layer, x, base, r, color, emoji=True)
        img.alpha_composite(layer)
        return
    stroke = max(2, round(size * p.stroke)) if p.effect in ("outline", "glow", "shadow") else 0
    if p.effect == "shadow":
        stroke = max(2, round(size * 0.025))  # thin edge keeps light text readable on bright scenes
    # soft dark shadow under everything (as in native TikTok text)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    _draw_text(sh, x + size * 0.02, base + size * 0.05, r, (0, 0, 0, 200), stroke, (0, 0, 0, 200))
    sh = sh.filter(ImageFilter.GaussianBlur(max(3, size * (0.09 if p.effect == "shadow" else 0.06))))
    img.alpha_composite(sh)
    if p.effect == "glow":
        g = Image.new("RGBA", img.size, (0, 0, 0, 0))
        _draw_text(g, x, base, r, (*COLORS[p.glow], 255), round(size * 0.10), (*COLORS[p.glow], 255))
        for rad, k in ((size * 0.28, 1), (size * 0.12, 1)):
            gl = g.filter(ImageFilter.GaussianBlur(rad))
            for _ in range(k):
                img.alpha_composite(gl)
    _draw_text(layer, x, base, r, color, stroke, (*COLORS["ink"], 255), emoji=True)
    img.alpha_composite(layer)


def schedule(kinds: list[str], timing: str) -> list[float]:
    """Start time (s) of each reveal unit."""
    starts = []
    if timing == "static":
        return [0.0] * len(kinds)
    if timing == "late_cta":
        return [2.1 if k == "cta" else 0.0 for k in kinds]
    if timing == "head_first":
        return [0.0 if k == "head" else 1.0 for k in kinds]
    if timing == "stagger":
        order = {"head": 0.0, "body": 0.7, "cta": 1.6}
        return [order[k] for k in kinds]
    if timing == "lines":
        t = 0.0
        for i, k in enumerate(kinds):
            if i == 0:
                starts.append(0.0)
                t = 0.55
                continue
            if k == "cta":
                t += 0.25
            starts.append(round(t, 2))
            t += 0.42
        return starts
    raise ValueError(timing)
