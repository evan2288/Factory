"""Render a scenario to MP4 (and/or keyframe stills) with continuous, overlapping change.

Usage:
  python make_video.py ../timeline/scenario.json --out ../out/future.mp4 [--stills] [--fps 60]

Time model
  The scenario's "tempo" maps video seconds to calendar years, e.g.
      "tempo": [[2025, 0], [2100, 60], [2300, 150], [3000, 300]]
  Each event has a "year" (start) and "years" (how long the change takes).
  Every event whose span covers the current year animates at the same time.

Animation per acquiring country
  advance  the acquirer's colour sweeps out from its existing border across the
           taken land behind a moving border line (wars, annexations, retreats)
  bloom    a new state grows outward from its heartland (secessions)
  fade     cross-fade over the changed area (unions, renames)
Picked automatically; force with "anim": "advance" | "bloom" | "fade" on a change.
"""
import argparse
import bisect
import math
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

import cairo
import imageio_ffmpeg
import shapely
from shapely.geometry import Point
from shapely.ops import polylabel

import render
import timeline
from world import Atlas


def ease(t):
    t = min(1.0, max(0.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def _slim(geom, tol=3.0, min_area=30.0):
    """Simplify and drop specks (tiny islands) so per-frame buffers stay cheap."""
    g = geom.simplify(tol)
    parts = list(g.geoms) if hasattr(g, "geoms") else [g]
    parts = [p for p in parts if p.area >= min_area]
    if not parts:
        return g
    return shapely.multipolygons(parts) if len(parts) > 1 else parts[0]


class Sweep:
    """Per-acquirer animated mask for one event."""

    def __init__(self, group_geom, source_geom, mode):
        self.group = group_geom
        self.hull = _slim(group_geom).buffer(3.0, quad_segs=1)
        self.mode = mode
        self.src = None
        self.D = 1.0
        if mode == "advance" and source_geom is not None and not source_geom.is_empty:
            pts = shapely.get_coordinates(group_geom)
            step = max(1, len(pts) // 4000)
            sample = shapely.points(pts[::step])
            self.D = float(shapely.distance(source_geom, sample).max()) + 2.0
            self.src = _slim(source_geom.intersection(_slim(group_geom).buffer(self.D + 8, quad_segs=1)))
            if self.src.is_empty:
                self.mode = "bloom"
        if self.mode == "bloom":
            parts = list(group_geom.geoms) if hasattr(group_geom, "geoms") else [group_geom]
            big = max(parts, key=lambda p: p.area)
            try:
                c = polylabel(big, tolerance=1.0)
            except Exception:
                c = big.representative_point()
            self.src = Point(c.x, c.y)
            pts = shapely.get_coordinates(group_geom)
            step = max(1, len(pts) // 4000)
            self.D = float(shapely.distance(self.src, shapely.points(pts[::step])).max()) + 2.0

    def mask(self, t):
        if self.mode == "fade" or t >= 1.0:
            return self.group
        d = self.D * ease(t)
        if d <= 0.5:
            return None
        return self.src.buffer(d, quad_segs=8 if self.mode == "bloom" else 2).intersection(self.hull)


def build_sweeps(prev_kf, cur_kf, atlas):
    groups = {}
    for tid in cur_kf.changed_ids:
        groups.setdefault(cur_kf.world.owner[tid], []).append(tid)
    sweeps = []
    forced = cur_kf.anim or {}
    for cid, tids in groups.items():
        g = atlas.union(tids)
        had = prev_kf.world.tiles_of(cid)
        mode = forced.get(cid)
        src = prev_kf.world.shape(cid) if had else None
        if mode is None:
            if not had:
                mode = "bloom"
            else:
                mode = "advance" if src.buffer(3).intersects(g) and g.area < 6 * src.area else "fade"
        sweeps.append(Sweep(g, src, mode))
    return sweeps


class Tempo:
    """Piecewise-linear map between video seconds and calendar years."""

    def __init__(self, anchors):
        self.years = [a[0] for a in anchors]
        self.secs = [a[1] for a in anchors]

    def year_at(self, s):
        i = bisect.bisect_right(self.secs, s) - 1
        i = max(0, min(i, len(self.secs) - 2))
        y0, y1, s0, s1 = self.years[i], self.years[i + 1], self.secs[i], self.secs[i + 1]
        return y0 + (y1 - y0) * (s - s0) / (s1 - s0)

    def seconds_at(self, y):
        i = bisect.bisect_right(self.years, y) - 1
        i = max(0, min(i, len(self.years) - 2))
        y0, y1, s0, s1 = self.years[i], self.years[i + 1], self.secs[i], self.secs[i + 1]
        return s0 + (s1 - s0) * (y - y0) / (y1 - y0)

    @property
    def total(self):
        return self.secs[-1]


class Renderer:
    def __init__(self, keyframes, atlas, labels=True, cache=10):
        self.kf = keyframes
        self.atlas = atlas
        self.labels = labels
        self._base = OrderedDict()
        self._cache = cache
        self._sweeps = {}

    def base(self, i):
        s = self._base.get(i)
        if s is None:
            t0 = time.time()
            s = render.render_base(self.kf[i].world, self.atlas, labels=self.labels)
            self._base[i] = s
            if len(self._base) > self._cache:
                self._base.popitem(last=False)
            print(f"  keyframe {i} ({self.kf[i].year}) rendered in {time.time() - t0:.1f}s", file=sys.stderr)
        else:
            self._base.move_to_end(i)
        return s

    def sweeps(self, i):
        s = self._sweeps.get(i)
        if s is None:
            s = build_sweeps(self.kf[i - 1], self.kf[i], self.atlas) if self.kf[i].changed_ids else []
            self._sweeps[i] = s
            for k in [k for k in self._sweeps if k < i - 40]:
                del self._sweeps[k]
        return s

    def compose(self, W, H, year, target, caption=None, cap_alpha=1.0):
        """Draw the world at fractional `year`: completed events fully, in-progress ones mid-sweep."""
        S = W / 1920.0
        kf = self.kf
        # j = number of leading events that are fully complete.
        j = 0
        while j + 1 < len(kf) and kf[j + 1].end <= year:
            j += 1
        ctx = cairo.Context(target)
        ctx.set_source_surface(self.base(j), 0, 0)
        ctx.paint()
        i = j + 1
        while i < len(kf) and kf[i].year <= year:
            ev = kf[i]
            t = 1.0 if ev.end <= ev.year else (year - ev.year) / (ev.end - ev.year)
            for sw in self.sweeps(i):
                m = sw.mask(t)
                if m is None or m.is_empty:
                    continue
                ctx.save()
                ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
                render.add_path(ctx, m)
                ctx.clip()
                ctx.set_source_surface(self.base(i), 0, 0)
                if sw.mode == "fade" and t < 1.0:
                    ctx.paint_with_alpha(ease(t))
                else:
                    ctx.paint()
                ctx.restore()
                if sw.mode != "fade" and t < 1.0:
                    ctx.save()
                    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
                    render.add_path(ctx, sw.group)
                    ctx.clip()
                    render.add_path(ctx, m)
                    ctx.set_source_rgb(*render.rgb(render.STYLE["border"]))
                    ctx.set_line_width(render.STYLE["border_width"] * S)
                    ctx.stroke()
                    ctx.restore()
            if t < 1.0 and ev.changed is not None:
                render.draw_highlight(ctx, ev.changed, 0.22 * math.sin(math.pi * t))
            i += 1
        if caption:
            render.draw_hud(ctx, W, H, year, caption[0], caption[1], cap_alpha)
        else:
            render.draw_hud(ctx, W, H, year, None, None, 0.0)
        target.flush()


def caption_at(kf, tempo, year, sec, fade_in=0.4, hold=4.0):
    """Most recently started event's caption, faded in and out in video seconds."""
    idx = 0
    for i in range(1, len(kf)):
        if kf[i].year <= year:
            idx = i
    ev = kf[idx]
    started = tempo.seconds_at(ev.year) if idx else 0.0
    age = sec - started
    if idx == 0:
        a = 1.0 if age < hold else max(0.0, 1 - (age - hold) / 0.6)
        return (ev.title, ev.subtitle), a
    a = min(1.0, age / fade_in)
    nxt = tempo.seconds_at(kf[idx + 1].year) if idx + 1 < len(kf) else 1e9
    life = min(hold, max(1.2, nxt - started))
    if age > life:
        a = max(0.0, 1 - (age - life) / 0.5)
    return (ev.title, ev.subtitle), a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--out", default=None)
    ap.add_argument("--stills", action="store_true", help="write one PNG per keyframe")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--outro", type=float, default=6.0)
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--start-seconds", type=float, default=0.0)
    ap.add_argument("--labels", choices=["on", "off"], default=None)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--crf", type=int, default=16)
    args = ap.parse_args()

    atlas = Atlas(args.width, args.height)
    W, H = atlas.meta["width"], atlas.meta["height"]
    sc, kf = timeline.build(args.scenario, atlas)
    tempo = Tempo(sc["tempo"])
    intro = sc.get("intro_seconds", 3.0)
    total = intro + tempo.total + args.outro
    print(f"{len(kf) - 1} events; {total:.0f}s total", file=sys.stderr)

    labels = sc.get("labels", True) if args.labels is None else args.labels == "on"
    rd = Renderer(kf, atlas, labels=labels)
    out_dir = Path(args.out).parent if args.out else Path(__file__).resolve().parent.parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)

    if args.stills:
        sd = out_dir / "stills"
        sd.mkdir(exist_ok=True)
        for i, k in enumerate(kf):
            rd.compose(W, H, k.end + 1e-6, target, (k.title, k.subtitle), 1.0)
            target.write_to_png(str(sd / f"{i:03d}_{int(k.year)}.png"))
        print(f"  wrote {len(kf)} stills to {sd}", file=sys.stderr)

    if not args.out:
        return

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
           "-r", str(args.fps), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nframes = int(total * args.fps)
    skip = int(args.start_seconds * args.fps)
    limit = int(args.max_seconds * args.fps) if args.max_seconds else None
    t0 = time.time()
    n = 0
    for f in range(skip, nframes):
        sec = f / args.fps
        if sec < intro:
            year = kf[0].year
            cap, a = (kf[0].title, kf[0].subtitle), min(1.0, sec / 0.5)
        else:
            s = min(sec - intro, tempo.total)
            year = tempo.year_at(s)
            cap, a = caption_at(kf, tempo, year, s)
            if sec - intro > tempo.total:
                cap, a = (kf[-1].title, kf[-1].subtitle), 1.0
        rd.compose(W, H, year, target, cap, a)
        proc.stdin.write(target.get_data())
        n += 1
        if n % (args.fps * 20) == 0:
            print(f"  {sec:.0f}s / {total:.0f}s ({n / (time.time() - t0):.1f} fps)", file=sys.stderr)
        if limit and n >= limit:
            break
    proc.stdin.close()
    proc.wait()
    print(f"wrote {args.out}: {n} frames, {n / args.fps:.1f}s in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
