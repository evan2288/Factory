"""Lift the on-screen text layer out of a reference video, pixel for pixel.

Used for the "exact copy" variant: the reference's own letters (fill, outline,
inline details, emoji) are copied, so the font, size, colour and position are
identical to the reference. Only the soft shadow is re-drawn, because it is
see-through and can't be separated from the reference's background.

How: the text overlay is static while the scene behind it moves. Inside a
region of interest, pixels that are (a) near the text's white fill and (b)
don't change over time belong to the text layer; their median colour is the
text colour. Everything else is left transparent.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageFilter

from vv_detect import H, W, normalize_frame
from vv_text import FONT_DIR


@dataclass
class RefElement:
    """One piece of reference text that appears at one moment (e.g. the CTA at 2.1 s)."""
    name: str
    y0: int
    y1: int
    appear_s: float = 0.0
    outline_px: int = 0                       # width of the solid dark outline around the white fill
    close_px: int = 0                         # join thin inline strokes into solid letters first
    renumber: dict = field(default_factory=dict)  # {"text", "font", "inline"}: redraw the headline's number
    shadow: dict = field(default_factory=dict)  # {"blur", "opacity", "dx", "dy", "spread"}


@dataclass
class RefSpec:
    roi: tuple[int, int, int, int]            # x0, y0, x1, y1 of all reference text
    elements: list[RefElement]
    extra_boxes: list[tuple[int, int, int, int]] = field(default_factory=list)  # e.g. emoji: keep static pixels
    fill_min: int = 200                       # a pixel is "white fill" if all channels stay above this
    std_max: float = 14.0                     # max temporal std for a text pixel


def read_roi_frames(path: str, roi, fps: float = 10.0):
    x0, y0, x1, y1 = roi
    cap = cv2.VideoCapture(path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(src_fps / fps))
    times, crops, i = [], [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % step == 0:
            times.append(i / src_fps)
            crops.append(normalize_frame(f)[y0:y1, x0:x1].copy())
        i += 1
    cap.release()
    return np.array(times), np.stack(crops)


def _disk(r: int):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def extract(path: str, spec: RefSpec) -> list[dict]:
    """Return one full-frame RGBA layer per element: [{"name", "appear_s", "img", "bbox"}]."""
    x0, y0, x1, y1 = spec.roi
    times, crops = read_roi_frames(path, spec.roi)
    layers = []
    for el in spec.elements:
        use = crops[times >= el.appear_s + 0.15]            # frames where this element is fully on screen
        ey0, ey1 = el.y0 - y0, el.y1 - y0
        band = use[:, ey0:ey1].astype(np.float32)
        med = np.median(band, axis=0)
        std = band.std(axis=0).mean(axis=2)
        mn = band.min(axis=0).min(axis=2)
        fill = ((mn >= spec.fill_min) & (std <= spec.std_max)).astype(np.uint8)
        fill = cv2.morphologyEx(fill, cv2.MORPH_OPEN, _disk(1))  # drop isolated specks
        static = (std <= spec.std_max * 1.6).astype(np.uint8)
        if el.outline_px:
            # Outlined text: the whole text layer (fill + outline + inline details) is what stays
            # still while the scene moves, so its shape comes straight from the stillness map,
            # limited to a band around the letters. The inner part of the outline is always text.
            glyph = cv2.morphologyEx(fill, cv2.MORPH_CLOSE, _disk(el.close_px)) if el.close_px else fill
            zone = cv2.dilate(glyph, _disk(el.outline_px + 1))
            core = cv2.dilate(glyph, _disk(max(1, el.outline_px - 3)))
            lo, hi = spec.std_max, spec.std_max * 2.2
            soft = np.clip((hi - std) / (hi - lo), 0, 1) * zone
            soft = np.maximum(soft, core.astype(np.float32))
            band_px = (cv2.dilate(glyph, _disk(el.outline_px)) > 0) & (cv2.dilate(fill, _disk(1)) == 0)
            dark = band_px & (static > 0) & (med.max(axis=2) < 90)
            ink = np.median(med[dark], axis=0) if dark.sum() > 50 else np.array([12.0, 12.0, 12.0])
            med = med.copy()
            # the outer rim is pure outline colour (the reference mixed it with its own scene)
            med[(zone > 0) & (core == 0)] = ink
            alpha = (soft >= 0.5).astype(np.uint8)
        else:
            alpha = cv2.dilate(fill, _disk(1)) & static
        for bx0, by0, bx1, by1 in spec.extra_boxes:
            if by1 <= el.y0 or by0 >= el.y1:
                continue
            sub = np.zeros_like(alpha)
            sub[max(0, by0 - el.y0):by1 - el.y0, bx0 - x0:bx1 - x0] = 1
            alpha |= sub & (std <= spec.std_max).astype(np.uint8)
        # soft 1 px edge like a normally anti-aliased render
        a = cv2.GaussianBlur((soft if el.outline_px else alpha).astype(np.float32), (0, 0), 0.7)
        a[cv2.erode(alpha, _disk(1)) > 0] = 1.0
        rgb = med[:, :, ::-1]                                  # BGR -> RGB
        text = np.dstack([rgb, a * 255]).clip(0, 255).astype(np.uint8)
        if el.renumber:
            text = _renumber(text, fill, el, med, ink if el.outline_px else None)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.paste(Image.fromarray(text, "RGBA"), (x0, el.y0))
        if el.shadow:
            canvas = _with_shadow(canvas, el.shadow)
        bbox = canvas.getbbox()
        layers.append({"name": el.name, "appear_s": el.appear_s, "img": canvas, "bbox": bbox,
                       "fill_px": int(fill.sum()), "text_px": int(alpha.sum())})
    return layers


def _renumber(text: np.ndarray, fill: np.ndarray, el: RefElement, med: np.ndarray, ink) -> np.ndarray:
    """Replace the number at the end of the headline (e.g. "64" -> "65").

    The number is the last word of the headline's first line: everything right of the widest
    gap in the white fill. It is erased and redrawn at the same height, baseline, left edge,
    fill colour and outline, in the closest open font.
    """
    from PIL import ImageDraw, ImageFont

    rn = el.renumber
    rows = np.where(fill.any(axis=1))[0]
    head = fill[rows[0]:rows[0] + rn.get("line_h", fill.shape[0])]
    cols = head.any(axis=0)
    xs = np.where(cols)[0]
    gaps, start = [], None
    for x in range(xs[0], xs[-1] + 1):
        if not cols[x] and start is None:
            start = x
        elif cols[x] and start is not None:
            gaps.append((x - start, start, x))
            start = None
    _, g0, g1 = max(gaps)                                   # the space before the number
    dx0 = g1
    if rn.get("measure") == "layer":  # thin serifs: take the height from the whole layer, minus the outline
        top = max(0, rows[0] - el.outline_px - 4)
        band_ = (text[..., 3] > 127)[top:rows[0] + rn.get("line_h", fill.shape[0]), g1:]
        ys = np.where(band_.any(axis=1))[0]
        dy0, dy1 = top + ys[0] + el.outline_px, top + ys[-1] + 1 - el.outline_px
    else:
        ys = np.where(head[:, g1:].any(axis=1))[0]
        dy0, dy1 = rows[0] + ys[0], rows[0] + ys[-1] + 1
    colour = np.median(med[fill > 0], axis=0)[::-1]
    out = text.copy()
    m_ = el.outline_px + 8                                  # erase the old number with its outline
    out[max(0, dy0 - m_):dy1 + m_, (g0 + g1) // 2:] = 0

    # draw the new number 4x oversized, then scale down for clean edges
    k = 4
    f_path = os.path.join(FONT_DIR, rn["font"])
    size = 100
    probe = ImageFont.truetype(f_path, size * k)
    bb = probe.getbbox(rn["text"], features=["lnum"])
    size = size * (dy1 - dy0) / ((bb[3] - bb[1]) / k) * rn.get("scale", 1.0)
    f = ImageFont.truetype(f_path, round(size * k))
    bb = f.getbbox(rn["text"], features=["lnum"])
    pad = (el.outline_px + 4) * k
    wbig, hbig = bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad
    m = Image.new("L", (wbig, hbig), 0)
    ImageDraw.Draw(m).text((pad - bb[0], pad - bb[1]), rn["text"], font=f, fill=255, features=["lnum"])
    small = (round(wbig / k * rn.get("stretch", 1.0)), round(hbig / k))
    mask = np.asarray(m.resize(small, Image.LANCZOS), dtype=np.float32) / 255
    solid = (mask > 0.5).astype(np.uint8)
    rgb = np.empty((*mask.shape, 3), np.float32)
    rgb[:] = colour
    alpha = mask.copy()
    if rn.get("inline"):  # white rim, thin dark line, white core (engraved serif look)
        line = cv2.erode(solid, _disk(rn["inline"][0])) - cv2.erode(solid, _disk(sum(rn["inline"])))
        line = cv2.GaussianBlur(line.astype(np.float32), (0, 0), 0.6)
        rgb = rgb * (1 - line[..., None]) + np.array(ink if ink is not None else (12, 12, 12))[::-1] * line[..., None]
    if el.outline_px:
        ring = cv2.dilate(solid, _disk(el.outline_px)).astype(np.float32)
        ring = cv2.GaussianBlur(ring, (0, 0), 0.8)
        ink_rgb = np.array(ink)[::-1]
        rgb = rgb * mask[..., None] + ink_rgb * (1 - mask[..., None])
        alpha = np.maximum(mask, ring)
    ox, oy = dx0 - round((el.outline_px + 4) * rn.get("stretch", 1.0)), dy0 - (el.outline_px + 4)
    h, w = mask.shape
    y0c, x0c = max(0, oy), max(0, ox)
    y1c, x1c = min(out.shape[0], oy + h), min(out.shape[1], ox + w)
    patch = np.dstack([rgb, alpha * 255])[y0c - oy:y1c - oy, x0c - ox:x1c - ox]
    base = out[y0c:y1c, x0c:x1c].astype(np.float32)
    pa = patch[..., 3:4] / 255
    ba = base[..., 3:4] / 255
    oa = pa + ba * (1 - pa)
    oc = (patch[..., :3] * pa + base[..., :3] * ba * (1 - pa)) / np.maximum(oa, 1e-6)
    out[y0c:y1c, x0c:x1c] = np.dstack([oc, oa * 255]).clip(0, 255).astype(np.uint8)
    # keep the headline centred where the reference had it
    r0, r1 = max(0, dy0 - m_), dy1 + m_

    def centre(img):
        c = np.where((img[r0:r1, :, 3] > 60).any(axis=0))[0]
        return (c[0] + c[-1]) / 2

    shift = round(centre(text) - centre(out))
    if shift:
        band = out[r0:r1].copy()
        out[r0:r1] = 0
        if shift > 0:
            out[r0:r1, shift:] = band[:, :-shift]
        else:
            out[r0:r1, :shift] = band[:, -shift:]
    return out


def _with_shadow(layer: Image.Image, sh: dict) -> Image.Image:
    a = layer.getchannel("A")
    if sh.get("spread"):
        a = a.filter(ImageFilter.MaxFilter(2 * sh["spread"] + 1))
    a = a.filter(ImageFilter.GaussianBlur(sh.get("blur", 6)))
    a = a.point(lambda v: round(v * sh.get("opacity", 0.5)))
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    black = Image.new("RGBA", layer.size, (0, 0, 0, 255))
    shadow.paste(black, (sh.get("dx", 0), sh.get("dy", 0)), a)
    return Image.alpha_composite(shadow, layer)
