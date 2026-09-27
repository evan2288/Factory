"""World state: which country owns which tile, and the derived geometry.

A `World` is a dict tile_id -> country_id plus a registry of countries
(name, colour). Country shapes are unions of their tiles, cached by tile set,
so an unchanged country renders as exactly the same pixels frame after frame.
"""
import colorsys
import pickle
import re
from pathlib import Path

from shapely import STRtree, from_wkb, unary_union
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import polylabel

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / "cache"

# Muted-but-distinct political-map palette (hex). Greedy colouring picks from it.
PALETTE = [
    "#e3a857", "#7fb27a", "#c9736a", "#7f9fcf", "#b98bc9", "#d9c55f",
    "#6fbcb3", "#d48fb2", "#a3b86c", "#cf9b7d", "#8ea8b0", "#e0b46e",
    "#8fbf8f", "#c78a92", "#9aa7d6", "#d6a65f",
]


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


class Country:
    __slots__ = ("id", "name", "color", "label_hint", "style")

    def __init__(self, cid, name, color=None, label_hint=None, style="normal"):
        self.id = cid
        self.name = name
        self.color = color
        self.label_hint = label_hint
        self.style = style      # "normal" or "rebel" (civil-war faction: hatched, dashed border)

    def __repr__(self):
        return f"Country({self.id!r}, {self.name!r})"


class Atlas:
    """Immutable tile geometry + lookup helpers, loaded from the build cache."""

    def __init__(self, width=1920, height=1080):
        with open(CACHE / f"tiles_{width}x{height}.pkl", "rb") as fh:
            d = pickle.load(fh)
        self.meta = d["meta"]
        self.names = d["names"]
        self.label_anchor = d["labels"]
        self.lakes = [from_wkb(w) for w in d["lakes"]]
        self.tiles = {}
        self.geom = {}
        for tid, t in d["tiles"].items():
            self.geom[tid] = from_wkb(t["geom"])
            self.tiles[tid] = t
        self._by_admin = {}
        for tid, t in self.tiles.items():
            self._by_admin.setdefault(_norm(t["admin"]), []).append(tid)
        self._by_adm0 = {}
        for tid, t in self.tiles.items():
            self._by_adm0.setdefault(t["adm0"], []).append(tid)
        self._union_cache = {}
        self.land = None

    # ---- tile selection for timeline authoring -------------------------------
    def tiles_of_admin(self, admin):
        key = _norm(admin)
        if key in self._by_admin:
            return list(self._by_admin[key])
        if admin in self._by_adm0:
            return list(self._by_adm0[admin])
        raise KeyError(f"unknown country: {admin!r}")

    def select(self, admin, provinces=None, regions=None, exclude=None):
        """Tiles of `admin`, optionally filtered by province names and/or region names."""
        ids = self.tiles_of_admin(admin)
        if provinces is None and regions is None:
            chosen = list(ids)
        else:
            want_p = {_norm(p) for p in (provinces or [])}
            want_r = {_norm(r) for r in (regions or [])}
            chosen, found_p, found_r = [], set(), set()
            for tid in ids:
                t = self.tiles[tid]
                keys = {_norm(t["name"]), _norm(t["alt"])}
                if keys & want_p:
                    chosen.append(tid)
                    found_p |= keys & want_p
                elif _norm(t["region"]) in want_r:
                    chosen.append(tid)
                    found_r.add(_norm(t["region"]))
            missing = (want_p - found_p) | (want_r - found_r)
            if missing:
                raise KeyError(f"{admin}: no province/region matching {sorted(missing)}")
        if exclude:
            ex = {_norm(e) for e in exclude}
            chosen = [tid for tid in chosen
                      if not ({_norm(self.tiles[tid]["name"]), _norm(self.tiles[tid]["alt"]),
                               _norm(self.tiles[tid]["region"])} & ex)]
        return chosen

    def union(self, tile_ids):
        key = frozenset(tile_ids)
        g = self._union_cache.get(key)
        if g is None:
            g = unary_union([self.geom[t] for t in key]) if key else Polygon()
            self._union_cache[key] = g
        return g

    def land_union(self):
        if self.land is None:
            self.land = unary_union(list(self.geom.values()))
        return self.land


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _color_dist(a, b):
    """Perceptual-ish distance in [0, ~1]: hue difference dominates, lightness helps."""
    ra, ga, ba = _hex_to_rgb(a)
    rb, gb, bb = _hex_to_rgb(b)
    ha, la, sa = colorsys.rgb_to_hls(ra, ga, ba)
    hb, lb, sb = colorsys.rgb_to_hls(rb, gb, bb)
    dh = abs(ha - hb)
    dh = min(dh, 1 - dh) * 2          # 0..1
    return 0.75 * dh + 0.25 * abs(la - lb) * 2 + 0.1 * abs(sa - sb)


def _shift(hexcolor, k):
    """k-th fallback shade when the palette is exhausted locally."""
    r, g, b = _hex_to_rgb(hexcolor)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h = (h + 0.07 * k) % 1.0
    l = min(0.8, max(0.35, l + (0.06 if k % 2 else -0.06)))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


class World:
    def __init__(self, atlas: Atlas):
        self.atlas = atlas
        self.owner = {}       # tile_id -> country_id
        self.countries = {}   # country_id -> Country
        self._shape_cache = {}

    # ---- construction ---------------------------------------------------------
    @classmethod
    def present_day(cls, atlas: Atlas, group_dependencies=True):
        """Every admin-0 unit is its own country (so Greenland keeps its name);
        with group_dependencies, dependencies inherit their sovereign's colour."""
        w = cls(atlas)
        sov = {}
        for tid, t in atlas.tiles.items():
            cid = t["adm0"]
            w.owner[tid] = cid
            sov[cid] = t["sov"]
            if cid not in w.countries:
                w.countries[cid] = Country(cid, atlas.names.get(cid, cid), label_hint=cid)
        w.assign_colors()
        if group_dependencies:
            # sovereign id -> the admin-0 id that carries the sovereign's own territory
            home = {}
            for cid, s in sov.items():
                if cid == s or atlas.names.get(cid) == atlas.names.get(s):
                    home[s] = cid
            for cid, s in sov.items():
                if cid != s and s in home and home[s] in w.countries:
                    w.countries[cid].color = w.countries[home[s]].color
        return w

    def copy(self):
        w = World(self.atlas)
        w.owner = dict(self.owner)
        w.countries = {k: Country(c.id, c.name, c.color, c.label_hint, c.style) for k, c in self.countries.items()}
        w._shape_cache = self._shape_cache  # shared: keyed by tile set, so safe
        return w

    # ---- queries --------------------------------------------------------------
    def tiles_of(self, cid):
        return [t for t, o in self.owner.items() if o == cid]

    def shape(self, cid):
        return self.atlas.union(self.tiles_of(cid))

    def live_countries(self):
        live = set(self.owner.values())
        return [c for c in self.countries.values() if c.id in live]

    def adjacency(self):
        """country_id -> set of neighbouring country_ids (sharing an edge)."""
        live = self.live_countries()
        shapes = [self.shape(c.id) for c in live]
        tree = STRtree(shapes)
        adj = {c.id: set() for c in live}
        for i, g in enumerate(shapes):
            for j in tree.query(g, predicate="intersects"):
                if i != j:
                    adj[live[i].id].add(live[j].id)
        return adj

    # ---- mutation -------------------------------------------------------------
    def transfer(self, tile_ids, to_cid, name=None, color=None, style=None):
        """Give tiles to country `to_cid`, creating it if needed. Returns the new World."""
        w = self.copy()
        if to_cid not in w.countries:
            w.countries[to_cid] = Country(to_cid, name or to_cid, color, style=style or "normal")
        elif name:
            w.countries[to_cid].name = name
        if style:
            w.countries[to_cid].style = style
        for t in tile_ids:
            if t not in w.owner:
                raise KeyError(f"unknown tile {t}")
            w.owner[t] = to_cid
        if color:
            w.countries[to_cid].color = color
        w.assign_colors(only_missing=True)
        return w

    def rename(self, cid, name):
        w = self.copy()
        w.countries[cid].name = name
        return w

    def recolor(self, cid, color):
        w = self.copy()
        w.countries[cid].color = color
        return w

    def assign_colors(self, only_missing=False):
        """Greedy graph colouring so no two neighbours share a colour."""
        adj = self.adjacency()
        order = sorted(adj, key=lambda c: -len(adj[c]))
        for cid in order:
            c = self.countries[cid]
            if only_missing and c.color:
                continue
            used = [self.countries[n].color for n in adj[cid] if self.countries[n].color]
            # Rotate the palette by a stable per-country offset for variety, then
            # pick the candidate that is most different from every neighbour.
            k = sum(ord(ch) for ch in cid) % len(PALETTE)
            rotated = PALETTE[k:] + PALETTE[:k]
            best, best_d = None, -1.0
            for p in rotated:
                d = min((_color_dist(p, u) for u in used), default=1.0)
                if d > best_d + 1e-9:
                    best, best_d = p, d
                    if d >= 0.45:
                        break
            if best_d < 0.12:
                k = 1
                while True:
                    cand = _shift(PALETTE[len(adj[cid]) % len(PALETTE)], k)
                    if min((_color_dist(cand, u) for u in used), default=1.0) >= 0.12:
                        best = cand
                        break
                    k += 1
            c.color = best

    # ---- labels ---------------------------------------------------------------
    def label_point(self, cid, geom=None):
        g = geom if geom is not None else self.shape(cid)
        if g.is_empty:
            return None
        c = self.countries[cid]
        # Unchanged present-day countries keep the cartographer-placed anchor.
        hint = c.label_hint
        if hint and hint in self.atlas.label_anchor:
            x, y = self.atlas.label_anchor[hint]
            if g.contains(Polygon([(x, y), (x + 0.1, y), (x, y + 0.1)])):
                return (x, y)
        parts = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
        big = max(parts, key=lambda p: p.area)
        try:
            pt = polylabel(big, tolerance=1.0)
        except Exception:
            pt = big.representative_point()
        return (pt.x, pt.y)
