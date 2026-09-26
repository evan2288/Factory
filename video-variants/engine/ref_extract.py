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

from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageFilter

from vv_detect import H, W, normalize_frame


@dataclass
class RefElement:
    """One piece of reference text that appears at one moment (e.g. the CTA at 2.1 s)."""
    name: str
    y0: int
    y1: int
    appear_s: float = 0.0
    outline_px: int = 0                       # width of the solid dark outline around the white fill
    close_px: int = 0                         # join thin inline strokes into solid letters first
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
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.paste(Image.fromarray(text, "RGBA"), (x0, el.y0))
        if el.shadow:
            canvas = _with_shadow(canvas, el.shadow)
        bbox = canvas.getbbox()
        layers.append({"name": el.name, "appear_s": el.appear_s, "img": canvas, "bbox": bbox,
                       "fill_px": int(fill.sum()), "text_px": int(alpha.sum())})
    return layers


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
