"""Render a scenario to MP4 (and/or keyframe stills).

Usage:
  python make_video.py ../timeline/scenario.json --out ../out/future.mp4 [--stills] [--fps 30]
"""
import argparse
import math
import subprocess
import sys
import time
from pathlib import Path

import cairo
import imageio_ffmpeg

import render
import timeline
from world import Atlas


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, t)))


def smooth_year(y0, y1, t):
    return y0 + (y1 - y0) * ease(t)


class Frames:
    """Yields (surface_a, surface_b, blend, year, caption, cap_alpha, highlight_geom, hl_alpha)."""

    def __init__(self, keyframes, atlas, fps, labels=True):
        self.kf = keyframes
        self.atlas = atlas
        self.fps = fps
        self.labels = labels
        self._base = {}

    def base(self, i):
        s = self._base.get(i)
        if s is None:
            t0 = time.time()
            s = render.render_base(self.kf[i].world, self.atlas, labels=self.labels)
            self._base[i] = s
            print(f"  keyframe {i} ({self.kf[i].year}) rendered in {time.time() - t0:.1f}s", file=sys.stderr)
        return s

    def total_seconds(self, outro):
        return sum(k.hold + k.transition + k.settle for k in self.kf) + outro

    def __iter__(self):
        fps = self.fps
        kf = self.kf
        # Intro: present day, title caption.
        n = int(kf[0].hold * fps)
        for f in range(n):
            a = 1.0 if f > fps * 0.4 else f / (fps * 0.4)
            yield self.base(0), None, 0.0, kf[0].year, (kf[0].title, kf[0].subtitle), a, None, 0.0
        for i in range(1, len(kf)):
            prev, cur = kf[i - 1], kf[i]
            # Hold: the year counts up from prev to cur; old caption fades out.
            n = int(cur.hold * fps)
            for f in range(n):
                t = f / max(1, n - 1)
                fade = max(0.0, 1.0 - f / (fps * 0.5))
                yield (self.base(i - 1), None, 0.0, smooth_year(prev.year, cur.year, t),
                       (prev.title, prev.subtitle), fade, None, 0.0)
            # Transition: crossfade to the new map with a highlight pulse on the changed tiles.
            n = int(cur.transition * fps)
            for f in range(n):
                t = f / max(1, n - 1)
                hl = 0.55 * math.sin(math.pi * t)
                yield (self.base(i - 1), self.base(i), ease(t), cur.year,
                       (cur.title, cur.subtitle), ease(t), cur.changed, hl)
            # Settle: new map, caption on, highlight fading out.
            n = int(cur.settle * fps)
            for f in range(n):
                t = f / max(1, n - 1)
                yield self.base(i), None, 0.0, cur.year, (cur.title, cur.subtitle), 1.0, cur.changed, 0.0
        # Outro: linger on the final map.
        n = int(self.outro * fps)
        for f in range(n):
            yield self.base(len(kf) - 1), None, 0.0, kf[-1].year, (kf[-1].title, kf[-1].subtitle), 1.0, None, 0.0


def compose(W, H, surf_a, surf_b, blend, year, caption, cap_alpha, hl_geom, hl_alpha, target):
    ctx = cairo.Context(target)
    ctx.set_source_surface(surf_a, 0, 0)
    ctx.paint()
    if surf_b is not None and blend > 0:
        ctx.set_source_surface(surf_b, 0, 0)
        ctx.paint_with_alpha(blend)
    if hl_geom is not None and hl_alpha > 0:
        render.draw_highlight(ctx, hl_geom, hl_alpha)
    render.draw_hud(ctx, W, H, year, caption[0], caption[1], cap_alpha)
    target.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--out", default=None)
    ap.add_argument("--stills", action="store_true", help="write one PNG per keyframe")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--outro", type=float, default=6.0)
    ap.add_argument("--max-seconds", type=float, default=None, help="truncate output (for tests)")
    ap.add_argument("--labels", choices=["on", "off"], default=None,
                    help="country name labels (default: scenario's \"labels\" key, else on)")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    atlas = Atlas(args.width, args.height)
    W, H = atlas.meta["width"], atlas.meta["height"]
    sc, kf = timeline.build(args.scenario, atlas)
    print(f"{len(kf) - 1} events; {sum(k.hold + k.transition + k.settle for k in kf) + args.outro:.0f}s total",
          file=sys.stderr)

    labels = sc.get("labels", True) if args.labels is None else args.labels == "on"
    frames = Frames(kf, atlas, args.fps, labels=labels)
    frames.outro = args.outro
    out_dir = Path(args.out).parent if args.out else Path(__file__).resolve().parent.parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.stills:
        sd = out_dir / "stills"
        sd.mkdir(exist_ok=True)
        target = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        for i, k in enumerate(kf):
            compose(W, H, frames.base(i), None, 0, k.year, (k.title, k.subtitle), 1.0, None, 0.0, target)
            p = sd / f"{i:02d}_{int(k.year)}.png"
            target.write_to_png(str(p))
            print(f"  wrote {p}", file=sys.stderr)

    if not args.out:
        return

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
           "-r", str(args.fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    target = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    limit = int(args.max_seconds * args.fps) if args.max_seconds else None
    t0 = time.time()
    n = 0
    for spec in frames:
        compose(W, H, *spec, target)
        proc.stdin.write(target.get_data())
        n += 1
        if n % (args.fps * 10) == 0:
            print(f"  {n / args.fps:.0f}s rendered ({n / (time.time() - t0):.1f} fps)", file=sys.stderr)
        if limit and n >= limit:
            break
    proc.stdin.close()
    proc.wait()
    print(f"wrote {args.out}: {n} frames, {n / args.fps:.1f}s in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
