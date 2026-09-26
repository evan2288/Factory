"""15 variants of a clip made from a reference video's on-screen text.

    v01  EXACT COPY: the reference's own text layer (same font, size, colour,
         outline and timing), moved only if it would cover the face.
    v02  same fonts as the reference, new colours.
    v03+ 13 more looks: different fonts, title/body colours, sizes, effects and
         reveal timings (headline first, line by line, late CTA...).

Text is the reference's wording, verbatim, in every variant. Text never covers
a face at any point in the clip and stays in the middle band of the screen.

    python ref_variants.py --only SEED-04 --no-upload     # one clip, local only
    python ref_variants.py                               # all four, upload to Drive
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import replace

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from ref_extract import extract  # noqa: E402
from ref_specs import REFS  # noqa: E402
from vv_audio import MUSIC_DIR, pick_tracks  # noqa: E402
from vv_detect import H, W, Box, HeadDetector, _iou, sample_frames  # noqa: E402
from vv_render import filter_graph, frame_at, micro_grade, probe, psnr_outside_text, verify  # noqa: E402
from vv_style import Look, Part, render, scaled, schedule  # noqa: E402
from vv_text import font, matched_colors, scene_colors  # noqa: E402

N_VARIANTS = 15
BAND = (0.25, 0.77)          # preferred: block between 25% and 77% of the height
BAND_WIDE = (0.20, 0.82)     # fallback when the face leaves no room
EXACT_BAND = (0.15, 0.87)    # the exact copy keeps its size, so it may sit a little lower
PREF_CENTER = 0.58           # the references sit just below the middle
JITTER = [0, 16, -16, 28, -28, 8, -8, 22, -22, 12, -12, 30, -30, 4]
SHRINK_STEPS = (1.0, 0.94, 0.88, 0.82, 0.76, 0.70, 0.64)
SHRINK_FLAG = 0.85           # flag a variant whose text had to shrink below 85% of plan

# Same fonts as each reference, different colours (v02).
REF_TWIN = {
    "SEED-04": dict(head=("Montserrat-BlackItalic.ttf", 140), body=("TikTokSans-Medium.ttf", 64),
                    cta=("TikTokSans-Medium.ttf", 54), body_effect="shadow"),
    "SEED-05": dict(head=("TikTokSans-Bold.ttf", 118), body=("TikTokSans-SemiBold.ttf", 56),
                    cta=("TikTokSans-SemiBold.ttf", 68), body_effect="outline"),
    "SEED-06": dict(head=("TikTokSans-Black.ttf", 132), body=("Merriweather-Black.ttf", 60),
                    cta=("Merriweather-Black.ttf", 60), body_effect="shadow"),
    "SEED-07": dict(head=("PlayfairDisplay-Black.ttf", 150), body=("TikTokSans-SemiBold.ttf", 46),
                    cta=("TikTokSans-SemiBold.ttf", 46), body_effect="outline"),
}


def looks_for(sid: str, m1: str, m2: str) -> list[Look]:
    """14 designed looks (v02-v15). m1/m2 are pastels picked to suit this clip's colours."""
    t = REF_TWIN[sid]
    return [
        Look("Reference fonts, new colours",
             Part(t["head"][0], t["head"][1], "butter"),
             Part(t["body"][0], t["body"][1], "white", effect=t["body_effect"], stroke=0.05),
             Part(t["cta"][0], t["cta"][1], m1, effect=t["body_effect"], stroke=0.05),
             timing="static"),
        Look("Bold title, italic body",
             Part("Montserrat-Black.ttf", 124, "white"),
             Part("Montserrat-SemiBoldItalic.ttf", 58, m1, effect="shadow"),
             Part("Montserrat-SemiBoldItalic.ttf", 48, "white", effect="shadow"),
             timing="stagger", anim="pop"),
        Look("Serif gold",
             Part("PlayfairDisplay-Black.ttf", 138, "gold", effect="shadow"),
             Part("PlayfairDisplay-BoldItalic.ttf", 62, "white", effect="shadow"),
             Part("PlayfairDisplay-BoldItalic.ttf", 54, "cream", effect="shadow"),
             timing="stagger", anim="fade"),
        Look("Label boxes, line by line",
             Part("TikTokSans-Black.ttf", 104, "white", effect="pill", box="coral"),
             Part("TikTokSans-Bold.ttf", 52, "black", effect="box", box="white"),
             Part("TikTokSans-Bold.ttf", 46, "white", effect="box", box="black", box_alpha=225),
             timing="lines", anim="pop", gap=0.18),
        Look("Neon glow",
             Part("TikTokSans-Black.ttf", 128, "white", effect="glow", glow="pink", stroke=0.035),
             Part("TikTokSans-Bold.ttf", 58, "white", stroke=0.06),
             Part("TikTokSans-Bold.ttf", 50, "butter", stroke=0.06),
             timing="head_first", anim="fade"),
        Look("Poster",
             Part("BebasNeue-Regular.ttf", 196, "butter", stroke=0.035),
             Part("TikTokSans-SemiBold.ttf", 52, "white", case="upper", tracking=0.02, stroke=0.06),
             Part("TikTokSans-SemiBold.ttf", 46, m1, case="upper", tracking=0.02, stroke=0.06),
             timing="stagger", anim="fade", gap=0.12),
        Look("Typewriter",
             Part("ArchivoBlack-Regular.ttf", 112, "white"),
             Part("CourierPrime-Bold.ttf", 54, "white", effect="box", box="black", box_alpha=170),
             Part("CourierPrime-Bold.ttf", 48, "butter", effect="box", box="black", box_alpha=170),
             timing="lines", anim="fade", gap=0.22),
        Look("Highlighted title",
             Part("Montserrat-ExtraBoldItalic.ttf", 104, "black", effect="pill", box="butter"),
             Part("TikTokSans-Bold.ttf", 60, "white"),
             Part("TikTokSans-Bold.ttf", 50, "butter"),
             timing="head_first", anim="pop", gap=0.2),
        Look("Pastel serif",
             Part("DMSerifDisplay-Regular.ttf", 142, "blush", effect="shadow"),
             Part("Poppins-SemiBoldItalic.ttf", 56, "white", effect="shadow"),
             Part("Poppins-SemiBoldItalic.ttf", 48, "blush", effect="shadow"),
             timing="static", anim="fade"),
        Look("Big classic, late CTA",
             Part("TikTokSans-Black.ttf", 150, "white"),
             Part("TikTokSans-Bold.ttf", 66, "sky"),
             Part("TikTokSans-Bold.ttf", 58, "white"),
             timing="late_cta", anim="pop"),
        Look("Small caps, line by line",
             Part("Montserrat-ExtraBold.ttf", 96, m2, case="upper"),
             Part("Montserrat-SemiBoldItalic.ttf", 56, "white", stroke=0.06),
             Part("Montserrat-Bold.ttf", 44, "white", case="upper", stroke=0.06),
             timing="lines", anim="fade"),
        Look("Condensed",
             Part("Anton-Regular.ttf", 150, "white", stroke=0.05),
             Part("LeagueGothic-Regular.ttf", 86, "butter", stroke=0.05),
             Part("LeagueGothic-Regular.ttf", 72, "white", stroke=0.05),
             timing="stagger", anim="pop", gap=0.18),
        Look("Magazine",
             Part("PlayfairDisplay-BoldItalic.ttf", 136, "white", effect="shadow"),
             Part("TikTokSans-SemiBold.ttf", 42, "cream", case="upper", tracking=0.06, effect="box",
                  box="black", box_alpha=150),
             Part("TikTokSans-SemiBold.ttf", 40, "butter", case="upper", tracking=0.06, effect="box",
                  box="black", box_alpha=150),
             timing="head_first", anim="fade", gap=0.2),
        Look("Italic impact",
             Part("Poppins-BlackItalic.ttf", 124, "peach"),
             Part("Lora-BoldItalic.ttf", 62, "white", effect="shadow"),
             Part("Lora-BoldItalic.ttf", 54, "peach", effect="shadow"),
             timing="stagger", anim="fade"),
    ]


# ------------------------------------------------------------------ faces

def analyze_faces(path: str, det: HeadDetector) -> dict:
    """Face keep-out boxes for the whole clip (see vv_detect.analyze).

    One change for close-ups: when the face detectors already see a face, the
    body-pose head box for the same head only counts as soft margin. The pose
    box is sized from the shoulders and runs far below the chin in close-ups;
    it is still a hard box for heads the face detectors miss (profiles).
    """
    frames = sample_frames(path)
    per_frame = []
    for f in frames:
        bs = det.detect(f)
        frontal = [b for b in bs if b.src in ("yunet", "blaze") and b.tier == "face"]
        for b in bs:
            if b.src == "pose" and b.tier in ("face", "core"):
                if any(b.inter(fb.x0, fb.y0, fb.x1, fb.y1) > 0.3 * min(b.area(), fb.area()) for fb in frontal):
                    b.tier = "halo"
        per_frame.append(bs)
    n = len(frames)
    need = max(2, int(round(0.12 * n)))
    keep, minor = [], []
    for fi, fb in enumerate(per_frame):
        for b in fb:
            support = sum(1 for fj, other in enumerate(per_frame)
                          if fj != fi and any(o.tier == b.tier and _iou(o, b) > 0.25 for o in other))
            if support + 1 < need:
                continue
            face_h = (b.y1 - b.y0) / {"halo": 1.85, "face": 1.38, "core": 0.85}[b.tier]
            (keep if face_h >= 0.03 * H or b.src == "pose" else minor).append(b)
    return {"frames": frames, "boxes": keep, "minor_boxes": minor, "frames_sampled": n,
            "frames_with_faces": sum(1 for fb in per_frame if fb)}


def face_cost(x, y, bw, bh, boxes, minor, margin=12):
    rect = (x - margin, y - margin, x + bw + margin, y + bh + margin)
    face = sum(b.inter(*rect) for b in boxes if b.tier == "face")
    core = sum(b.inter(*rect) for b in boxes if b.tier == "core")
    halo = [b for b in boxes if b.tier == "halo"]
    soft = sum(b.inter(*rect) for b in halo) / max(1, len(halo) ** 0.5)
    small = sum(b.inter(*rect) for b in minor)
    return face, core, soft, small


def place(bw, bh, boxes, minor, jitter=0, x=None):
    """Top-left for a bw x bh block: never on a face, near PREF_CENTER, inside the band."""
    x = (W - bw) // 2 if x is None else x
    for band, fallback in ((BAND, False), (BAND_WIDE, True)):
        lo, hi = int(band[0] * H), int(band[1] * H) - bh
        cands = []
        for y in range(lo, max(lo, hi) + 1, 4):
            face, core, soft, small = face_cost(x, y, bw, bh, boxes, minor)
            if face or core:
                continue
            cands.append((soft * 0.005 + small * 0.002 + abs(y + bh / 2 - PREF_CENTER * H), y))
        if cands:
            y = min(cands)[1]
            for dy in (jitter, -jitter, jitter // 2, -jitter // 2):
                if dy and lo <= y + dy <= hi and not any(face_cost(x, y + dy, bw, bh, boxes, minor)[:2]):
                    y += dy
                    break
            return {"x": x, "y": y, "ok": True, "fallback": fallback, "face_overlap": 0}
    lo, hi = int(BAND_WIDE[0] * H), int(BAND_WIDE[1] * H) - bh
    best = min((sum(face_cost(x, y, bw, bh, boxes, minor)[:2]), y) for y in range(lo, max(lo, hi) + 1, 4))
    return {"x": x, "y": best[1], "ok": False, "fallback": True, "face_overlap": round(best[0])}


def place_exact(bbox, boxes, minor):
    """Smallest vertical move that keeps the reference's own text off the face."""
    x0, y0, x1, y1 = bbox
    bh = y1 - y0
    lo, hi = int(EXACT_BAND[0] * H), int(EXACT_BAND[1] * H) - bh
    for dy in sorted(range(lo - y0, hi - y0 + 1), key=abs):
        face, core, _, _ = face_cost(x0, y0 + dy, x1 - x0, bh, boxes, minor)
        if not face and not core:
            return {"dy": dy, "ok": True, "face_overlap": 0}
    return {"dy": 0, "ok": False, "face_overlap": round(sum(face_cost(x0, y0, x1 - x0, bh, boxes, minor)[:2]))}


# ------------------------------------------------------------------ encode

def encode_layers(src: str, layers: list[dict], out: str, grade: dict, fps: float, dur: float,
                  music: dict | None, crf: int = 16, preset: str = "slow") -> None:
    """layers: [{"png", "start", "anim"}], each a full-frame RGBA PNG."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src]
    for L in layers:
        cmd += ["-loop", "1", "-framerate", f"{fps:g}", "-t", f"{dur:.3f}", "-i", L["png"]]
    base = filter_graph(grade).split(";")[0]  # scale/crop + invisible grade -> [v]
    parts = [base.replace("[v]", "[v0]")]
    for i, L in enumerate(layers, 1):
        st = L["start"]
        chain = f"[{i}:v]format=rgba"
        if st > 0 or L["anim"] != "pop":
            d = {"pop": 1.0 / fps, "fade": 0.28, "rise": 0.32}[L["anim"]]
            chain += f",fade=t=in:st={st:.3f}:d={d:.3f}:alpha=1"
        chain += f",scale=out_color_matrix=bt709:out_range=tv,format=yuva444p[t{i}]"
        parts.append(chain)
        ypos = "0"
        if L["anim"] == "rise":
            ypos = f"'if(lt(t,{st:.3f}),36,if(lt(t,{st + 0.32:.3f}),36*(1-(t-{st:.3f})/0.32),0))'"
        parts.append(f"[v{i - 1}][t{i}]overlay=x=0:y={ypos}:format=yuv444:eval=frame:eof_action=repeat[v{i}]")
    parts.append(f"[v{len(layers)}]format=yuv420p[out]")
    graph = ";".join(parts)
    maps = ["-map", "[out]"]
    acodec = []
    if music:
        mi = len(layers) + 1
        cmd += ["-ss", f"{music['start']:.2f}", "-i", music["path"]]
        fade_out = max(0.0, dur - 0.8)
        graph += (f";[{mi}:a]aresample=48000,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d=0.35,afade=t=out:st={fade_out:.3f}:d=0.8[aout]")
        maps += ["-map", "[aout]"]
        acodec = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    cmd += ["-filter_complex", graph, *maps, "-r", f"{fps:g}",
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-profile:v", "high", "-level:v", "4.2",
            "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-color_range", "tv", "-movflags", "+faststart", *acodec, "-t", f"{dur:.3f}", out]
    subprocess.run(cmd, check=True)


def full_png(img: Image.Image, x: int, y: int, path: str) -> None:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(img, (int(x), int(y)))
    canvas.save(path)


def contact_sheet(paths, labels, out, title, t_frac=0.93):
    tw, th, cols = 216, 384, 5
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 48) + 50), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    d.text((12, 12), title, font=font("TikTokSans-Bold.ttf", 24), fill=(240, 240, 240))
    for i, (p, lab) in enumerate(zip(paths, labels)):
        f = frame_at(p, t_frac)
        if f is None:
            continue
        im = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)).resize((tw, th), Image.LANCZOS)
        x, y = (i % cols) * tw, 50 + (i // cols) * (th + 48)
        sheet.paste(im, (x, y))
        for k, line in enumerate(lab.split("\n")[:2]):
            d.text((x + 6, y + th + 4 + k * 20), line, font=font("TikTokSans-SemiBold.ttf", 15),
                   fill=(255, 222, 89) if "EXACT" in line else (220, 220, 220))
    sheet.save(out, quality=88)


# ------------------------------------------------------------------ one clip

def make_ref_variants(sid: str, clip: str, reference: str, out_dir: str, n: int = N_VARIANTS,
                      detector: HeadDetector | None = None, log=print, crf: int = 16, preset: str = "slow") -> dict:
    r = REFS[sid]
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    info = probe(clip)
    fps, dur = info["fps"] or 24.0, info["duration"]
    det = detector or HeadDetector()
    a = analyze_faces(clip, det)
    boxes, minor = a["boxes"], a["minor_boxes"]
    scene = scene_colors(a["frames"], rect=(108, 0.40 * H, 972, 0.78 * H))
    pastels = [c for c in matched_colors(scene) if c not in ("white", "cream", "gold", "butter")]
    m1, m2 = random.Random(sid).sample(pastels[:3], 2)
    tracks = pick_tracks(r["theme"], 0, n, dur, seed=sid)
    log(f"  {sid}: {a['frames_sampled']} frames, {len(boxes)} face boxes; pastels {m1}/{m2} "
        f"({time.time() - t0:.0f}s)")

    base = f"{sid}_{r['slug']}"
    records, outs, labels = [], [], []
    with tempfile.TemporaryDirectory() as tmp:
        # ---- v01: exact copy of the reference's text layer
        ex = extract(reference, r["exact"])
        x0 = min(L["bbox"][0] for L in ex)
        y0 = min(L["bbox"][1] for L in ex)
        x1 = max(L["bbox"][2] for L in ex)
        y1 = max(L["bbox"][3] for L in ex)
        pe = place_exact((x0, y0, x1, y1), boxes, minor)
        plans = [dict(kind="exact", look=None, layers=[], box=(x0, y0 + pe["dy"], x1 - x0, y1 - y0),
                      ok=pe["ok"], overlap=pe["face_overlap"], size_pct=100, dy=pe["dy"])]
        for k, L in enumerate(ex):
            png = os.path.join(tmp, f"v01_{k}.png")
            canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            canvas.alpha_composite(L["img"], (0, pe["dy"])) if pe["dy"] >= 0 else \
                canvas.alpha_composite(L["img"].crop((0, -pe["dy"], W, H)), (0, 0))
            canvas.save(png)
            plans[0]["layers"].append({"png": png, "start": L["appear_s"], "anim": "pop", "unit": L["name"]})

        # ---- v02-v15: designed looks
        for i, look in enumerate(looks_for(sid, m1, m2)[: n - 1], start=2):
            tried = []
            for s in SHRINK_STEPS:
                lk = scaled(look, s)
                rd = render(r["text"], lk)
                pl = place(rd.w, rd.h, boxes, minor, JITTER[(i - 2) % len(JITTER)])
                tried.append((pl, rd, s))
                if pl["ok"]:
                    break
            pl, rd, s = tried[-1] if tried[-1][0]["ok"] else min(tried, key=lambda t: t[0]["face_overlap"])
            starts = schedule(rd.unit_kinds, look.timing)
            layers = []
            for k, (u, st) in enumerate(zip(rd.units, starts)):
                png = os.path.join(tmp, f"v{i:02d}_{k}.png")
                full_png(u, pl["x"], pl["y"], png)
                layers.append({"png": png, "start": st, "anim": look.anim if st > 0 or look.anim == "fade" else "pop",
                               "unit": rd.unit_kinds[k]})
            plans.append(dict(kind="look", look=look, layers=layers, box=(pl["x"], pl["y"], rd.w, rd.h),
                              ok=pl["ok"], overlap=pl["face_overlap"], size_pct=round(s * 100), dy=0,
                              lines=rd.lines))

        for i, p in enumerate(plans, start=1):
            vid = f"{sid}-v{i:02d}"
            name = f"{base}_v{i:02d}" + ("_EXACT-COPY" if p["kind"] == "exact" else "") + ".mp4"
            out = os.path.join(out_dir, name)
            grade = micro_grade(vid)
            tr = tracks[i - 1]
            music = {"path": os.path.join(MUSIC_DIR, tr["file"]), "start": tr["start"]}
            t1 = time.time()
            encode_layers(clip, p["layers"], out, grade, fps, dur, music, crf=crf, preset=preset)
            v = verify(out, dur, expect_audio=True)
            bx, by, bw, bh = p["box"]
            diff_db = psnr_outside_text(out, clip, by, by + bh)
            look = p["look"]
            timing = "same as reference" if look is None else look.timing
            reveal = [{"unit": L["unit"], "at_s": L["start"], "anim": L["anim"]} for L in p["layers"]]
            flags = []
            if not p["ok"]:
                flags.append(f"text overlaps a face ({p['overlap']} px²)")
            if p["size_pct"] < SHRINK_FLAG * 100:
                flags.append(f"text shrunk to {p['size_pct']}% to clear the face")
            if diff_db is not None and diff_db < 38:
                flags.append(f"picture differs from source ({diff_db} dB)")
            if not v["ok"]:
                flags += v["problems"]
            rec = {
                "video_id": vid, "file": name, "variant": i,
                "exact_copy": p["kind"] == "exact",
                "label": "EXACT COPY of reference text" if look is None else look.name,
                "text": r["text"],
                "fonts": ({"all": "lifted from the reference video"} if look is None else
                          {"headline": look.head.font, "body": look.body.font, "cta": look.cta.font}),
                "colors": ({"all": "as reference"} if look is None else
                           {"headline": look.head.color, "body": look.body.color, "cta": look.cta.color}),
                "effects": (None if look is None else
                            {"headline": look.head.effect, "body": look.body.effect, "cta": look.cta.effect}),
                "size_pct": p["size_pct"],
                "timing": timing, "reveal": reveal,
                "text_box": [bx, by, bw, bh],
                "text_top_pct": round(by / H * 100, 1), "text_bottom_pct": round((by + bh) / H * 100, 1),
                "moved_from_reference_px": p["dy"] if look is None else None,
                "text_clear_of_faces": p["ok"], "face_overlap_px": p["overlap"],
                "music": {"mode": "music_only", "track": tr["file"], "style": tr["style"], "start_s": tr["start"]},
                "grade": grade, "picture_diff_db": diff_db,
                "duration_s": v["info"]["duration"], "bytes": os.path.getsize(out),
                "verified": v["ok"], "problems": flags, "encode_s": round(time.time() - t1, 1),
            }
            records.append(rec)
            outs.append(out)
            lab = "v01 EXACT COPY" if look is None else f"v{i:02d} {look.name}"
            labels.append(f"{lab}\n{rec['size_pct']}% · {timing} · {rec['text_top_pct']:.0f}-{rec['text_bottom_pct']:.0f}%")
            log(f"    {name}: {rec['label']} | {timing} | y {rec['text_top_pct']}-{rec['text_bottom_pct']}% | "
                f"size {rec['size_pct']}% | clear={p['ok']} | {rec['bytes'] / 1e6:.1f} MB | {diff_db} dB | "
                f"{rec['encode_s']}s | {'OK' if not flags else flags}")

    preview = os.path.join(out_dir, f"{base}_preview.jpg")
    contact_sheet(outs, labels, preview, f"{sid}  {r['slug']}  ·  reference: {r['reference'][:28]}")
    result = {
        "source_id": sid, "slug": r["slug"], "theme": r["theme"],
        "source_file": os.path.basename(clip), "reference_file": os.path.basename(reference),
        "reference_look": r["ref_look"], "text": r["text"], "source_info": info,
        "faces": {"boxes": len(boxes), "frames_with_faces": a["frames_with_faces"], "frames_sampled": a["frames_sampled"]},
        "pastels": [m1, m2], "preview": os.path.basename(preview), "variants": records,
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(out_dir, f"{base}.json"), "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return result


# ------------------------------------------------------------------ batch

INTAKE_FOLDER_ID = "1CpetOR7yOXulJsacZ1EaT8J2yw-B_FOl"   # Factory Intake (read only)
DEST_PATH = "3_SEEDANCE_2.5/four videos September 25th"   # inside BANK


def main():
    import run_batch as rb

    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--preset", default="slow")
    ap.add_argument("--n", type=int, default=N_VARIANTS)
    a = ap.parse_args()
    work = os.path.join(rb.WORK, "sep25")
    src_dir = os.path.join(work, "src")
    os.makedirs(src_dir, exist_ok=True)
    rb.RCLONE = rb.rclone_bin()
    rb.write_rclone_conf()
    state_path = os.path.join(work, "state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    det = HeadDetector()
    try:
        for sid, r in REFS.items():
            if a.only and sid not in a.only:
                continue
            if state.get(sid, {}).get("done") and not a.no_upload:
                rb.log(f"{sid}: already in BANK, skipping")
                continue
            for name in (r["clip"], r["reference"]):  # copies only; the intake folder is never changed
                if not os.path.exists(os.path.join(src_dir, name)):
                    rb.rc("copyto", rb.remote(INTAKE_FOLDER_ID, name), os.path.join(src_dir, name))
            out_dir = os.path.join(work, "out", sid)
            rb.log(f"{sid} {r['slug']}: rendering {a.n} variants")
            res = make_ref_variants(sid, os.path.join(src_dir, r["clip"]), os.path.join(src_dir, r["reference"]),
                                    out_dir, n=a.n, detector=det, log=lambda m: rb.log(m), preset=a.preset)
            flagged = [v["file"] for v in res["variants"] if v["problems"]]
            if not a.no_upload:
                dest = rb.remote(rb.BANK_FOLDER_ID, DEST_PATH)
                rb.rc("copy", out_dir, dest, "--include", "*.mp4", "--transfers", "4", "--drive-chunk-size", "32M")
                base = f"{sid}_{r['slug']}"
                rb.rc("copyto", os.path.join(out_dir, f"{base}_preview.jpg"),
                      rb.remote(rb.BANK_FOLDER_ID, f"{DEST_PATH}/_previews/{base}_preview.jpg"))
                rb.rc("copyto", os.path.join(out_dir, f"{base}.json"), rb.remote(rb.BANK_FOLDER_ID, f"_data/{base}.json"))
                listed = json.loads(rb.rc("lsjson", "--files-only", dest))
                sizes = {f["Name"]: f["Size"] for f in listed}
                missing = [v["file"] for v in res["variants"] if sizes.get(v["file"]) != v["bytes"]]
                if missing:
                    raise RuntimeError(f"{sid}: upload check failed for {missing}")
                for v in res["variants"]:
                    os.remove(os.path.join(out_dir, v["file"]))
                state[sid] = {"done": True, "flagged": flagged, "seconds": res["seconds"]}
                with open(state_path, "w") as f:
                    json.dump(state, f, indent=2)
            rb.log(f"{sid}: {len(res['variants'])} variants in {res['seconds']:.0f}s"
                   + (f"; flagged {flagged}" if flagged else "; all checks passed"))
    finally:
        det.close()
    if not a.no_upload and all(state.get(s, {}).get("done") for s in REFS):
        shutil.rmtree(src_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
