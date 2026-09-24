"""Audio for variants: check what a clip's sound already contains, pick a music bed.

YAMNet (Google's AudioSet classifier) labels each ~1 s of audio. A clip whose
own audio is mostly music keeps it; otherwise one of our original tracks is
mixed in (under speech/ambience, or on its own when the clip is silent).
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
YAMNET = os.path.join(HERE, "models", "yamnet.tflite")
MUSIC_DIR = os.path.join(HERE, "music", "tracks")

# Which music styles suit which clip themes (first is the best fit).
THEME_STYLES = {
    "wallsit": ["gym_energy", "lofi_chill", "groove_pop"],
    "fitness": ["gym_energy", "groove_pop", "chic_house"],
    "dance": ["groove_pop", "chic_house", "gym_energy"],
    "fashion": ["chic_house", "groove_pop", "lofi_chill"],
    "skincare": ["elegant_piano", "lofi_chill", "soft_acoustic"],
    "makeup": ["lofi_chill", "elegant_piano", "chic_house"],
    "hair": ["chic_house", "lofi_chill", "elegant_piano"],
    "glow": ["elegant_piano", "lofi_chill", "soft_acoustic"],
    "morning": ["soft_acoustic", "lofi_chill", "groove_pop"],
    "city": ["soft_acoustic", "chic_house", "groove_pop"],
    "couple": ["soft_acoustic", "elegant_piano", "lofi_chill"],
}

MUSIC_WORDS = re.compile(r"music|instrument|piano|guitar|drum|bass|synth|keyboard|organ|string|beat|"
                         r"song|pop|rock|jazz|hip hop|electronic|disco|funk|house|techno|ambient|"
                         r"orchestra|violin|percussion|cymbal|hi-hat|snare|rhythm|melody|chord", re.I)

_classifier = None


def _clf():
    global _classifier
    if _classifier is None:
        from mediapipe.tasks.python import audio, core
        _classifier = audio.AudioClassifier.create_from_options(audio.AudioClassifierOptions(
            base_options=core.base_options.BaseOptions(model_asset_path=YAMNET),
            max_results=8, running_mode=audio.RunningMode.AUDIO_CLIPS))
    return _classifier


def pcm16k(path: str, seconds: float | None = None) -> np.ndarray | None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path]
    if seconds:
        cmd += ["-t", str(seconds)]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return np.frombuffer(r.stdout, dtype=np.float32)


def loudness(path: str) -> float | None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=framelog=quiet",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def classify(path: str, seconds: float | None = None) -> dict:
    """Share of ~1 s windows that sound like music / speech, plus the top labels."""
    from mediapipe.tasks.python.components.containers import audio_data as ad
    x = pcm16k(path, seconds)
    if x is None or len(x) < 16000 * 0.5:
        return {"has_audio": False, "music": 0.0, "speech": 0.0, "top": [], "lufs": None}
    data = ad.AudioData.create_from_array(x.astype(np.float32), 16000)
    res = _clf().classify(data)
    music = speech = 0
    counts: dict[str, float] = {}
    for r in res:
        cats = r.classifications[0].categories
        if any(MUSIC_WORDS.search(c.category_name) and c.score >= 0.25 for c in cats):
            music += 1
        if any(c.category_name in ("Speech", "Narration, monologue", "Conversation") and c.score >= 0.35
               for c in cats):
            speech += 1
        for c in cats[:3]:
            counts[c.category_name] = counts.get(c.category_name, 0) + c.score
    n = max(1, len(res))
    lufs = loudness(path)
    return {"has_audio": lufs is not None and lufs > -60, "music": round(music / n, 2), "speech": round(speech / n, 2),
            "top": [k for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:5]], "lufs": lufs}


def audio_plan(src_info: dict, cls: dict) -> dict:
    """Decide how a clip's variants get music."""
    if not src_info.get("audio_codec") or not cls["has_audio"] or (cls["lufs"] or -99) < -45:
        return {"mode": "music_only", "reason": "clip has no usable sound"}
    if cls["music"] >= 0.5:
        return {"mode": "keep", "reason": f"clip already has music ({int(cls['music'] * 100)}% of the time)"}
    # Keep the clip's own sound and lay music under it (lower under speech).
    under = 10.0 if cls["speech"] >= 0.3 else 6.0
    return {"mode": "mix", "music_below_db": under,
            "reason": f"clip sound kept, music {under:.0f} dB under it" + (" (speech)" if cls["speech"] >= 0.3 else "")}


def library() -> list[dict]:
    with open(os.path.join(MUSIC_DIR, "library.json")) as f:
        return json.load(f)


def pick_tracks(theme: str, clip_index: int, n: int, clip_dur: float, seed: str) -> list[dict]:
    """n music choices for one clip: rotate through tracks of the theme's styles,
    each starting at a different point in the track."""
    lib = library()
    styles = THEME_STYLES.get(theme, ["lofi_chill", "soft_acoustic", "elegant_piano"])
    pool = [t for s in styles for t in lib if t["style"] == s]
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        t = pool[(clip_index + i * 2) % len(pool)]
        latest = max(0.0, t["duration_s"] - clip_dur - 3)
        out.append({"file": t["file"], "style": t["style"], "start": round(rnd.uniform(0, latest), 2)})
    return out


def audio_filter(plan: dict, clip_dur: float, src_lufs: float | None, music_start: float) -> tuple[list[str], str]:
    """Extra ffmpeg input args for the music file and the audio filter graph producing [aout].

    Music input is index 2 (0 = clip, 1 = text overlay PNG).
    """
    fade_out = max(0.0, clip_dur - 0.8)
    music = (f"[2:a]aresample=48000,atrim=0:{clip_dur:.3f},asetpts=PTS-STARTPTS,"
             f"afade=t=in:st=0:d=0.35,afade=t=out:st={fade_out:.3f}:d=0.8")
    if plan["mode"] == "music_only":
        graph = f"{music},volume=1.0[aout]"
    else:  # mix
        target = (src_lufs if src_lufs is not None else -18.0) - plan["music_below_db"]
        target = max(-32.0, min(-18.0, target))
        gain = target - (-16.0)  # library tracks are mastered to -16 LUFS
        graph = (f"{music},volume={gain:.2f}dB[m];"
                 "[0:a]aresample=48000,aformat=channel_layouts=stereo[o];"
                 "[o][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89[aout]")
    return ["-ss", f"{music_start:.2f}", "-i"], graph
