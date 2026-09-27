"""Render a scenario to MP4 (and/or keyframe stills).

Usage:
  python make_video.py ../timeline/scenario.json --out ../out/future.mp4 [--stills] [--fps 60]

Transitions between keyframes are animated per acquiring country:
  advance  the acquirer's colour sweeps out from its existing border across the
           taken land, with a moving border line (wars, annexations, retreats)
  bloom    a new state grows outward from its heartland (secessions)
  fade     cross-fade over the changed area (unions, renames)
The mode is picked automatically (advance if the acquirer already borders the
land, else bloom; unions of many whole countries fade) and can be forced per
change with "anim": "advance" | "bloom" | "fade".
"""
import argparse
import math
import subprocess
import sys
import time
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


def smooth_year(y0, y1, t):
    return y0 + (y1 - y0) * ease(t)


def _slim(geom, tol=3.0, min_area=30.0):
    """Simplify and drop specks (tiny islands) so per-frame buffers stay cheap."""
    g = geom.simplify(tol)
    parts = list(g.geoms) if hasattr(g, "geoms") else [g]
    parts = [p for p in parts if p.area >= min_area]
    if not parts:
        return g
    return shapely.multipolygons(parts) if len(parts) > 1 else parts[0]


class Sweep:
    """Per-acquirer animated mask for one transition."""

    def __init__(self, group_geom, source_geom, mode):
        self.group = group_geom
        # Cheap envelope for clipping the sweep: outside the group the old and new
        # frames are identical, so the mask only needs to be exact-ish, not exact.
        self.hull = _slim(group_geom).buffer(3.0, quad_segs=1)
        self.mode = mode
        self.src = None
        self.D = 1.0
        if mode == "advance" and source_geom is not None and not source_geom.is_empty:
            # Only the part of the source near the land matters for the sweep.
            pts = shapely.get_coordinates(group_geom)
            step = max(1, len(pts) // 4000)
            sample = shapely.points(pts[::step])
            d = shapely.distance(source_geom, sample)
            self.D = float(d.max()) + 2.0
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
        return self.src.buffer(d, quad_segs=2).intersection(self.hull)


def build_sweeps(prev_kf, cur_kf, atlas):
    """Group the changed tiles by new owner and decide how each group animates."""
    groups = {}
    for tid in cur_kf.changed_ids:
        groups.setdefault(cur_kf.world.owner[tid], []).append(tid)
    sweeps = []
    forced = cur_kf.anim or {}
    for cid, tids in groups.items():
        g = atlas.union(tids)
        had = prev_kf.world.tiles_of(cid)
        mode = forced.get(cid)
        if mode is None:
            if not had:
                mode = "bloom"
            else:
                src = prev_kf.world.shape(cid)
                # A union swallowing whole countries fades; an advance needs a shared front.
                mode = "advance" if src.buffer(3).intersects(g) and g.area < 6 * src.area else "fade"
        src = prev_kf.world.shape(cid) if had else None
        sweeps.append(Sweep(g, src, mode))
    return sweeps


class Frames:
    def __init__(self, keyframes, atlas, fps, labels=True, outro=6.0):
        self.kf = keyframes
        self.atlas = atlas
        self.fps = fps
        self.labels = labels
        self.outro = outro
        self._base = {}

    def base(self, i):
        s = self._base.get(i)
        if s is None:
            t0 = time.time()
            s = render.render_base(self.kf[i].world, self.atlas, labels=self.labels)
            self._base[i] = s
            print(f"  keyframe {i} ({self.kf[i].year}) rendered in {time.time() - t0:.1f}s", file=sys.stderr)
        return s

    def __iter__(self):
        fps, kf = self.fps, self.kf
        n = int(kf[0].hold * fps)
        for f in range(n):
            a = min(1.0, f / (fps * 0.4))
            yield dict(a=self.base(0), year=kf[0].year, caption=(kf[0].title, kf[0].subtitle), cap_alpha=a)
        for i in range(1, len(kf)):
            prev, cur = kf[i - 1], kf[i]
            n = int(cur.hold * fps)
            for f in range(n):
                t = f / max(1, n - 1)
                fade = max(0.0, 1.0 - f / (fps * 0.5))
                yield dict(a=self.base(i - 1), year=smooth_year(prev.year, cur.year, t),
                           caption=(prev.title, prev.subtitle), cap_alpha=fade)
            sweeps = build_sweeps(prev, cur, self.atlas) if cur.changed_ids else []
            n = int(cur.transition * fps)
            for f in range(n):
                t = f / max(1, n - 1)
                yield dict(a=self.base(i - 1), b=self.base(i), t=t, sweeps=sweeps, year=cur.year,
                           caption=(cur.title, cur.subtitle), cap_alpha=ease(min(1.0, t * 2)),
                           hl=cur.changed, hl_alpha=0.28 * math.sin(math.pi * t))
            n = int(cur.settle * fps)
            for f in range(n):
                yield dict(a=self.base(i), year=cur.year, caption=(cur.title, cur.subtitle), cap_alpha=1.0)
        n = int(self.outro * fps)
        for f in range(n):
            yield dict(a=self.base(len(kf) - 1), year=kf[-1].year, caption=(kf[-1].title, kf[-1].subtitle), cap_alpha=1.0)


def compose(W, H, spec, target):
    S = W / 1920.0
    ctx = cairo.Context(target)
    ctx.set_source_surface(spec["a"], 0, 0)
    ctx.paint()
    if "b" in spec:
        t = spec["t"]
        for sw in spec["sweeps"]:
            m = sw.mask(t)
            if m is None or m.is_empty:
                continue
            ctx.save()
            ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            render.add_path(ctx, m)
            ctx.clip()
            ctx.set_source_surface(spec["b"], 0, 0)
            if sw.mode == "fade":
                ctx.paint_with_alpha(ease(t))
            else:
                ctx.paint()
            ctx.restore()
            if sw.mode != "fade" and t < 1.0:
                # Moving front line.
                ctx.save()
                ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
                render.add_path(ctx, sw.group)
                ctx.clip()
                render.add_path(ctx, m)
                ctx.set_source_rgb(*render.rgb(render.STYLE["border"]))
                ctx.set_line_width(render.STYLE["border_width"] * S)
                ctx.stroke()
                ctx.restore()
        if spec.get("hl") is not None and spec.get("hl_alpha", 0) > 0:
            render.draw_highlight(ctx, spec["hl"], spec["hl_alpha"])
    cap = spec["caption"]
    render.draw_hud(ctx, W, H, spec["year"], cap[0], cap[1], spec.get("cap_alpha", 1.0))
    target.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--out", default=None)
    ap.add_argument("--stills", action="store_true", help="write one PNG per keyframe")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--outro", type=float, default=6.0)
    ap.add_argument("--max-seconds", type=float, default=None, help="truncate output (for tests)")
    ap.add_argument("--start-seconds", type=float, default=0.0, help="skip output before this time")
    ap.add_argument("--labels", choices=["on", "off"], default=None,
                    help="country name labels (default: scenario's \"labels\" key, else on)")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--crf", type=int, default=16)
    args = ap.parse_args()

    atlas = Atlas(args.width, args.height)
    W, H = atlas.meta["width"], atlas.meta["height"]
    sc, kf = timeline.build(args.scenario, atlas)
    total = sum(k.hold + k.transition + k.settle for k in kf) + args.outro
    print(f"{len(kf) - 1} events; {total:.0f}s total", file=sys.stderr)

    labels = sc.get("labels", True) if args.labels is None else args.labels == "on"
    frames = Frames(kf, atlas, args.fps, labels=labels, outro=args.outro)
    out_dir = Path(args.out).parent if args.out else Path(__file__).resolve().parent.parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.stills:
        sd = out_dir / "stills"
        sd.mkdir(exist_ok=True)
        target = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        for i, k in enumerate(kf):
            compose(W, H, dict(a=frames.base(i), year=k.year, caption=(k.title, k.subtitle)), target)
            p = sd / f"{i:02d}_{int(k.year)}.png"
            target.write_to_png(str(p))
        print(f"  wrote {len(kf)} stills to {sd}", file=sys.stderr)

    if not args.out:
        return

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
           "-r", str(args.fps), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    target = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    skip = int(args.start_seconds * args.fps)
    limit = int(args.max_seconds * args.fps) if args.max_seconds else None
    t0 = time.time()
    n = 0
    for idx, spec in enumerate(frames):
        if idx < skip:
            continue
        compose(W, H, spec, target)
        proc.stdin.write(target.get_data())
        n += 1
        if n % (args.fps * 20) == 0:
            print(f"  {n / args.fps:.0f}s rendered ({n / (time.time() - t0):.1f} fps)", file=sys.stderr)
        if limit and n >= limit:
            break
    proc.stdin.close()
    proc.wait()
    print(f"wrote {args.out}: {n} frames, {n / args.fps:.1f}s in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
