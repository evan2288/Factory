"""Place the text block, apply the invisible grade and encode each variant."""
from __future__ import annotations

import json
import random
import re
import subprocess

import cv2
import numpy as np
from PIL import Image

from vv_detect import H, W

FFMPEG = "ffmpeg"

# Where text may sit: centred, clear of the top header / bottom caption UI.
BAND = (0.22, 0.78)          # preferred: block top >= 22% of height, bottom <= 78%
BAND_WIDE = (0.16, 0.82)     # fallback when faces leave no room in the preferred band
HALO_WEIGHT = 0.005          # cost per px² of covering the soft margin around a face (neck, hair tips)
PREF_CENTER = 0.52           # block centre gravitates here (matches the references)


# ------------------------------------------------------------------ probe

def probe(path: str) -> dict:
    """Stream info from `ffmpeg -i` (no ffprobe in the static build)."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
    txt = r.stderr
    info = {"duration": None, "fps": None, "width": None, "height": None,
            "audio_codec": None, "color": None, "vcodec": None}
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", txt)
    if m:
        info["duration"] = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    for line in txt.splitlines():
        if "Video:" in line and info["width"] is None:
            mm = re.search(r"Video: (\w+)", line)
            info["vcodec"] = mm[1] if mm else None
            mm = re.search(r", (\d{2,5})x(\d{2,5})", line)
            if mm:
                info["width"], info["height"] = int(mm[1]), int(mm[2])
            mm = re.search(r"([\d.]+) fps", line)
            if mm:
                info["fps"] = float(mm[1])
            mm = re.search(r"yuv\w*\(([^)]*)\)", line)
            info["color"] = mm[1] if mm else None
        if "Audio:" in line and info["audio_codec"] is None:
            mm = re.search(r"Audio: (\w+)", line)
            info["audio_codec"] = mm[1] if mm else None
    return info


# -------------------------------------------------------------- placement

def place_block(bw: int, bh: int, boxes, minor, jitter: int = 0) -> dict:
    """Pick the block's top-left so it never covers a face at any point in the clip.

    Hard rule: no overlap with any face (incl. hair) or eyes/nose/mouth box.
    Soft: stay off the neck/halo margin and tiny background faces, keep near
    the preferred height. Returns {'x','y','ok','fallback','face_overlap'}.
    """
    x = (W - bw) // 2
    margin = 12
    hard = [b for b in boxes if b.tier in ("face", "core")]
    halo = [b for b in boxes if b.tier == "halo"]

    def cost_at(y, strict):
        rect = (x - margin, y - margin, x + bw + margin, y + bh + margin)
        face = sum(b.inter(*rect) for b in hard if b.tier == "face")
        core = sum(b.inter(*rect) for b in hard if b.tier == "core")
        if strict and (face > 0 or core > 0):
            return None
        soft = sum(b.inter(*rect) for b in halo) / max(1, len(halo) ** 0.5)
        small = sum(b.inter(*rect) for b in minor)
        centre = y + bh / 2
        return (core * 1e6 + face * 1e3 + soft * HALO_WEIGHT + small * 0.002 + abs(centre - PREF_CENTER * H)), face, core

    for band, fallback in ((BAND, False), (BAND_WIDE, True)):
        lo, hi = int(band[0] * H), int(band[1] * H) - bh
        cands = []
        for y in range(lo, max(lo, hi) + 1, 4):
            c = cost_at(y, strict=True)
            if c is not None:
                cands.append((c[0], y))
        if cands:
            cands.sort()
            y = cands[0][1]
            if jitter:  # small per-variant nudge, only if still clear of faces
                for dy in (jitter, -jitter, jitter // 2, -jitter // 2):
                    yy = y + dy
                    if lo <= yy <= hi and cost_at(yy, strict=True) is not None:
                        y = yy
                        break
            return {"x": x, "y": y, "ok": True, "fallback": fallback, "face_overlap": 0}

    # Nothing is fully clear (face fills the frame): least overlap, never the core face.
    lo, hi = int(BAND_WIDE[0] * H), int(BAND_WIDE[1] * H) - bh
    best = min(((cost_at(y, strict=False), y) for y in range(lo, max(lo, hi) + 1, 4)), key=lambda t: t[0][0])
    (score, face, core), y = best
    return {"x": x, "y": y, "ok": False, "fallback": True, "face_overlap": round(face + core)}


# ------------------------------------------------------------------ grade

def micro_grade(seed: str) -> dict:
    """Tiny, invisible adjustments that make each variant a distinct encode.

    Brightness moves at most ~1.5 of 255 levels; contrast and gamma stay
    within 0.8%, saturation within 1.6%; sharpening is very light.
    """
    rnd = random.Random(seed)

    def signed(lo, hi):
        return rnd.choice((-1, 1)) * rnd.uniform(lo, hi)

    return {
        "brightness": round(signed(0.002, 0.006), 4),
        "contrast": round(1 + signed(0.003, 0.008), 4),
        "saturation": round(1 + signed(0.006, 0.016), 4),
        "gamma": round(1 + signed(0.003, 0.008), 4),
        "sharpen": round(rnd.uniform(0.06, 0.16), 3),
    }


def filter_graph(g: dict) -> str:
    return (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd+full_chroma_int,"
        "crop=1080:1920,setsar=1,"
        f"eq=brightness={g['brightness']}:contrast={g['contrast']}:saturation={g['saturation']}:gamma={g['gamma']},"
        f"unsharp=5:5:{g['sharpen']}:5:5:0,format=yuv444p[v];"
        "[1:v]format=rgba,scale=out_color_matrix=bt709:out_range=tv,format=yuva444p[t];"
        "[v][t]overlay=0:0:format=yuv444:eof_action=repeat,format=yuv420p[out]"
    )


def encode(src: str, overlay_png: str, out: str, grade: dict, audio_codec: str | None,
           crf: int = 16, preset: str = "slow", music: dict | None = None) -> None:
    """Encode one variant. `music` = {"path", "start", "plan", "src_lufs", "duration"} or None.

    plan["mode"]: keep = original audio as is; mix = original + music under it;
    music_only = music replaces a silent/missing track.
    """
    graph = filter_graph(grade)
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-i", overlay_png]
    maps = ["-map", "[out]"]
    if music and music["plan"]["mode"] in ("mix", "music_only"):
        from vv_audio import audio_filter
        pre, agraph = audio_filter(music["plan"], music["duration"], music.get("src_lufs"), music["start"])
        cmd += pre + [music["path"]]
        graph += ";" + agraph
        maps += ["-map", "[aout]"]
        acodec = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    else:
        maps += ["-map", "0:a?"]
        acodec = ["-c:a", "copy"] if audio_codec == "aac" else ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-filter_complex", graph, *maps,
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-profile:v", "high", "-level:v", "4.2",
            "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-color_range", "tv", "-movflags", "+faststart", *acodec]
    if music:  # never let the music make the file longer than the clip
        cmd += ["-t", f"{music['duration']:.3f}"]
    cmd.append(out)
    subprocess.run(cmd, check=True)


def full_frame_png(block: Image.Image, x: int, y: int, path: str) -> None:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(block, (int(x), int(y)))
    canvas.save(path, optimize=True)


# ----------------------------------------------------------------- verify

def verify(out: str, expect_duration: float | None, expect_audio: bool) -> dict:
    """Decode the whole file and check size, duration and streams."""
    dec = subprocess.run([FFMPEG, "-v", "error", "-i", out, "-f", "null", "-"], capture_output=True, text=True)
    info = probe(out)
    problems = []
    if dec.stderr.strip():
        problems.append("decode errors: " + dec.stderr.strip()[:200])
    if (info["width"], info["height"]) != (W, H):
        problems.append(f"size {info['width']}x{info['height']}")
    if expect_duration and info["duration"] and abs(info["duration"] - expect_duration) > 0.25:
        problems.append(f"duration {info['duration']:.2f}s vs {expect_duration:.2f}s")
    if expect_audio and not info["audio_codec"]:
        problems.append("audio missing")
    return {"ok": not problems, "problems": problems, "info": info}


def frame_at(path: str, t_frac: float) -> np.ndarray | None:
    cap = cv2.VideoCapture(path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(n * t_frac)))
    ok, f = cap.read()
    cap.release()
    return f if ok else None


def psnr_outside_text(out: str, src: str, text_y0: int, text_y1: int, seconds: float = 2.0) -> float | None:
    """Frame-accurate PSNR (dB) between variant and source, away from the text.

    Uses the biggest band above or below the text block. >= 38 dB looks identical.
    """
    top = max(0, text_y0 - 24)
    bot = min(H, text_y1 + 24)
    y, h = (0, top) if top >= H - bot else (bot, H - bot)
    h -= h % 2
    if h < 64:
        return None
    norm = "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920"
    g = (f"[0:v]crop=1080:{h}:0:{y},format=yuv420p[a];"
         f"[1:v]{norm},crop=1080:{h}:0:{y},format=yuv420p[b];[a][b]psnr")
    r = subprocess.run([FFMPEG, "-hide_banner", "-t", str(seconds), "-i", out, "-t", str(seconds), "-i", src,
                        "-lavfi", g, "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"average:([\d.]+|inf)", r.stderr)
    return None if not m else (99.0 if m[1] == "inf" else round(float(m[1]), 1))


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return 99.0 if mse == 0 else 10 * np.log10(255 ** 2 / mse)


def dump(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
