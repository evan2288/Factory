"""Compose a small library of original, royalty-free background tracks.

    python music_gen.py            # writes music/tracks/*.m4a + music/tracks/library.json

Each track is written as MIDI, every instrument is rendered on its own with
FluidSynth (GeneralUser GS soundfont, free for commercial music), measured,
set to a target loudness for its role, then mixed and normalised to -16 LUFS.
Balancing by measurement keeps the mix sane without anyone listening.
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import tempfile

import mido

HERE = os.path.dirname(os.path.abspath(__file__))
SF2 = os.path.join(HERE, "music", "sf2", "GeneralUser-GS.sf2")
OUT = os.path.join(HERE, "music", "tracks")
PPQ = 480
LENGTH_S = 52

DEG = {"I": 0, "ii": 2, "iii": 4, "IV": 5, "V": 7, "vi": 9, "vii": 11,
       "i": 0, "bIII": 3, "iv": 5, "v": 7, "bVI": 8, "bVII": 10}
QUAL = {"maj": [0, 4, 7], "min": [0, 3, 7], "maj7": [0, 4, 7, 11], "min7": [0, 3, 7, 10],
        "dom7": [0, 4, 7, 10], "maj9": [0, 4, 7, 11, 14], "min9": [0, 3, 7, 10, 14],
        "add9": [0, 4, 7, 14], "sus2": [0, 2, 7], "dom9": [0, 4, 7, 10, 14]}
KEYS = {"C": 0, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
PENTA_MAJ = [0, 2, 4, 7, 9]
PENTA_MIN = [0, 3, 5, 7, 10]

# GM drum notes
KICK, SNARE, RIM, CLAP, CHH, OHH, CRASH, SHAKER, TAMB = 36, 38, 37, 39, 42, 46, 49, 82, 54


class Part:
    def __init__(self, name, program, channel, role, reverb=40, drums=False):
        self.name, self.program, self.channel, self.role = name, program, channel, role
        self.reverb, self.drums = reverb, drums
        self.notes = []  # (start_beats, dur_beats, pitch, vel)

    def add(self, start, dur, pitch, vel):
        self.notes.append((start, dur, int(pitch), max(1, min(127, int(vel)))))


def chord_pcs(key_pc, deg, qual):
    root = (key_pc + DEG[deg]) % 12
    return root, [(root + i) for i in QUAL[qual]]


def voice(intervals_abs, prev, lo, hi):
    """Pick an inversion/octave inside [lo, hi] that moves least from the previous voicing."""
    root = intervals_abs[0]
    cands = []
    base = [root + i - intervals_abs[0] for i in intervals_abs]
    for inv in range(len(base)):
        v = base[inv:] + [n + 12 for n in base[:inv]]
        for octv in range(-3, 6):
            vv = [n + 12 * octv for n in v]
            if vv[0] >= lo and vv[-1] <= hi:
                cands.append(vv)
    if not cands:
        return [n + 12 * ((lo - base[0]) // 12 + 1) for n in base]
    if not prev:
        mid = (lo + hi) / 2
        return min(cands, key=lambda c: abs(sum(c) / len(c) - mid))
    return min(cands, key=lambda c: sum(min(abs(a - b) for b in prev) for a in c))


def humanize(rnd, t, v, tj=0.012, vj=7):
    return t + rnd.uniform(-tj, tj), v + rnd.randint(-vj, vj)


# ------------------------------------------------------------------ styles

def style_lofi(rnd, key, prog, bpm, bars):
    ep = Part("keys", 4, 0, "chords", reverb=55)
    bass = Part("bass", 33, 1, "bass", reverb=10)
    vib = Part("melody", 11, 2, "melody", reverb=70)
    dr = Part("drums", 0, 9, "drums", reverb=25, drums=True)
    swing = 0.58
    prev = None
    key_pc = KEYS[key]
    for b in range(bars):
        deg, q = prog[b % len(prog)]
        root, ivs = chord_pcs(key_pc, deg, q)
        v = voice([i for i in ivs], prev, 53, 74)
        prev = v
        t0 = b * 4
        for n in v:
            t, vel = humanize(rnd, t0, 62)
            ep.add(t + rnd.uniform(0, 0.02), 1.8, n, vel)
            t, vel = humanize(rnd, t0 + 2 + (swing - 0.5), 48)
            ep.add(t, 1.3, n, vel)
        r = 36 + (root - 36) % 12
        bass.add(t0, 1.4, r, 84)
        bass.add(t0 + 1 + swing, 0.45, r + 7 if rnd.random() < 0.5 else r, 70)
        nxt_root, _ = chord_pcs(key_pc, *prog[(b + 1) % len(prog)])
        nr = 36 + (nxt_root - 36) % 12
        bass.add(t0 + 3 + swing, 0.4, nr + (1 if nr < r else -1), 64)
        for i in range(8):  # swung 8ths
            pos = t0 + i // 2 + (swing if i % 2 else 0)
            t, vel = humanize(rnd, pos, 50 if i % 2 else 64, tj=0.01, vj=8)
            dr.add(t, 0.1, CHH, vel)
        for pos in (0, 1 + swing, 2 + swing * 0.9 if b % 2 else 2.75):
            dr.add(t0 + pos, 0.2, KICK, 92 + rnd.randint(-6, 4))
        for pos in (1, 3):
            dr.add(t0 + pos + 0.01, 0.2, SNARE, 70 + rnd.randint(-6, 6))
        if b % 2 == 1:  # sparse vibraphone answer phrase
            scale = [key_pc + s for s in PENTA_MAJ]
            for k, pos in enumerate((0.5, 1 + swing, 2.5)):
                p = 72 + (rnd.choice(scale) - 72) % 12
                vib.add(t0 + pos, 0.9, p, 55 - k * 4)
    return [ep, bass, vib, dr]


def style_acoustic(rnd, key, prog, bpm, bars):
    gtr = Part("guitar", 25, 0, "chords", reverb=35)
    bass = Part("bass", 32, 1, "bass", reverb=10)
    glock = Part("melody", 9, 2, "melody", reverb=60)
    dr = Part("drums", 0, 9, "drums", reverb=20, drums=True)
    key_pc = KEYS[key]
    pattern = [(0, "D", 88), (1, "D", 80), (1.5, "U", 62), (2.5, "U", 64), (3, "D", 82), (3.5, "U", 60)]
    for b in range(bars):
        deg, q = prog[b % len(prog)]
        root, ivs = chord_pcs(key_pc, deg, q)
        r = 40 + (root - 40) % 12  # E2..D#3
        shape = [r, r + 7, r + 12, r + 12 + (ivs[1] - ivs[0]), r + 19, r + 24]
        t0 = b * 4
        for pos, d, vel in pattern:
            notes = shape if d == "D" else list(reversed(shape[2:]))
            for k, n in enumerate(notes):
                t, v = humanize(rnd, t0 + pos + k * 0.012, vel - k * 2, tj=0.006)
                gtr.add(t, 0.45 if d == "U" else 0.9, n, v)
        rb = 36 + (root - 36) % 12
        bass.add(t0, 1.6, rb, 86)
        bass.add(t0 + 2, 1.2, rb + 7, 76)
        bass.add(t0 + 3.5, 0.4, rb + 12 if rnd.random() < 0.5 else rb + 7, 66)
        for pos in (0, 2):
            dr.add(t0 + pos, 0.2, KICK, 90)
        for pos in (1, 3):
            dr.add(t0 + pos, 0.2, CLAP, 74 + rnd.randint(-5, 5))
        for i in range(8):
            t, v = humanize(rnd, t0 + i * 0.5, 62 if i % 2 == 0 else 46, tj=0.008)
            dr.add(t, 0.1, SHAKER, v)
        if b % 4 in (1, 3):
            scale = [key_pc + s for s in PENTA_MAJ]
            for k, pos in enumerate((0, 1, 1.5, 3)):
                glock.add(t0 + pos, 0.6, 79 + (rnd.choice(scale) - 79) % 12, 50)
    return [gtr, bass, glock, dr]


def style_house(rnd, key, prog, bpm, bars):
    keys = Part("keys", 5, 0, "chords", reverb=45)
    pad = Part("pad", 89, 3, "pad", reverb=80)
    bass = Part("bass", 38, 1, "bass", reverb=5)
    dr = Part("drums", 0, 9, "drums", reverb=15, drums=True)
    key_pc = KEYS[key]
    prev = None
    for b in range(bars):
        deg, q = prog[b % len(prog)]
        root, ivs = chord_pcs(key_pc, deg, q)
        v = voice(ivs, prev, 57, 76)
        prev = v
        t0 = b * 4
        for pos in (0.5, 1.5, 3):
            for n in v:
                t, vel = humanize(rnd, t0 + pos, 74, tj=0.004)
                keys.add(t, 0.32, n, vel)
        for n in voice(ivs, None, 48, 67):
            pad.add(t0, 3.95, n, 48)
        rb = 33 + (root - 33) % 12
        for i in range(4):
            bass.add(t0 + i + 0.5, 0.38, rb + (12 if (i == 3 and b % 2) else 0), 92)
        for i in range(4):
            dr.add(t0 + i, 0.2, KICK, 108)
            dr.add(t0 + i + 0.5, 0.15, OHH, 62 + rnd.randint(-4, 4))
            dr.add(t0 + i + 0.25, 0.08, CHH, 34)
            dr.add(t0 + i + 0.75, 0.08, CHH, 38)
        for pos in (1, 3):
            dr.add(t0 + pos, 0.2, CLAP, 90)
        if b % 8 == 0:
            dr.add(t0, 1, CRASH, 70)
    return [keys, pad, bass, dr]


def style_piano(rnd, key, prog, bpm, bars):
    """Uplifting piano: bright broken chords, warm strings, a light shaker pulse."""
    pno = Part("piano", 0, 0, "chords", reverb=50)
    strings = Part("strings", 49, 1, "pad", reverb=70)
    dr = Part("drums", 0, 9, "perc_light", reverb=20, drums=True)
    key_pc = KEYS[key]
    prev = None
    for b in range(bars):
        deg, q = prog[b % len(prog)]
        root, ivs = chord_pcs(key_pc, deg, q)
        t0 = b * 4
        lb = 36 + (root - 36) % 12
        for pos in (0, 2):
            pno.add(t0 + pos, 1.9, lb, 66)
            pno.add(t0 + pos, 1.9, lb + 12, 56)
        arp = voice(ivs, prev, 64, 84)
        prev = arp
        seq = [arp[0], arp[1], arp[-1], arp[1]] * 4
        for i, n in enumerate(seq):
            t, v = humanize(rnd, t0 + i * 0.25, 58 if i % 4 == 0 else 46, tj=0.008, vj=5)
            pno.add(t, 0.4, n, v)
        for n in voice(ivs, None, 55, 72):
            strings.add(t0, 3.95, n, 48)
        for i in range(8):
            dr.add(t0 + i * 0.5, 0.1, SHAKER, 52 if i % 2 == 0 else 38)
        for pos in (0, 2):
            dr.add(t0 + pos, 0.2, KICK, 64)
    return [pno, strings, dr]


def style_gym(rnd, key, prog, bpm, bars):
    syn = Part("synth", 90, 0, "chords", reverb=35)
    strings = Part("pad", 50, 3, "pad", reverb=60)
    bass = Part("bass", 39, 1, "bass", reverb=5)
    dr = Part("drums", 0, 9, "drums", reverb=12, drums=True)
    key_pc = KEYS[key]
    prev = None
    for b in range(bars):
        deg, q = prog[b % len(prog)]
        root, ivs = chord_pcs(key_pc, deg, q)
        v = voice(ivs, prev, 55, 74)
        prev = v
        t0 = b * 4
        for i in range(8):
            if i % 2:
                for n in v:
                    syn.add(t0 + i * 0.5, 0.3, n, 70)
        for n in voice(ivs, None, 50, 69):
            strings.add(t0, 3.95, n, 50)
        rb = 28 + (root - 28) % 12
        for i in range(8):
            bass.add(t0 + i * 0.5, 0.42, rb + (12 if i == 7 else 0), 100 if i % 2 == 0 else 88)
        for i in range(4):
            dr.add(t0 + i, 0.2, KICK, 112)
        for pos in (1, 3):
            dr.add(t0 + pos, 0.2, SNARE, 100)
            dr.add(t0 + pos, 0.2, CLAP, 86)
        for i in range(16):
            dr.add(t0 + i * 0.25, 0.06, CHH, 78 if i % 4 == 2 else (52 if i % 2 else 40))
        if b % 8 == 0:
            dr.add(t0, 1, CRASH, 84)
    return [syn, strings, bass, dr]


def style_groove(rnd, key, prog, bpm, bars):
    """Smooth neo-soul / funk groove: jazz-guitar chops, Rhodes, round bass."""
    gtr = Part("guitar", 26, 0, "chords", reverb=30)
    ep = Part("keys", 4, 2, "pad", reverb=55)
    bass = Part("bass", 33, 1, "bass", reverb=5)
    dr = Part("drums", 0, 9, "drums", reverb=18, drums=True)
    key_pc = KEYS[key]
    prev = None
    for b in range(bars):
        deg, q = prog[b % len(prog)]
        root, ivs = chord_pcs(key_pc, deg, q)
        v = voice(ivs, prev, 55, 74)
        prev = v
        t0 = b * 4
        for s16 in (2, 6, 11, 14):
            for n in v[-3:]:
                t, vel = humanize(rnd, t0 + s16 * 0.25, 58, tj=0.006)
                gtr.add(t, 0.16, n, vel)
        for n in voice(ivs, None, 52, 72):
            t, vel = humanize(rnd, t0, 50)
            ep.add(t, 3.6, n, vel)
        rb = 33 + (root - 33) % 12
        for s16, iv, d, vel in ((0, 0, 0.9, 92), (6, 0, 0.35, 80), (8, 7, 0.5, 78), (11, 12, 0.2, 70),
                                (14, 10, 0.25, 72)):
            bass.add(t0 + s16 * 0.25, d, rb + iv, vel)
        for s16 in (0, 7, 10):
            dr.add(t0 + s16 * 0.25, 0.2, KICK, 96)
        for s16 in (4, 12):
            dr.add(t0 + s16 * 0.25, 0.2, SNARE, 78)
            dr.add(t0 + s16 * 0.25, 0.2, RIM, 50)
        for s16 in range(0, 16, 2):
            t, vel = humanize(rnd, t0 + s16 * 0.25, 58 if s16 % 4 == 0 else 44, tj=0.008)
            dr.add(t, 0.08, CHH, vel)
    return [gtr, ep, bass, dr]


STYLES = {
    "lofi_chill": (style_lofi, [(82, "F", [("I", "maj7"), ("vi", "min7"), ("ii", "min7"), ("V", "dom7")]),
                                (78, "Eb", [("IV", "maj7"), ("iii", "min7"), ("vi", "min7"), ("I", "maj7")]),
                                (86, "D", [("ii", "min9"), ("V", "dom7"), ("I", "maj9"), ("vi", "min7")])]),
    "soft_acoustic": (style_acoustic, [(98, "G", [("I", "maj"), ("V", "maj"), ("vi", "min"), ("IV", "maj")]),
                                       (94, "D", [("vi", "min"), ("IV", "maj"), ("I", "maj"), ("V", "maj")]),
                                       (102, "C", [("I", "maj"), ("IV", "add9"), ("vi", "min"), ("V", "maj")])]),
    "chic_house": (style_house, [(120, "C", [("vi", "min7"), ("IV", "maj7"), ("I", "maj7"), ("V", "dom7")]),
                                 (122, "Eb", [("ii", "min7"), ("V", "dom7"), ("iii", "min7"), ("vi", "min7")]),
                                 (118, "A", [("vi", "min9"), ("ii", "min7"), ("IV", "maj7"), ("V", "maj")])]),
    "elegant_piano": (style_piano, [(88, "C", [("I", "add9"), ("IV", "maj7"), ("I", "add9"), ("V", "sus2")]),
                                    (84, "D", [("I", "maj"), ("V", "maj"), ("IV", "add9"), ("IV", "maj")]),
                                    (92, "E", [("IV", "maj7"), ("V", "maj"), ("I", "add9"), ("I", "maj")])]),
    "gym_energy": (style_gym, [(126, "E", [("i", "min"), ("bVI", "maj"), ("bIII", "maj"), ("bVII", "maj")]),
                               (128, "D", [("i", "min"), ("bVII", "maj"), ("bVI", "maj"), ("bVII", "maj")]),
                               (124, "F", [("i", "min"), ("iv", "min"), ("bVI", "maj"), ("bVII", "maj")])]),
    "groove_pop": (style_groove, [(100, "D", [("ii", "min9"), ("V", "dom9")]),
                                  (104, "A", [("vi", "min9"), ("ii", "min9"), ("IV", "maj7"), ("V", "dom9")]),
                                  (98, "E", [("ii", "min9"), ("V", "dom9"), ("iii", "min7"), ("vi", "min9")])]),
}
ROLE_LUFS = {"drums": -17.0, "bass": -19.5, "chords": -18.5, "pad": -26.0, "melody": -24.5, "perc_light": -30.0}
POST = {
    "lofi_chill": "highpass=f=40,lowpass=f=7000",
    "soft_acoustic": "highpass=f=35",
    "chic_house": "highpass=f=30",
    "elegant_piano": "highpass=f=30",
    "gym_energy": "highpass=f=30",
    "groove_pop": "highpass=f=30",
}


def write_midi(parts, bpm, path):
    mid = mido.MidiFile(ticks_per_beat=PPQ)
    for p in parts:
        tr = mido.MidiTrack()
        mid.tracks.append(tr)
        tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
        ev = []
        if not p.drums:
            ev.append((0, mido.Message("program_change", channel=p.channel, program=p.program)))
        ev.append((0, mido.Message("control_change", channel=p.channel, control=91, value=p.reverb)))
        ev.append((0, mido.Message("control_change", channel=p.channel, control=7, value=110)))
        for s, d, n, v in p.notes:
            on = max(0, int(round(s * PPQ)))
            off = max(on + 1, int(round((s + d) * PPQ)))
            ev.append((on, mido.Message("note_on", channel=p.channel, note=n, velocity=v)))
            ev.append((off, mido.Message("note_off", channel=p.channel, note=n, velocity=0)))
        ev.sort(key=lambda e: (e[0], 0 if e[1].type == "note_off" else 1))
        last = 0
        for t, m in ev:
            tr.append(m.copy(time=t - last))
            last = t
    mid.save(path)


def lufs(path) -> float:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=framelog=quiet",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else -70.0


def render_track(name, style, fn, bpm, key, prog, seed):
    rnd = random.Random(seed)
    bars = int(LENGTH_S / (240 / bpm)) + 1
    parts = [p for p in fn(rnd, key, prog, bpm, bars) if p.notes]
    dur = bars * 240 / bpm
    with tempfile.TemporaryDirectory() as tmp:
        stems = []
        for p in parts:
            mid = os.path.join(tmp, f"{p.name}.mid")
            wav = os.path.join(tmp, f"{p.name}.wav")
            write_midi([p], bpm, mid)
            subprocess.run(["fluidsynth", "-ni", "-q", "-g", "0.5", "-r", "48000", "-F", wav, SF2, mid],
                           check=True, capture_output=True)
            level = lufs(wav)
            gain = max(-30.0, min(24.0, ROLE_LUFS[p.role] - level))
            stems.append((wav, gain, p.role, level))
        inputs = sum((["-i", w] for w, *_ in stems), [])
        chains = "".join(f"[{i}:a]volume={g:.2f}dB[s{i}];" for i, (_, g, _, _) in enumerate(stems))
        mix = "".join(f"[s{i}]" for i in range(len(stems)))
        out = os.path.join(OUT, f"{name}.m4a")
        graph = (f"{chains}{mix}amix=inputs={len(stems)}:normalize=0:duration=longest,"
                 f"atrim=0:{dur:.2f},{POST[style]},"
                 "acompressor=threshold=-18dB:ratio=2.5:attack=15:release=220,"
                 f"afade=t=out:st={dur - 2:.2f}:d=2,loudnorm=I=-16:TP=-1.5:LRA=9")
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", graph,
                        "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "192k", out], check=True)
    return {"file": os.path.basename(out), "style": style, "bpm": bpm, "key": key,
            "duration_s": round(dur, 1), "stems": {r: round(l, 1) for _, _, r, l in stems},
            "lufs": round(lufs(out), 1)}


def ensure_soundfont():
    if os.path.exists(SF2):
        return
    os.makedirs(os.path.dirname(SF2), exist_ok=True)
    url = "https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2"
    subprocess.run(["curl", "-sSL", "-o", SF2, url], check=True)


def main():
    import sys
    ensure_soundfont()
    only = set(sys.argv[1:])
    os.makedirs(OUT, exist_ok=True)
    lib_path = os.path.join(OUT, "library.json")
    lib = [t for t in json.load(open(lib_path)) if t["style"] not in only] if (only and os.path.exists(lib_path)) else []
    for style, (fn, variants) in STYLES.items():
        if only and style not in only:
            continue
        for k, (bpm, key, prog) in enumerate(variants, 1):
            name = f"{style}_{k}"
            info = render_track(name, style, fn, bpm, key, prog, seed=f"{name}-v1")
            lib.append(info)
            print(f"{name}: {bpm} bpm {key}, {info['duration_s']}s, {info['lufs']} LUFS, stems {info['stems']}", flush=True)
    lib.sort(key=lambda t: t["file"])
    with open(lib_path, "w") as f:
        json.dump(lib, f, indent=2)


if __name__ == "__main__":
    main()
