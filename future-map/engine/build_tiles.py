"""Preprocess Natural Earth 10m admin-1 provinces into a fixed tile set.

Every future border in the video is a union of these tiles, so borders can only
ever fall on real present-day international or provincial lines. Tiles are
projected once, snapped to a sub-pixel grid (so neighbours share identical
edges) and cached to disk.

Usage: python build_tiles.py [--width 1920] [--height 1080]
"""
import argparse
import json
import pickle
import sys
from pathlib import Path

from pyproj import Transformer
from shapely import set_precision
from shapely.geometry import shape
from shapely.ops import transform
from shapely.validation import make_valid

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
CACHE = HERE.parent / "cache"

# Map extent: drop Antarctica and the far south so the inhabited world fills the frame.
LAT_MIN, LAT_MAX = -56.0, 84.0
GRID = 1 / 8  # pixel snapping grid; shared vertices land on the same point


def project_fn(width, height, margin_x=20, hud_h=0):
    """Return (fn, meta) mapping lon/lat -> pixel coords in a Robinson projection."""
    tr = Transformer.from_crs("EPSG:4326", "+proj=robin", always_xy=True)
    # Robinson bounding box for the chosen latitude band.
    xs, ys = [], []
    for lon in (-180, 180):
        for lat in (LAT_MIN, LAT_MAX, 0):
            x, y = tr.transform(lon, lat)
            xs.append(x)
            ys.append(y)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    avail_w = width - 2 * margin_x
    avail_h = height - hud_h
    scale = min(avail_w / (x1 - x0), avail_h / (y1 - y0))
    map_w, map_h = (x1 - x0) * scale, (y1 - y0) * scale
    off_x = (width - map_w) / 2
    off_y = (avail_h - map_h) / 2

    def fn(lon, lat):
        x, y = tr.transform(lon, lat)
        return (x - x0) * scale + off_x, (y1 - y) * scale + off_y

    meta = dict(width=width, height=height, scale=scale, off_x=off_x, off_y=off_y,
                map_w=map_w, map_h=map_h, x0=x0, y1=y1)
    return fn, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--hud", type=int, default=0, help="pixels reserved at bottom")
    args = ap.parse_args()

    fn, meta = project_fn(args.width, args.height, hud_h=args.hud)

    print("loading admin-1 ...", file=sys.stderr)
    a1 = json.load(open(DATA / "ne_10m_admin_1_states_provinces.geojson"))
    a0 = json.load(open(DATA / "ne_50m_admin_0_countries.geojson"))

    # adm0_a3 -> sovereign grouping and display names, from admin-0.
    sov_of = {}
    name_of = {}
    for f in a0["features"]:
        p = f["properties"]
        sov_of[p["ADM0_A3"]] = p["SOV_A3"]
        name_of[p["ADM0_A3"]] = p["ADMIN"]
        name_of.setdefault(p["SOV_A3"], p["SOVEREIGNT"])

    tiles = {}
    skipped = 0
    for f in a1["features"]:
        p = f["properties"]
        if p["adm0_a3"] == "ATA" or p.get("admin") == "Antarctica":
            continue
        g = shape(f["geometry"])
        if g.is_empty:
            skipped += 1
            continue
        g = transform(fn, g)
        g = set_precision(make_valid(g), GRID)
        if g.is_empty:
            skipped += 1
            continue
        tid = p["adm1_code"]
        tiles[tid] = dict(
            id=tid,
            geom=g.wkb,
            admin=p["admin"],
            adm0=p["adm0_a3"],
            sov=sov_of.get(p["adm0_a3"], p["adm0_a3"]),
            name=p.get("name_en") or p.get("name") or "",
            alt=p.get("name") or "",
            region=p.get("region") or "",
            type=p.get("type_en") or "",
            area=g.area,
        )

    # Country label anchors from admin-0 (LABEL_X/Y), projected.
    labels = {}
    for f in a0["features"]:
        p = f["properties"]
        if p.get("LABEL_X") is not None:
            labels[p["ADM0_A3"]] = fn(p["LABEL_X"], p["LABEL_Y"])

    lakes = []
    try:
        lk = json.load(open(DATA / "ne_50m_lakes.geojson"))
        for f in lk["features"]:
            if (f["properties"].get("scalerank") or 9) <= 3:
                g = transform(fn, shape(f["geometry"]))
                if not g.is_empty:
                    lakes.append(g.wkb)
    except FileNotFoundError:
        pass

    CACHE.mkdir(exist_ok=True)
    out = CACHE / f"tiles_{args.width}x{args.height}.pkl"
    with open(out, "wb") as fh:
        pickle.dump(dict(meta=meta, tiles=tiles, names=name_of, labels=labels, lakes=lakes), fh)
    print(f"wrote {out}: {len(tiles)} tiles, {skipped} skipped, {len(lakes)} lakes", file=sys.stderr)


if __name__ == "__main__":
    main()
