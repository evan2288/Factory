"""Make N text variants of one clip.

    python make_variants.py SRC.mp4 OUT_DIR --id SEED-02 --slug wallsit-living-room \
        --theme wallsit [--hook-index 0] [--n 10]

Writes OUT_DIR/<id>_<slug>_vNN.mp4, OUT_DIR/<id>_<slug>_preview.jpg and
OUT_DIR/<id>_<slug>.json (everything about each variant).
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from hooks import HOOKS
from vv_detect import H, W, HeadDetector, analyze, normalize_frame
from vv_render import encode, frame_at, full_frame_png, micro_grade, place_block, probe, psnr_outside_text, verify
from vv_text import FAMILIES, Hook, TextStyle, font, matched_colors, render_block, scene_colors

# 10 looks per clip: different font family, size and/or colour each time.
# "M1"/"M2" = pastel picked to suit this clip's colours.
PLAN = [
    # family      size  headline  body     white CTA box
    ("classic",   1.00, "white",  "white", False),
    ("classic",   0.92, "cream",  "cream", False),
    ("condensed", 1.00, "white",  "white", False),
    ("caps",      0.94, "white",  "white", False),
    ("classic",   1.06, "M1",     "white", True),
    ("impact",    0.96, "butter", "white", False),
    ("classic",   1.12, "white",  "white", True),
    ("classic",   1.00, "M2",     "M2",    False),
    ("caps",      1.04, "cream",  "cream", True),
    ("condensed", 1.08, "M1",     "M1",    False),
]
JITTER = [0, 12, -12, 20, -20, 8, -8, 16, -16, 4]
FAMILY_LABEL = {"classic": "TikTok Classic", "condensed": "Condensed", "impact": "Impact headline", "caps": "All caps"}


def style_label(st: TextStyle) -> str:
    colour = st.head_color if st.head_color == st.body_color else f"{st.head_color} headline"
    box = " + white CTA box" if st.cta_label else ""
    return f"{FAMILY_LABEL[st.family]} · {colour} · {round(st.scale * 100)}% size{box}"


def fit_and_place(hook: Hook, st: TextStyle, boxes, minor, jitter: int):
    """Render at the planned size; step down only if faces leave no clear room."""
    tried = []
    for shrink in (1.0, 0.94, 0.88, 0.82, 0.76, 0.70):
        s2 = TextStyle(st.family, round(st.scale * shrink, 3), st.head_color, st.body_color, st.cta_label, st.max_width)
        block = render_block(hook, s2)
        pl = place_block(block.w, block.h, boxes, minor, jitter)
        tried.append((pl, block, s2))
        if pl["ok"]:
            return tried[-1]
    return min(tried, key=lambda t: t[0]["face_overlap"])


def contact_sheet(paths: list[str], labels: list[str], out: str, title: str) -> None:
    tw, th = 216, 384
    cols = 5
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 30) + 50), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    d.text((12, 12), title, font=font("TikTokSans-Bold.ttf", 24), fill=(240, 240, 240))
    for i, (p, lab) in enumerate(zip(paths, labels)):
        f = frame_at(p, 0.5)
        if f is None:
            continue
        im = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)).resize((tw, th), Image.LANCZOS)
        x, y = (i % cols) * tw, 50 + (i // cols) * (th + 30)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + th + 6), lab, font=font("TikTokSans-SemiBold.ttf", 15), fill=(220, 220, 220))
    sheet.save(out, quality=86)


def make_variants(src: str, out_dir: str, source_id: str, slug: str, hook: Hook, n: int = 10,
                  crf: int = 16, preset: str = "slow", detector: HeadDetector | None = None,
                  log=print) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    info = probe(src)
    a = analyze(src, detector)
    scene = scene_colors(a["frames"], rect=(108, 0.35 * H, 972, 0.72 * H))
    m = [c for c in matched_colors(scene) if c not in ("white", "cream")]
    pick = {"M1": m[0], "M2": m[1] if len(m) > 1 else m[0]}
    log(f"  analysed {a['frames_sampled']} frames, {len(a['boxes'])} face boxes, "
        f"{a['frames_with_faces']}/{a['frames_sampled']} frames with faces, colours {pick} ({time.time() - t0:.0f}s)")

    base = f"{source_id}_{slug}"
    records, outs, labels = [], [], []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(1, n + 1):
            fam, scale, hc, bc, label = PLAN[(i - 1) % len(PLAN)]
            st = TextStyle(fam, scale, pick.get(hc, hc), pick.get(bc, bc), label)
            pl, block, st_used = fit_and_place(hook, st, a["boxes"], a["minor_boxes"], JITTER[(i - 1) % len(JITTER)])
            vid = f"{source_id}-v{i:02d}"
            png = os.path.join(tmp, f"{vid}.png")
            full_frame_png(block.img, pl["x"], pl["y"], png)
            grade = micro_grade(vid)
            out = os.path.join(out_dir, f"{base}_v{i:02d}.mp4")
            t1 = time.time()
            encode(src, png, out, grade, info["audio_codec"], crf=crf, preset=preset)
            v = verify(out, info["duration"], bool(info["audio_codec"]))
            # How different is the picture outside the text? (>= 38 dB looks identical)
            diff_db = psnr_outside_text(out, src, pl["y"], pl["y"] + block.h)
            rec = {
                "video_id": vid,
                "file": os.path.basename(out),
                "variant": i,
                "style": style_label(st_used),
                "family": st_used.family,
                "size_pct": round(st_used.scale * 100),
                "headline_color": st_used.head_color,
                "body_color": st_used.body_color,
                "cta_box": st_used.cta_label,
                "text_box": [pl["x"], pl["y"], block.w, block.h],
                "text_clear_of_faces": pl["ok"],
                "face_overlap_px": pl["face_overlap"],
                "grade": grade,
                "picture_diff_db": diff_db,
                "duration_s": v["info"]["duration"],
                "bytes": os.path.getsize(out),
                "verified": v["ok"],
                "problems": v["problems"],
                "encode_s": round(time.time() - t1, 1),
            }
            records.append(rec)
            outs.append(out)
            labels.append(f"v{i:02d} {st_used.family} {rec['size_pct']}% {st_used.head_color}")
            log(f"  {rec['file']}: {rec['style']} | y={pl['y']} clear={pl['ok']} | "
                f"{rec['bytes'] / 1e6:.1f} MB | diff {diff_db} dB | {rec['encode_s']}s | {'OK' if v['ok'] else v['problems']}")

    preview = os.path.join(out_dir, f"{base}_preview.jpg")
    contact_sheet(outs, labels, preview, f"{source_id}  {slug}  —  {hook.headline}")
    result = {
        "source_id": source_id,
        "slug": slug,
        "source_file": os.path.basename(src),
        "source_info": info,
        "hook": {"headline": hook.headline, "body": hook.body, "cta": hook.cta},
        "colours": pick,
        "faces": {"boxes": len(a["boxes"]), "frames_with_faces": a["frames_with_faces"],
                  "frames_sampled": a["frames_sampled"]},
        "preview": os.path.basename(preview),
        "variants": records,
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(out_dir, f"{base}.json"), "w") as f:
        json.dump(result, f, indent=2)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out_dir")
    ap.add_argument("--id", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--theme", required=True, choices=sorted(HOOKS))
    ap.add_argument("--hook-index", type=int, default=0)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--preset", default="slow")
    a = ap.parse_args()
    hooks = HOOKS[a.theme]
    det = HeadDetector()
    try:
        r = make_variants(a.src, a.out_dir, a.id, a.slug, hooks[a.hook_index % len(hooks)], a.n, a.crf, a.preset, det)
    finally:
        det.close()
    bad = [v["file"] for v in r["variants"] if not v["verified"] or not v["text_clear_of_faces"]]
    print(f"done in {r['seconds']}s; {len(r['variants']) - len(bad)}/{len(r['variants'])} passed" + (f"; check {bad}" if bad else ""))


if __name__ == "__main__":
    main()
