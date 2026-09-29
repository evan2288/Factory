"""Add the title to the raw covers and encode the silent preview videos.

Usage: python3 scripts/finish-assets.py <outdir>
Needs Pillow and ffmpeg on PATH.
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

out = sys.argv[1] if len(sys.argv) > 1 else "assets-out"
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def font(size):
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def title_cover(src, dst, size):
    w, h = size
    im = Image.open(src).convert("RGB").resize(size, Image.LANCZOS)
    # Darken the lower third so the title reads on any background.
    grad = Image.new("L", (1, h))
    for y in range(h):
        grad.putpixel((0, y), int(255 * max(0.0, (y / h - 0.45)) * 1.4))
    grad = grad.resize((w, h))
    im = Image.composite(Image.new("RGB", size, (0, 0, 0)), im, grad.point(lambda v: min(255, v)))
    im = Image.blend(im, Image.open(src).convert("RGB").resize(size, Image.LANCZOS), 0.35)

    text = "CURFEW"
    fsize = int(w * (0.19 if w > h else 0.2))
    f = font(fsize)
    spacing = int(fsize * 0.22)
    widths = [f.getbbox(c)[2] for c in text]
    total = sum(widths) + spacing * (len(text) - 1)
    while total > w * 0.92:
        fsize = int(fsize * 0.95)
        f = font(fsize)
        spacing = int(fsize * 0.22)
        widths = [f.getbbox(c)[2] for c in text]
        total = sum(widths) + spacing * (len(text) - 1)
    x = (w - total) // 2
    y = int(h * (0.68 if w > h else 0.72))

    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    d = ImageDraw.Draw(im)
    cx = x
    for c, cw in zip(text, widths):
        gd.text((cx, y), c, font=f, fill=(190, 30, 30, 255))
        cx += cw + spacing
    glow = glow.filter(ImageFilter.GaussianBlur(fsize * 0.18))
    im = Image.alpha_composite(im.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(im)
    cx = x
    for c, cw in zip(text, widths):
        d.text((cx, y), c, font=f, fill=(206, 198, 176))
        cx += cw + spacing
    im.save(dst, quality=95)
    print("wrote", dst, size)


title_cover(f"{out}/cover-landscape-raw.png", f"{out}/cover-landscape-1920x1080.png", (1920, 1080))
title_cover(f"{out}/cover-portrait-raw.png", f"{out}/cover-portrait-800x1200.png", (800, 1200))
title_cover(f"{out}/cover-square-raw.png", f"{out}/cover-square-800x800.png", (800, 800))


def encode(frames_dir, cover, dst, size):
    # First frame is the cover (portal requirement), held for half a second, then the gameplay frames.
    w, h = size
    cover_frame = f"{out}/_cover_{w}x{h}.png"
    Image.open(cover).convert("RGB").resize(size, Image.LANCZOS).save(cover_frame)
    concat = f"{out}/_list_{w}x{h}.txt"
    with open(concat, "w") as fh:
        for _ in range(6):
            fh.write(f"file '{os.path.abspath(cover_frame)}'\n")
        for name in sorted(os.listdir(frames_dir)):
            fh.write(f"file '{os.path.abspath(os.path.join(frames_dir, name))}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-r", "12", "-f", "concat", "-safe", "0", "-i", concat,
        "-vf", f"minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:vsbmc=1,scale={w}:{h}:flags=lanczos,unsharp=5:5:0.4,format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-movflags", "+faststart", "-an", dst,
    ], check=True)
    print("wrote", dst, os.path.getsize(dst) // 1024, "KB")


encode(f"{out}/frames-land", f"{out}/cover-landscape-1920x1080.png", f"{out}/preview-landscape-1920x1080.mp4", (1920, 1080))
encode(f"{out}/frames-port", f"{out}/cover-portrait-800x1200.png", f"{out}/preview-portrait-1080x1620.mp4", (1080, 1620))
