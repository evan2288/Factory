"""Cairo renderer: world state -> antialiased vector frame, plus HUD overlays."""
import math

import cairo
from shapely.geometry import MultiPolygon, Polygon

STYLE = dict(
    ocean="#0c1726",
    border="#0c1726",          # borders are drawn in the ocean colour: crisp, no halo
    border_width=1.6,
    coast="#3b5a7a",
    coast_width=0.8,
    lake="#0c1726",
    label="#ffffff",
    label_halo="#0c1726",
    label_font="Montserrat",
    label_min=11, label_max=34,
    label_min_area=900,        # px^2 below which a country gets no label
    year_font="Bebas Neue",
    year_color="#ffffff",
    caption_font="Montserrat",
    caption_color="#ffffff",
    sub_color="#b9c6d6",
    hud_bg="#0c1726",
    highlight="#ffffff",
)


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def add_path(ctx, geom):
    parts = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for poly in parts:
        if poly.is_empty or not isinstance(poly, Polygon):
            continue
        for ring in (poly.exterior, *poly.interiors):
            coords = ring.coords
            if len(coords) < 3:
                continue
            ctx.move_to(*coords[0][:2])
            for x, y in coords[1:]:
                ctx.line_to(x, y)
            ctx.close_path()


def _label_font_size(area, style):
    s = math.sqrt(area) * 0.18
    return max(style["label_min"], min(style["label_max"], s))


def draw_label(ctx, text, x, y, size, style, alpha=1.0, halo=True):
    ctx.select_font_face(style["label_font"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(size)
    ext = ctx.text_extents(text)
    tx = x - ext.width / 2 - ext.x_bearing
    ty = y + ext.height / 2
    ctx.move_to(tx, ty)
    ctx.text_path(text)
    if halo:
        ctx.set_source_rgba(*rgb(style["label_halo"]), 0.85 * alpha)
        ctx.set_line_width(max(2.0, size * 0.18))
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.stroke_preserve()
    ctx.set_source_rgba(*rgb(style["label"]), alpha)
    ctx.fill()
    return ext.width


def fits(ctx, text, size, geom, style):
    """True if the label at `size` is no wider than the country's largest part."""
    parts = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    big = max(parts, key=lambda p: p.area)
    minx, miny, maxx, maxy = big.bounds
    ctx.select_font_face(style["label_font"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(size)
    return ctx.text_extents(text).width <= (maxx - minx) * 1.25


def render_base(world, atlas, style=STYLE, labels=True):
    """Render the political map for a World into a new ARGB32 surface."""
    W, H = atlas.meta["width"], atlas.meta["height"]
    S = W / 1920.0  # all pixel sizes below are authored at 1080p and scaled
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)

    ctx.set_source_rgb(*rgb(style["ocean"]))
    ctx.paint()

    live = world.live_countries()
    shapes = {c.id: world.shape(c.id) for c in live}

    # Fills. Each country is one union polygon, so there are no internal seams.
    for c in live:
        g = shapes[c.id]
        if g.is_empty:
            continue
        add_path(ctx, g)
        ctx.set_source_rgb(*rgb(c.color))
        ctx.fill()

    # Civil-war factions: diagonal hatching over the fill.
    rebels = [c for c in live if c.style == "rebel" and not shapes[c.id].is_empty]
    if rebels:
        hatch = _hatch_pattern(style)
        for c in rebels:
            ctx.save()
            add_path(ctx, shapes[c.id])
            ctx.clip()
            ctx.set_source(hatch)
            ctx.paint()
            ctx.restore()

    # Lakes punch through in ocean colour.
    for lk in atlas.lakes:
        add_path(ctx, lk)
    ctx.set_source_rgb(*rgb(style["lake"]))
    ctx.fill()

    # Borders: stroke every country outline. Shared edges are stroked twice with
    # identical geometry, so they stay a single crisp line.
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for c in live:
        add_path(ctx, shapes[c.id])
    ctx.set_source_rgb(*rgb(style["border"]))
    ctx.set_line_width(style["border_width"] * S)
    ctx.stroke()

    # Faction front lines: white dashes over the border so they read as contested.
    if rebels:
        for c in rebels:
            add_path(ctx, shapes[c.id])
        ctx.set_source_rgba(1, 1, 1, 0.85)
        ctx.set_line_width(1.2 * S)
        ctx.set_dash([3.0 * S, 3.0 * S])
        ctx.stroke()
        ctx.set_dash([])

    # Soft coastline on top so land reads against the dark ocean.
    add_path(ctx, atlas.land_union())
    ctx.set_source_rgba(*rgb(style["coast"]), 0.9)
    ctx.set_line_width(style["coast_width"] * S)
    ctx.stroke()

    if labels:
        placed = []  # bounding boxes of labels already drawn, biggest countries first

        def box(text, size, x, y):
            ctx.select_font_face(style["label_font"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(size)
            e = ctx.text_extents(text)
            pad = 3 * S
            return (x - e.width / 2 - pad, y - e.height / 2 - pad, x + e.width / 2 + pad, y + e.height / 2 + pad)

        def clear(b):
            return all(b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3] for o in placed)

        for c in sorted(live, key=lambda c: -shapes[c.id].area):
            g = shapes[c.id]
            if g.area < style["label_min_area"] * S * S:
                continue
            pt = world.label_point(c.id, g)
            if pt is None:
                continue
            size = _label_font_size(g.area / (S * S), style) * S
            text = c.name.upper() if size >= 16 * S else c.name
            while size > style["label_min"] * S and not (fits(ctx, text, size, g, style)
                                                         and clear(box(text, size, *pt))):
                size -= S
            b = box(text, size, *pt)
            if not fits(ctx, text, size, g, style) or not clear(b):
                continue
            placed.append(b)
            draw_label(ctx, text, pt[0], pt[1], size, style)

    surf.flush()
    return surf


def _hatch_pattern(style, S=1.0):
    """Repeating diagonal dark lines, used to mark civil-war factions."""
    period = int(round(7 * S))
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, period, period)
    c = cairo.Context(s)
    c.set_source_rgba(*rgb(style["ocean"]), 0.55)
    c.set_line_width(1.6 * S)
    c.move_to(-1, period + 1)
    c.line_to(period + 1, -1)
    c.stroke()
    c.move_to(-1, 1)
    c.line_to(1, -1)
    c.stroke()
    c.move_to(period - 1, period + 1)
    c.line_to(period + 1, period - 1)
    c.stroke()
    p = cairo.SurfacePattern(s)
    p.set_extend(cairo.EXTEND_REPEAT)
    return p


def draw_highlight(ctx, geom, alpha, style=STYLE):
    if alpha <= 0 or geom.is_empty:
        return
    ctx.save()
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    add_path(ctx, geom)
    ctx.set_source_rgba(*rgb(style["highlight"]), alpha)
    ctx.fill()
    ctx.restore()


def draw_hud(ctx, W, H, year, title=None, subtitle=None, alpha=1.0, style=STYLE):
    """Year counter top-left, caption bottom-centre. Sizes authored at 1080p."""
    S = W / 1920.0
    ctx.save()
    # Year
    ctx.select_font_face(style["year_font"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(96 * S)
    ytxt = f"{int(round(year))}" if year >= 0 else f"{int(round(-year))} BC"
    ext = ctx.text_extents(ytxt)
    ctx.move_to(56 * S, 40 * S + ext.height)
    ctx.set_source_rgba(*rgb(style["year_color"]), 1.0)
    ctx.show_text(ytxt)
    ctx.select_font_face(style["caption_font"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(18 * S)
    ctx.move_to(58 * S, 40 * S + ext.height + 30 * S)
    ctx.set_source_rgba(*rgb(style["sub_color"]), 0.9)
    ctx.show_text("AD" if year >= 0 else "")

    # Caption
    if title and alpha > 0:
        ctx.select_font_face(style["caption_font"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(40 * S)
        e1 = ctx.text_extents(title)
        ctx.select_font_face(style["caption_font"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(22 * S)
        e2 = ctx.text_extents(subtitle or "")
        box_w = max(e1.width, e2.width) + 80 * S
        box_h = (60 + (34 if subtitle else 0) + 30) * S
        bx, by = (W - box_w) / 2, H - box_h - 28 * S
        ctx.set_source_rgba(*rgb(style["hud_bg"]), 0.78 * alpha)
        _round_rect(ctx, bx, by, box_w, box_h, 10 * S)
        ctx.fill()
        ctx.select_font_face(style["caption_font"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(40 * S)
        ctx.move_to((W - e1.width) / 2 - e1.x_bearing, by + 22 * S + e1.height)
        ctx.set_source_rgba(*rgb(style["caption_color"]), alpha)
        ctx.show_text(title)
        if subtitle:
            ctx.select_font_face(style["caption_font"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            ctx.set_font_size(22 * S)
            ctx.move_to((W - e2.width) / 2 - e2.x_bearing, by + 22 * S + e1.height + 36 * S)
            ctx.set_source_rgba(*rgb(style["sub_color"]), alpha)
            ctx.show_text(subtitle)
    ctx.restore()


def _round_rect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()
