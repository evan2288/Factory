"""Builds the paid and free cookbooks as print-ready HTML (then pdf.mjs turns them into PDFs).

Usage: python3 build.py [--author "@handle"] [--price 9] [--link "https://..."]
"""
import argparse
import html
import math
import os

from recipes import CHAPTERS, RECIPES, PANTRY, PRINCIPLES, HOOKS, PROFILE, SAFETY, allergens

ap = argparse.ArgumentParser()
ap.add_argument("--author", default="")
ap.add_argument("--price", default="9")
ap.add_argument("--link", default="link in bio")
args = ap.parse_args()

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
CH = {c[0]: dict(slug=c[0], name=c[1], blurb=c[2], color=c[3], tint=c[4]) for c in CHAPTERS}
BYID = {r["id"]: r for r in RECIPES}
E = html.escape
INK = "#15161a"
SLUGS = [c[0] for c in CHAPTERS]

FONTS = open(os.path.join(HERE, "fonts", "embedded.css")).read()
CSS = FONTS + """
@page { size: 8.5in 11in; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: 'DM Sans', system-ui, sans-serif; color: #15161a; background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { width: 8.5in; height: 11in; position: relative; overflow: hidden; page-break-after: always; break-after: page; padding: 0.6in 0.65in; background: #fff; }
.page:last-child { page-break-after: auto; }
.display { font-family: 'Anton', Impact, sans-serif; text-transform: uppercase; letter-spacing: 0.01em; line-height: 0.92; font-weight: 400; }
.hand { font-family: 'Caveat', cursive; }
.muted { color: #6b6f7a; }
.num { position: absolute; bottom: 0.35in; right: 0.65in; font-size: 10px; color: #9a9ea8; letter-spacing: 0.12em; }
.foot { position: absolute; bottom: 0.35in; left: 0.65in; font-size: 10px; color: #9a9ea8; letter-spacing: 0.12em; text-transform: uppercase; }

/* stickers: white die-cut outline + soft shadow drawn from the same shapes */
.stk { display: block; overflow: visible; }
.stk .ol * { fill: #fff; stroke: #fff; stroke-width: 22px; }
.stk .sh { opacity: 0.16; }
.stk .sh * { fill: #15161a; stroke: #15161a; stroke-width: 22px; }

/* covers */
.cover { padding: 0; }
.cover .bg { position: absolute; inset: 0; }
.cover .kicker { position: absolute; left: 0.65in; top: 0.62in; color: #FFC43D; font-size: 13px; font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase; }
.cover .title { position: absolute; left: 0.65in; right: 0.65in; top: 1.0in; color: #fff; font-size: 128px; }
.cover .sub { position: absolute; left: 0.65in; right: 0.65in; color: #fff; font-size: 30px; font-weight: 700; line-height: 1.15; }
.cover .tag { position: absolute; left: 0.65in; color: #c9ccd3; font-size: 16px; max-width: 6.2in; line-height: 1.5; }
.cover .author { position: absolute; left: 0.65in; bottom: 0.7in; color: #fff; font-size: 14px; letter-spacing: 0.2em; text-transform: uppercase; }
.cover .badge { position: absolute; right: 0.65in; top: 0.7in; width: 1.55in; height: 1.55in; border-radius: 50%; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 15px; font-weight: 700; line-height: 1.2; padding: 12px; transform: rotate(8deg); box-shadow: 0 0 0 5px rgba(255,255,255,0.12); }
.srow { position: absolute; left: 0.65in; right: 0.65in; display: flex; justify-content: space-between; }
.srow.c3 { justify-content: center; gap: 0.45in; }
.pills { position: absolute; left: 0.65in; right: 0.65in; display: flex; flex-wrap: wrap; gap: 8px; }
.pills span { border: 2px solid rgba(255,255,255,0.3); color: #fff; border-radius: 999px; padding: 6px 13px; font-size: 13px; font-weight: 700; }
.stripes { position: absolute; left: 0; right: 0; bottom: 0; height: 0.3in; display: flex; }
.stripes i { flex: 1; }

/* chapter opener */
.chapter { padding: 0; }
.chapter .band-bg { position: absolute; inset: 0; }
.chapter .n { position: absolute; left: 0.65in; top: 0.8in; color: rgba(255,255,255,0.55); font-size: 240px; }
.chapter .art { position: absolute; right: 0.6in; top: 0.6in; width: 3.2in; height: 3.2in; }
.chapter .t { position: absolute; left: 0.65in; right: 0.65in; top: 4.6in; color: #fff; font-size: 92px; }
.chapter .b { position: absolute; left: 0.65in; right: 1.6in; top: 7.4in; color: #fff; font-size: 19px; line-height: 1.5; }
.chapter .list { position: absolute; left: 0.65in; right: 0.65in; bottom: 0.7in; color: rgba(255,255,255,0.92); font-size: 12.5px; columns: 2; column-gap: 24px; line-height: 1.7; }

/* recipe: a column, so the flavour band soaks up whatever height is left */
.recipe { display: flex; flex-direction: column; }
.recipe > * { flex: none; }
.recipe .head { display: flex; gap: 14px; align-items: center; margin-bottom: 10px; }
.recipe .idn { flex: none; width: 58px; height: 58px; border-radius: 14px; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 27px; line-height: 1; }
.recipe .kick { font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase; color: #6b6f7a; font-weight: 700; margin-bottom: 5px; }
.recipe h1 { margin: 0; font-size: 44px; line-height: 1.12; }
.recipe h1.long { font-size: 36px; }
.recipe .meta { display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 4px 0 12px; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #6b6f7a; align-items: center; }
.recipe .meta b { color: #15161a; }
.weird { display: inline-flex; gap: 4px; vertical-align: middle; margin-left: 4px; }
.weird i { width: 11px; height: 11px; border-radius: 50%; background: #e2e4e9; display: inline-block; }
.hook { border-left: 5px solid; padding: 9px 15px; margin: 0 0 12px; font-size: 17.5px; line-height: 1.3; font-weight: 500; background: #fafafb; border-radius: 0 10px 10px 0; }
.hook small { display: block; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #6b6f7a; margin-bottom: 4px; }
.why { font-size: 13px; line-height: 1.52; color: #3c3f48; margin: 0 0 14px; }
.why b { color: #15161a; }
.cols { display: grid; grid-template-columns: 2.55in 1fr; gap: 26px; }
.ing h3, .steps h3, .film h3, .stats h3 { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; margin: 0 0 8px; color: #6b6f7a; }
.ing ul { list-style: none; margin: 0; padding: 0; font-size: 13px; line-height: 1.5; }
.ing li { padding: 4px 0; border-bottom: 1px solid #ececf0; }
.steps ol { margin: 0; padding-left: 0; list-style: none; counter-reset: s; font-size: 13px; line-height: 1.5; }
.steps li { position: relative; padding: 0 0 8px 32px; counter-increment: s; }
.steps li::before { content: counter(s); position: absolute; left: 0; top: 0; width: 22px; height: 22px; border-radius: 50%; color: #fff; font-weight: 700; font-size: 11.5px; display: flex; align-items: center; justify-content: center; background: var(--c); }
.tip { margin-top: 4px; font-size: 12.5px; line-height: 1.5; color: #3c3f48; }
.tip b { font-weight: 700; color: #15161a; }
.know { margin-top: 10px; background: #f6f7f9; border-radius: 12px; padding: 9px 11px 10px; }
.allergens { font-size: 11px; line-height: 1.9; }
.allergens b, .safe b { display: block; font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: #6b6f7a; line-height: 1.4; margin-bottom: 3px; }
.allergens span { display: inline-block; margin: 0 4px 3px 0; padding: 1px 8px; border-radius: 999px; background: #fff; color: #3c3f48; line-height: 1.6; }
.allergens span.pn { background: #FF5A5F; color: #fff; font-weight: 700; }
.allergens span.ok { background: #DFF9F0; color: #0b6b4f; }
.ckline { font-size: 10.5px; color: #6b6f7a; border-top: 1px dashed #c7cad2; margin-top: 5px; padding-top: 6px; line-height: 1.45; }
.ckline em { font-style: normal; font-weight: 700; color: #3c3f48; }
.safe { margin-top: 9px; background: #FFF1E0; border-radius: 9px; padding: 7px 9px 8px; font-size: 11px; line-height: 1.45; color: #3c3f48; }
.safe b { color: #c2410c; display: flex; align-items: center; gap: 5px; }
.safe b svg { width: 12px; height: 12px; flex: none; }
.band { flex: 1 1 0; min-height: 0; display: flex; gap: 12px; align-items: stretch; container-type: size; }
.band > * { margin-top: 10px; }
.band .stats { flex: none; width: 2.45in; border-radius: 14px; padding: 8px 10px; display: flex; flex-direction: column; justify-content: center; }
.band .stats h3 { margin: 0 0 2px 4px; }
.band .stats svg { width: 100%; height: auto; max-height: 1.75in; flex: 0 1 auto; min-height: 0; }
.band .strip { display: none; flex: 1 1 auto; align-self: center; border-radius: 12px; padding: 9px 14px; gap: 10px; justify-content: space-between; align-items: center; }
.strip .fs-t { font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: #6b6f7a; font-weight: 700; line-height: 1.25; }
.strip .fs span { display: block; font-size: 9.5px; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 700; color: #3c3f48; margin-bottom: 4px; }
.strip .seg { display: flex; gap: 2px; }
.strip .seg i { width: 9px; height: 7px; border-radius: 2px; }
.band .art { flex: 1 1 0; min-width: 0; display: flex; align-items: center; justify-content: center; }
.band .art svg { height: 100%; max-height: 2.5in; width: auto; max-width: 100%; }
.band .say { flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; justify-content: center; font-size: 30px; line-height: 1.05; color: #15161a; }
.band .say small { font-family: 'DM Sans', sans-serif; font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: #6b6f7a; font-weight: 700; margin-bottom: 4px; }
@container (max-height: 1.6in) { .band .stats, .band .say { display: none; } .band .strip { display: flex; } }
@container (max-height: 0.8in) { .band .art { display: none; } }
@container (max-height: 0.55in) { .band .strip { display: none; } }
.film { margin-top: 10px; border-radius: 14px; padding: 11px 15px; }
.film .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; font-size: 12px; line-height: 1.45; }
.film .grid div b { display: block; font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 3px; }
.film .texts { margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; }
.film .texts span { background: #15161a; color: #fff; border-radius: 999px; padding: 4px 10px; font-size: 11.5px; font-weight: 500; }
.film .cap { margin-top: 8px; font-size: 12px; line-height: 1.45; color: #3c3f48; }
.film .cap b { display: block; font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 3px; color: #15161a; }
.locked { margin-top: 12px; border: 2px dashed #c7cad2; border-radius: 14px; padding: 12px 16px; display: flex; gap: 18px; align-items: center; }
.lk-copy { flex: 1; min-width: 0; }
.lk-tag { display: flex; gap: 6px; align-items: center; font-size: 10.5px; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 700; color: #6b6f7a; }
.lk-tag svg { width: 13px; height: 13px; flex: none; }
.lk-copy b { display: block; font-size: 24px; margin: 6px 0 5px; line-height: 1; }
.lk-copy p { margin: 0; font-size: 12px; line-height: 1.45; color: #3c3f48; }
.lk-phones { flex: none; display: flex; gap: 10px; }
.ph { width: 0.66in; height: 1.15in; border: 3px solid #15161a; border-radius: 12px; padding: 12px 6px 6px; background: #fff; display: flex; flex-direction: column; gap: 5px; }
.ph span { font-size: 8.5px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #9a9ea8; }
.ph i { display: block; height: 6px; border-radius: 3px; background: #e2e4e9; }
.ph i.s { width: 60%; }
.ph i.k { height: 16px; margin-top: auto; background: #15161a; border-radius: 6px; }

/* text pages */
.text h1 { font-size: 64px; margin: 0 0 18px; }
.text h2 { font-size: 22px; margin: 20px 0 8px; }
.text p { font-size: 14.5px; line-height: 1.6; margin: 0 0 12px; max-width: 6.4in; }
.text .lead { font-size: 18px; line-height: 1.5; color: #3c3f48; }
.text.flex { display: flex; flex-direction: column; }
.text.flex > * { flex: none; }
.corner { position: absolute; right: 0.55in; top: 0.45in; width: 1.35in; height: 1.35in; }
.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 16px; }
.card { border-radius: 14px; padding: 15px 18px; font-size: 13px; line-height: 1.5; }
.card b { display: block; font-size: 15px; margin-bottom: 4px; }
.cards.tight { gap: 10px; margin-top: 10px; }
.cards.tight .card { padding: 11px 14px; font-size: 12.5px; line-height: 1.45; }
.cards.tight .card b { font-size: 14px; margin-bottom: 2px; }
.sc { display: flex; gap: 12px; align-items: flex-start; }
.sc .icw { flex: none; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.sc .icw svg { width: 19px; height: 19px; }
.pantry { columns: 2; column-gap: 28px; font-size: 13.5px; line-height: 1.5; margin-top: 12px; }
.pantry div { break-inside: avoid; padding: 10px 0; border-bottom: 1px solid #ececf0; }
.pantry b { display: block; }
.toc { columns: 2; column-gap: 32px; font-size: 12.5px; line-height: 1.8; margin-top: 4px; }
.toc .c { font-weight: 700; margin-top: 8px; break-after: avoid; }
.toc .c:first-child { margin-top: 0; }
.toc .r { display: flex; justify-content: space-between; gap: 8px; }
.toc .r span:last-child { color: #9a9ea8; }
.cal { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-top: 14px; }
.cal div { border-radius: 10px; padding: 10px 10px 9px; font-size: 11.5px; line-height: 1.32; min-height: 1.2in; }
.cal b { display: block; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 4px; opacity: 0.7; }
.hooks { columns: 2; column-gap: 28px; font-size: 12.5px; line-height: 1.45; margin-top: 10px; }
.hooks div { break-inside: avoid; padding: 7px 0 7px 24px; position: relative; border-bottom: 1px solid #ececf0; }
.hooks div::before { content: '\\201C'; position: absolute; left: 0; top: 2px; font-family: 'Anton'; font-size: 24px; color: #c7cad2; }
.score { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; }
.score th, .score td { border: 1px solid #e2e4e9; padding: 10px 8px; text-align: left; }
.score th { background: #f4f5f7; font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; }
.score td { height: 40px; }
.cta { border-radius: 18px; padding: 22px 24px; }
.cta h2 { margin: 0 0 10px; font-size: 30px; }
.cta p { margin: 0 0 9px; font-size: 13.5px; line-height: 1.5; }
.cta .price { font-size: 56px; margin: 12px 0 2px; }
.sig { margin-top: auto; display: flex; align-items: center; gap: 20px; padding-top: 14px; }
.sig .row { display: flex; gap: 12px; flex: none; }
.sig .row svg { width: 1.05in; height: 1.05in; }
.sig .hand { font-size: 30px; line-height: 1.1; margin: 0; }
.how { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 18px; }
.how-i { display: flex; gap: 10px; align-items: center; background: #f6f7f9; border-radius: 14px; padding: 10px 12px; font-size: 12px; line-height: 1.4; color: #3c3f48; }
.how-i svg { flex: none; width: 0.8in; height: 0.8in; }
.how-i b { display: block; font-size: 13.5px; margin-bottom: 2px; color: #15161a; }
.callout { display: flex; gap: 12px; align-items: center; background: #FFF1E0; border-radius: 14px; padding: 12px 16px; margin-top: 14px; font-size: 13px; line-height: 1.45; color: #3c3f48; }
.callout svg { flex: none; width: 26px; height: 26px; }
.eq { margin-top: auto; display: flex; align-items: center; gap: 12px; background: #15161a; color: #fff; border-radius: 18px; padding: 14px 20px; }
.eq-i { display: flex; flex-direction: column; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; flex: none; }
.eq-i svg { width: 1.2in; height: 1.2in; }
.eq-op { font-size: 44px; color: #FFC43D; flex: none; }
.eq-r { flex: 1; font-size: 13px; line-height: 1.45; color: #c9ccd3; }
.eq-r b { display: block; font-size: 26px; color: #fff; margin-bottom: 6px; line-height: 1.02; }
.storyboard { display: flex; justify-content: center; align-items: center; gap: 12px; margin: 4px 0 6px; }
.sb { display: flex; flex-direction: column; align-items: center; width: 1.75in; }
.sb-t { font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: #9a9ea8; font-weight: 700; margin-bottom: 5px; }
.sb-ph { width: 1.2in; height: 2.1in; border: 4px solid #15161a; border-radius: 18px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; }
.sb-ph svg { width: 0.9in; height: 0.9in; }
.sb-chip { background: #15161a; color: #fff; border-radius: 999px; padding: 3px 9px; font-size: 10.5px; font-weight: 700; }
.sb-l { font-size: 11.5px; font-weight: 700; text-align: center; margin-top: 6px; line-height: 1.3; }
.sb-arrow { width: 22px; height: 22px; flex: none; }
.flist { display: grid; grid-template-columns: 1fr 1fr; gap: 0 22px; margin-top: 6px; }
.fl { display: flex; align-items: center; gap: 10px; font-size: 13px; line-height: 1.3; padding: 6px 0; border-bottom: 1px solid #ececf0; }
.fl-n { flex: none; width: 26px; height: 26px; border-radius: 7px; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 13px; line-height: 1; }
.fl-name { flex: 1; }
.fl-p { color: #9a9ea8; font-size: 12px; flex: none; }
.up-grid { display: grid; grid-template-columns: 1fr 3.4in; gap: 24px; align-items: start; margin-top: 4px; }
.mini-wrap { width: 3.4in; height: 4.4in; overflow: hidden; border-radius: 10px; box-shadow: 0 10px 28px rgba(21,22,26,0.22), 0 0 0 1px #e2e4e9; position: relative; }
.mini-page { width: 8.5in; height: 11in; transform: scale(0.4); transform-origin: 0 0; position: relative; overflow: hidden; padding: 0.6in 0.65in; background: #fff; }
.mini-cap { font-size: 11.5px; color: #6b6f7a; text-align: center; margin-top: 10px; line-height: 1.4; }
"""


# ---------- illustrations (inline SVG, nothing licensed) ----------
SK = f'stroke="{INK}" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"'


def _star(cx, cy, s):
    return (f'<path d="M{cx} {cy - s} Q{cx} {cy} {cx + s} {cy} Q{cx} {cy} {cx} {cy + s} Q{cx} {cy} {cx - s} {cy} Q{cx} {cy} {cx} {cy - s}Z" '
            f'fill="#fff" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>')


def _face(x, y, w=11):
    return (f'<circle cx="{x - w}" cy="{y}" r="4.6" fill="{INK}"/><circle cx="{x + w}" cy="{y}" r="4.6" fill="{INK}"/>'
            f'<path d="M{x - 7} {y + 9} Q{x} {y + 16} {x + 7} {y + 9}" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>')


def _burst(cx, cy, ro, ri, n=12):
    pts = []
    for i in range(n * 2):
        a = math.pi * i / n - math.pi / 2
        rr = ro if i % 2 == 0 else ri
        pts.append(f"{cx + rr * math.cos(a):.1f},{cy + rr * math.sin(a):.1f}")
    return " ".join(pts)


# Each chapter has a mascot: (silhouette shapes, details drawn on top).
ART = {
    "sweet-salty": (  # a pickle
        f'<path d="M48 150 C30 132 40 96 72 70 C104 44 146 34 160 50 C174 66 160 102 128 128 C96 154 66 168 48 150Z" fill="#8BD450" {SK}/>',
        '<circle cx="128" cy="64" r="5" fill="#5DA130"/><circle cx="148" cy="80" r="4" fill="#5DA130"/>'
        '<circle cx="64" cy="134" r="5" fill="#5DA130"/><circle cx="86" cy="148" r="4" fill="#5DA130"/>'
        + _face(104, 98) + _star(36, 50, 14) + _star(170, 150, 11)),
    "spicy-sweet": (  # a chili
        f'<path d="M154 47 C156 36 162 30 172 28" fill="none" stroke="{INK}" stroke-width="14" stroke-linecap="round"/>'
        f'<path d="M150 52 C112 44 66 70 52 116 C42 150 56 176 70 168 C80 162 84 140 104 118 C126 94 156 82 160 66 C162 58 158 54 150 52Z" fill="#FF4D4D" {SK}/>'
        f'<path d="M136 58 C142 44 162 42 170 56 C160 66 146 66 136 58Z" fill="#3FBF5F" {SK}/>',
        '<path d="M154 47 C156 36 162 30 172 28" fill="none" stroke="#3FBF5F" stroke-width="6" stroke-linecap="round"/>'
        '<path d="M70 96 C74 84 82 76 92 72" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" opacity=".7"/>'
        + _face(94, 104, 10) + _star(36, 44, 13) + _star(168, 120, 11)),
    "fat-acid": (  # a lemon
        f'<ellipse cx="31" cy="110" rx="10" ry="8" fill="#FFE45C" {SK}/><ellipse cx="169" cy="110" rx="10" ry="8" fill="#FFE45C" {SK}/>'
        f'<ellipse cx="100" cy="110" rx="66" ry="52" fill="#FFE45C" {SK}/>'
        f'<path d="M106 60 C112 38 140 30 154 38 C146 56 124 64 106 60Z" fill="#3FBF5F" {SK}/>',
        '<path d="M112 56 C124 50 136 44 148 40" fill="none" stroke="#2E8F46" stroke-width="3" stroke-linecap="round"/>'
        '<circle cx="78" cy="122" r="7" fill="#FF8FAB" opacity=".7"/><circle cx="122" cy="122" r="7" fill="#FF8FAB" opacity=".7"/>'
        + _face(100, 106) + _star(38, 52, 13) + _star(166, 166, 11)),
    "umami": (  # a ramen bowl
        f'<path d="M128 14 L84 96" stroke="{INK}" stroke-width="14" stroke-linecap="round"/><path d="M150 20 L102 98" stroke="{INK}" stroke-width="14" stroke-linecap="round"/>'
        f'<path d="M40 98 C46 74 60 74 66 96 C72 72 86 72 92 96 C98 72 112 72 118 96 C124 72 138 72 144 96 C150 76 160 76 162 98Z" fill="#FFE7A3" {SK}/>'
        f'<ellipse cx="140" cy="86" rx="20" ry="13" fill="#fff" {SK}/>'
        f'<path d="M24 98 H176 C176 144 144 172 100 172 C56 172 24 144 24 98Z" fill="#FF5A5F" {SK}/>',
        '<path d="M128 14 L84 96" stroke="#C47A35" stroke-width="6" stroke-linecap="round"/><path d="M150 20 L102 98" stroke="#C47A35" stroke-width="6" stroke-linecap="round"/>'
        '<circle cx="140" cy="86" r="7" fill="#FFB020"/>'
        '<path d="M34 114 H166" stroke="#fff" stroke-width="5" stroke-linecap="round"/>'
        + _face(100, 136) + _star(30, 40, 13)),
    "texture": (  # a CRUNCH burst
        f'<polygon points="{_burst(100, 100, 94, 70)}" fill="#FF5A5F" {SK}/>',
        f'<text x="100" y="113" text-anchor="middle" font-family="Anton, Impact, sans-serif" font-size="37" fill="#fff" stroke="{INK}" stroke-width="2" '
        'paint-order="stroke" letter-spacing="1" transform="rotate(-8 100 100)">CRUNCH!</text>'),
    "breakfast": (  # a fried egg
        f'<path d="M60 52 C88 30 130 40 150 60 C176 84 174 124 150 146 C126 170 82 172 58 152 C34 132 26 80 60 52Z" fill="#fff" {SK}/>',
        f'<circle cx="104" cy="100" r="34" fill="#FFC43D" {SK}/>'
        '<path d="M84 88 Q88 74 102 72" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round"/>'
        + _face(104, 100, 10) + _star(170, 36, 13) + _star(28, 168, 11)),
    "drinks-dessert": (  # an ice cream cone
        f'<path d="M64 104 L136 104 L100 186Z" fill="#E9A15B" {SK}/>'
        f'<path d="M56 106 C44 70 70 40 100 40 C130 40 156 70 144 106 C140 116 132 110 128 118 C124 128 114 122 110 114 C104 124 94 124 90 114 C84 126 72 122 72 112 C66 118 58 114 56 106Z" fill="#9BF6C7" {SK}/>'
        f'<circle cx="104" cy="32" r="12" fill="#E63946" {SK}/>',
        '<path d="M88 106 L112 158 M112 106 L124 131 M112 106 L88 158 M88 106 L76 131" stroke="#B9773A" stroke-width="3" stroke-linecap="round"/>'
        f'<path d="M106 20 C108 12 114 6 122 4" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>'
        '<path d="M74 64 l7 -4 M124 58 l7 4 M132 86 l-5 6 M66 90 l7 3" stroke="#7B61FF" stroke-width="5" stroke-linecap="round"/>'
        + _face(100, 80, 12) + _star(36, 40, 13) + _star(168, 150, 11)),
}


def sticker(slug, size=None, rot=0, flip=False, extra=""):
    body, detail = ART[slug]
    tf = f"rotate({rot} 100 100)" + (" translate(200 0) scale(-1 1)" if flip else "")
    style = f' style="width:{size};height:{size}{extra}"' if size else ""
    return (f'<svg class="stk" viewBox="-14 -14 228 228" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"{style}>'
            f'<g transform="{tf}"><g class="sh" transform="translate(5 7)">{body}</g><g class="ol">{body}</g>{body}{detail}</g></svg>')


LABELS = ["Sweet", "Salty", "Sour", "Spicy", "Umami", "Crunch"]


def radar(profile, color):
    vals = [int(c) for c in profile]
    cx, cy, R = 126, 88, 56

    def pt(i, r):
        a = -math.pi / 2 + i * math.pi / 3
        return cx + r * math.cos(a), cy + r * math.sin(a)

    def poly(rs):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, r) for i, r in enumerate(rs)))

    rings = "".join(f'<polygon points="{poly([R * k / 5] * 6)}" fill="{"#fff" if k == 5 else "none"}" stroke="#d5d8df" stroke-width="1.3"/>' for k in (5, 4, 3, 2, 1))
    axes = "".join(f'<line x1="{cx}" y1="{cy}" x2="{pt(i, R)[0]:.1f}" y2="{pt(i, R)[1]:.1f}" stroke="#d5d8df" stroke-width="1.3"/>' for i in range(6))
    rs = [R * max(v, 0.3) / 5 for v in vals]
    dots = "".join(f'<circle cx="{pt(i, r)[0]:.1f}" cy="{pt(i, r)[1]:.1f}" r="3.6" fill="{color}" stroke="#fff" stroke-width="1.5"/>' for i, r in enumerate(rs))
    labels = ""
    for i, (lab, v) in enumerate(zip(LABELS, vals)):
        x, y = pt(i, R + 13)
        anchor = "middle" if i in (0, 3) else ("start" if i in (1, 2) else "end")
        dy = {0: -3, 3: 13}.get(i, 5)
        labels += (f'<text x="{x:.1f}" y="{y + dy:.1f}" text-anchor="{anchor}" font-family="DM Sans, sans-serif" font-size="14" font-weight="700" fill="#3c3f48">'
                   f'{lab} <tspan fill="{color}">{v}</tspan></text>')
    return (f'<svg class="radar" viewBox="0 0 252 176" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Flavour stats">{rings}{axes}'
            f'<polygon points="{poly(rs)}" fill="{color}" fill-opacity=".32" stroke="{color}" stroke-width="3" stroke-linejoin="round"/>{dots}{labels}</svg>')


IC = {
    "fire": '<path d="M12 2.5c.8 3.2 4.8 4.6 4.8 9.6a4.8 4.8 0 0 1-9.6 0c0-2.6 1.6-3.8 2-5.6 1 .9 1.6 1.9 1.7 3 .9-2 1.1-4.2 1.1-7z"/>',
    "drip": '<path d="M4 4h16v5.5c0 1.6-1.3 1.6-1.7 3.1s-1.5 2.1-2.3.4-.8-2.9-2.1-2.9-1 3.7-2.3 6.4-2.7 1-2.7-1.5-.4-2.5-1.7-2.5S4 11.6 4 9.5z"/>',
    "thermo": '<path d="M10 4a2 2 0 0 1 4 0v9.3a4 4 0 1 1-4 0z"/><path d="M12 9v7"/>',
    "knife": '<path d="M3 20L14.5 8.5l2.5 2.5L6.5 21.5z"/><path d="M14.5 8.5l4-4 2.5 2.5-4 4"/>',
    "egg": '<path d="M12 3c3.5 0 6.5 5.2 6.5 10a6.5 6.5 0 0 1-13 0C5.5 8.2 8.5 3 12 3z"/>',
    "bowl": '<path d="M3 11h18a9 9 0 0 1-18 0z"/><path d="M8 8.5c0-1 1-1.5 1.5-1.5M12 6.5c0-1 1-1.5 1.5-1.5M15.5 8.5c0-1 1-1.5 1.5-1.5"/>',
    "chili": '<path d="M17 6.5c-5 0-10 4-12.5 12 4.5-.8 10.5-4 12.5-9"/><path d="M17 6.5c1-2 2.5-2.8 4-2.8"/>',
    "peanut": '<path d="M12 2.8a4.2 4.2 0 0 1 3 7 4.6 4.6 0 1 1-6 0 4.2 4.2 0 0 1 3-7z"/>',
    "person": '<circle cx="12" cy="7" r="3.5"/><path d="M5.5 21c.5-4.5 3-7 6.5-7s6 2.5 6.5 7"/>',
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    "warn": '<path d="M12 3.5l9.5 16.5h-19z"/><path d="M12 10v4.5M12 17.2v.3"/>',
    "lock": '<rect x="4.5" y="10.5" width="15" height="10.5" rx="2.5" fill="#15161a"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
    "arrow": '<path d="M4 12h15M13 6l6 6-6 6"/>',
}


def strip(profile, color):
    items = '<div class="fs-t">Flavour<br>stats</div>'
    for lab, v in zip(LABELS, profile):
        segs = "".join(f'<i style="background:{color if k < int(v) else "#d5d8df"}"></i>' for k in range(5))
        items += f'<div class="fs"><span>{lab}</span><div class="seg">{segs}</div></div>'
    return items


def sig(text, color, slugs):
    row = "".join(sticker(sl, rot=(-7 if i % 2 else 7)) for i, sl in enumerate(slugs))
    return f'<div class="sig"><div class="row">{row}</div><p class="hand" style="color:{color}">{text}</p></div>'


def icon(name, color=INK, width="2"):
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" '
            f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{IC[name]}</svg>')


# ---------- page parts ----------
def weird(n):
    return '<span class="weird">' + "".join(f'<i style="background:{"var(--c)" if i < n else "#e2e4e9"}"></i>' for i in range(5)) + "</span>"


def recipe_page(r, pageno, with_film=True, free=False, xref=None):
    c = CH[r["chapter"]]
    ingredients = [xref(i) if xref else i for i in r["ingredients"]]
    ing = "".join(f"<li>{E(i)}</li>" for i in ingredients)
    steps = "".join(f"<li>{E(s)}</li>" for s in r["steps"])
    tip = f'<div class="tip"><b>Tip.</b> {E(r["tip"])}</div>' if r.get("tip") else ""
    al, check = allergens(r)
    chips = "".join(f'<span class="{"pn" if a == "peanuts" else ""}">{E(a)}</span>' for a in al) or '<span class="ok">none of the big eight</span>'
    know = f'<div class="allergens"><b>Contains</b>{chips}</div>'
    if check:
        know += f'<div class="ckline"><em>Check labels:</em> {E(", ".join(check))}</div>'
    if r["id"] in SAFETY:
        know += f'<div class="safe"><b>{icon("warn", "#c2410c", "2.4")}Safety</b>{E(SAFETY[r["id"]])}</div>'
    flip = r["id"] % 2 == 0
    if with_film:
        shots = "".join(f"<div><b>{E(s.split(':')[0])}</b>{E(s.split(':', 1)[1].strip())}</div>" for s in r["film"])
        texts = "".join(f"<span>{E(t)}</span>" for t in r["text"])
        caption = f"{r['hook']} Full recipe below. Would you try it? #weirdfoodcombos #{c['slug'].replace('-', '')}"
        bottom = (f'<div class="film" style="background:{c["tint"]}"><h3>Film it · 3 shots</h3><div class="grid">{shots}</div>'
                  f'<div class="texts">{texts}</div><div class="cap"><b>Caption starter</b>{E(caption)}</div></div>')
    else:
        phones = "".join(f'<div class="ph"><span>Shot {i}</span><i></i><i class="s"></i><i class="k"></i></div>' for i in (1, 2, 3))
        bottom = (f'<div class="locked"><div class="lk-copy"><div class="lk-tag">{icon("lock")}In the full book</div>'
                  f'<b class="display">The film plan for this one</b>'
                  f'<p>The three shots, the on-screen text and a caption starter. All 50 recipes in Unhinged Kitchen come with one.</p></div>'
                  f'<div class="lk-phones">{phones}</div></div>')
    say = f'<div class="say hand"><small>On-screen text idea</small>"{E(r["text"][0])}"</div>' if not with_film else ""
    band = (f'<div class="band"><div class="stats" style="background:{c["tint"]}"><h3>Flavour stats</h3>{radar(PROFILE[r["id"]], c["color"])}</div>'
            f'<div class="strip" style="background:{c["tint"]}">{strip(PROFILE[r["id"]], c["color"])}</div>'
            f'{say}<div class="art">{sticker(c["slug"], rot=-7 if flip else 7, flip=flip)}</div></div>')
    long = " long" if len(r["name"]) > 30 else ""
    kick = f'<div class="kick">Recipe {r["id"]:02d} of 50 · {E(c["name"])}</div>' if free else ""
    chap = "" if free else f"<span>{E(c['name'])}</span>"
    return f"""
<section class="page recipe" style="--c:{c['color']}">
  <div class="head"><div class="idn display" style="background:{c['color']}">{r['id']:02d}</div><div>{kick}<h1 class="display{long}">{E(r['name'])}</h1></div></div>
  <div class="meta"><span>Weird score {weird(r['weird'])}</span><span><b>{r['time']} min</b></span><span>Serves <b>{r['serves']}</b></span>{chap}</div>
  <div class="hook" style="border-color:{c['color']}"><small>The hook</small>{E(r['hook'])}</div>
  <p class="why"><b>Why it works.</b> {E(r['why'])}</p>
  <div class="cols">
    <div class="ing"><h3>Ingredients</h3><ul>{ing}</ul><div class="know">{know}</div></div>
    <div class="steps"><h3>Method</h3><ol>{steps}</ol>{tip}</div>
  </div>
  {band}
  {bottom}
  <div class="foot">{'The Starter Pack' if free else 'Unhinged Kitchen'}</div><div class="num">{pageno}</div>
</section>"""


def srow(slugs, top, size, cls=""):
    return (f'<div class="srow {cls}" style="top:{top}in;height:{size}in">'
            + "".join(sticker(s, f"{size}in", rot=(-6 if i % 2 else 6)) for i, s in enumerate(slugs)) + "</div>")


def stripes():
    return '<div class="stripes deco">' + "".join(f'<i style="background:{c[3]}"></i>' for c in CHAPTERS) + "</div>"


def chapter_page(c, idx, recipes, pageno):
    items = "".join(f"<div>{r['id']:02d} · {E(r['name'])}</div>" for r in recipes)
    return f"""
<section class="page chapter"><div class="band-bg" style="background:{c['color']}"></div>
  <div class="n display">{idx:02d}</div>
  <div class="art">{sticker(c['slug'], '3.2in', rot=6)}</div>
  <div class="t display">{E(c['name'])}</div>
  <div class="b">{E(c['blurb'])}</div>
  <div class="list">{items}</div>
  <div class="num" style="color:rgba(255,255,255,.8)">{pageno}</div>
</section>"""


def text_page(body, pageno, free=False, cls="", corner=None):
    art = f'<div class="corner">{sticker(corner, "1.35in", rot=8)}</div>' if corner else ""
    return (f'<section class="page text {cls}">{art}{body}<div class="foot">{"The Starter Pack" if free else "Unhinged Kitchen"}</div>'
            f'<div class="num">{pageno}</div></section>')


SAFETY_CARDS = [
    ("fire", "Hot oil", "Pat food dry, lower it in away from you and never leave the pan. Grease fire: heat off, lid on. Never water."),
    ("drip", "Molten sugar", "Caramel runs near 170°C/340°F and sticks to skin. Deep pan, long sleeves, cream in slowly at arm's length. No finger-tasting."),
    ("thermo", "Cook it through", "Chicken 74°C/165°F. Beef and pork mince 71°C/160°F. Reheat leftovers to 74°C/165°F. A cheap probe thermometer ends the guessing."),
    ("knife", "Raw meat", "Use its own board. Don't rinse raw chicken; it splashes germs around. Wash your hands after, and bin brines and marinades that touched raw meat."),
    ("egg", "Raw and runny eggs", "Ramen carbonara, the jammy egg and the mousse use eggs that aren't fully cooked. Use pasteurised eggs for anyone pregnant, very young, older or immunocompromised."),
    ("bowl", "Rice and leftovers", "Cool cooked rice fast, refrigerate it within an hour, eat it within a day. Everything else: fridge within 2 hours (1 on hot days), at 4°C/40°F or colder."),
    ("chili", "Knives and chilies", "Claw grip, sharp knife, board on a damp towel so it can't slide. Wash your hands after chilies and keep them away from your eyes."),
    ("peanut", "Allergies", "Every recipe lists its allergens, peanuts in red. Ask guests first. Clean knives, boards and jars between foods: one peanut-butter knife in the jam is enough."),
    ("person", "Kids and pregnancy", "No honey for babies under 1. Popcorn, nuts and dates are choking risks for under-5s. Espresso, magnesium and protein powder are for adults."),
    ("phone", "Film safely", "Tripod over hot pans, not your hand. Keep cables away from the hob and sink. Heat off before you check footage. No shot is worth a burn."),
]


def safety_page(pageno, free=False):
    cards = ""
    for i, (ic, title, body) in enumerate(SAFETY_CARDS):
        c = CHAPTERS[i % 7]
        cards += f'<div class="card sc" style="background:{c[4]}"><div class="icw" style="background:{c[3]}">{icon(ic)}</div><div><b>{title}</b>{E(body)}</div></div>'
    return text_page(f"""
<h1 class="display">Safety first.<br>Chaos second.</h1>
<p class="lead">Weird is the goal. Getting hurt isn't. Read this once; any recipe that needs extra care also carries an orange safety note.</p>
<div class="cards tight">{cards}</div>
<p class="muted" style="font-size:11.5px;line-height:1.5;margin-top:14px;max-width:none">This book is general cooking guidance, not medical or dietary advice. Follow your appliance instructions and local food-safety advice, and use your own judgment for the people you're feeding.</p>
""", pageno, free=free, corner="spicy-sweet")


# ---------- paid book ----------
def build_paid():
    plan = ["cover", "read", "toc", "safety", "why", "pantry"]
    for c in CHAPTERS:
        plan.append(("chapter", c[0]))
        plan += [("recipe", r["id"]) for r in RECIPES if r["chapter"] == c[0]]
    plan += ["calendar", "hooks", "filming", "score", "swaps", "back"]
    pn = {k: i for i, k in enumerate(plan, 1)}

    def rp(rid):
        return pn[("recipe", rid)]

    def xref(s):
        return s.replace("(recipe 26)", f"(recipe 26, p.{rp(26)})")

    pages = []
    for key in plan:
        n = pn[key]
        if key == "cover":
            pages.append(f"""
<section class="page cover"><div class="bg" style="background:{INK}"></div>
  <div class="kicker">A cookbook for the chronically online</div>
  <div class="badge" style="background:#FFC43D;color:{INK}">50 recipes<br>+ film<br>plans</div>
  <div class="title display">Unhinged<br><span style="color:#FFC43D">Kitchen</span></div>
  <div class="sub" style="top:3.62in">50 weird food combos<br>that actually taste good</div>
  {srow(SLUGS[:4], 4.62, 1.7)}
  {srow(SLUGS[4:], 6.52, 1.7, "c3")}
  <div class="tag" style="top:8.5in">Sweet on salty. Spicy on cold. Pickles where pickles shouldn't be. Every recipe comes with the hook, the on-screen text and the three shots to film it.</div>
  <div class="pills" style="top:9.55in"><span>50 recipes</span><span>50 film plans</span><span>30-day calendar</span><span>40 viral hooks</span><span>Allergen &amp; safety notes</span></div>
  {stripes()}
</section>""")
        elif key == "read":
            pages.append(text_page(f"""
<h1 class="display">Read this<br>first</h1>
<p class="lead">This isn't a cookbook of pretty pictures you'll never make. It's fifty combinations that sound wrong, taste right, and film well.</p>
<p>Every recipe has the same parts: <b>the hook</b> (what you say in the first second of the video), <b>why it works</b> (the one line of flavour science that makes people trust you), the ingredients and method, <b>flavour stats</b> so you know what you're in for, and a <b>film-it plan</b>: three shots and three on-screen text lines. Make the food, shoot the three shots, post. That's the whole system.</p>
<p>The <b>weird score</b> is how much pushback you'll get in the comments. Ones and twos are crowd-pleasers. Fives are the ones that go viral because half the comments are "absolutely not" and the other half are "I tried it and I'm sorry I doubted you". Post the fives.</p>
<h2>How to use the book</h2>
<p>Start with the <b>pantry</b> on page {pn['pantry']}: twenty ingredients cover most of the book. Then pick any chapter. The <b>30-day calendar</b> on page {pn['calendar']} gives you a recipe a day for a month if you don't want to think. The <b>hook bank</b> is for when you've run out of first lines.</p>
<h2>Allergens and safety</h2>
<p>Every recipe lists what it contains from the big eight: <b>peanuts, tree nuts, dairy, eggs, wheat/gluten, soy, fish/shellfish and sesame</b>. Peanuts are flagged in red. "Check labels" names the ingredients whose allergens change from brand to brand. The lists are a guide, not a guarantee: read packaging, assume cross-contact in shared kitchens, and skip anything that isn't safe for you or the people you're feeding. Recipes with hot oil, molten sugar, raw or runny eggs, raw meat or caffeine carry an orange <b>safety note</b>, and page {pn['safety']} covers kitchen safety in one read.</p>
{sig("Make the weird thing.<br>Then film it.", "#FF5A5F", ["sweet-salty", "umami", "drinks-dessert"])}
""", n, cls="flex", corner="breakfast"))
        elif key == "toc":
            toc = '<div class="c">Start here</div>'
            for name, k in [("Read this first", "read"), ("Kitchen safety", "safety"), ("Why weird works", "why"), ("The 20-item pantry", "pantry")]:
                toc += f'<div class="r"><span>{name}</span><span>{pn[k]}</span></div>'
            for i, c in enumerate(CHAPTERS, 1):
                cc = CH[c[0]]
                toc += f'<div class="c" style="color:{cc["color"]}">{i:02d} · {E(cc["name"])}</div>'
                for r in [r for r in RECIPES if r["chapter"] == c[0]]:
                    toc += f'<div class="r"><span>{E(r["name"])}</span><span>{rp(r["id"])}</span></div>'
            toc += '<div class="c">Bonus</div>'
            for name, k in [("30-day posting calendar", "calendar"), ("The hook bank", "hooks"), ("The filming formula", "filming"), ("Taste-test scorecard", "score"), ("Swaps & substitutions", "swaps")]:
                toc += f'<div class="r"><span>{E(name)}</span><span>{pn[k]}</span></div>'
            pages.append(text_page(f'<h1 class="display">What\'s inside</h1><div class="toc">{toc}</div>', n))
        elif key == "safety":
            pages.append(safety_page(n))
        elif key == "why":
            cards = "".join(f'<div class="card" style="background:{CHAPTERS[i % 7][4]}"><b>{E(t)}</b>{E(b)}</div>' for i, (t, b) in enumerate(PRINCIPLES))
            eq = (f'<div class="eq"><div class="eq-i">{sticker("drinks-dessert")}<span>Vanilla ice cream</span></div>'
                  f'<div class="eq-op display">+</div><div class="eq-i">{sticker("spicy-sweet", rot=-8)}<span>Chili crisp</span></div>'
                  f'<div class="eq-op display">=</div><div class="eq-r"><b class="display">Rules 1, 3 &amp; 6<br>in one spoon</b>'
                  f'Salt makes it sweeter, fat carries the heat, crunch does the rest. Recipe 09, page {rp(9)}.</div></div>')
            pages.append(text_page(f'<h1 class="display">Why weird<br>works</h1><p class="lead">Six rules explain every recipe in this book. Learn them and you can invent your own combos on camera.</p><div class="cards">{cards}</div>{eq}', n, cls="flex", corner="fat-acid"))
        elif key == "pantry":
            pantry = "".join(f"<div><b>{E(a)}</b>{E(b)}</div>" for a, b in PANTRY)
            pages.append(text_page(f'<h1 class="display">The 20-item<br>pantry</h1><p class="lead">Buy these once. They show up in most of the fifty.</p><div class="pantry">{pantry}</div>', n, corner="sweet-salty"))
        elif key[0] == "chapter":
            cc = CH[key[1]]
            pages.append(chapter_page(cc, SLUGS.index(key[1]) + 1, [r for r in RECIPES if r["chapter"] == key[1]], n))
        elif key[0] == "recipe":
            pages.append(recipe_page(BYID[key[1]], n, xref=xref))
        elif key == "calendar":
            cal = []
            buckets = {c[0]: [r for r in RECIPES if r["chapter"] == c[0]] for c in CHAPTERS}
            while len(cal) < 30:
                for c in CHAPTERS:
                    if buckets[c[0]] and len(cal) < 30:
                        cal.append(buckets[c[0]].pop(0))
            cells = "".join(f'<div style="background:{CH[r["chapter"]]["tint"]}"><b>Day {i + 1}</b>{E(r["name"])}<br><span class="muted">p.{rp(r["id"])}</span></div>' for i, r in enumerate(cal))
            pages.append(text_page(f'<h1 class="display">30-day<br>posting calendar</h1><p class="lead">One recipe a day, chapters rotated so the feed never looks samey. Weekends off if you want them.</p><div class="cal">{cells}</div>', n, corner="drinks-dessert"))
        elif key == "hooks":
            hooks = "".join(f"<div>{E(h)}</div>" for h in HOOKS)
            pages.append(text_page(f'<h1 class="display">The hook<br>bank</h1><p class="lead">Forty first lines that stop the scroll. Say it in the first second, over the first shot.</p><div class="hooks">{hooks}</div>', n, corner="texture"))
        elif key == "filming":
            arrow = f'<div class="sb-arrow">{icon("arrow", "#9a9ea8", "2.4")}</div>'

            def phone(t, slug, chip, label, bg):
                return (f'<div class="sb"><div class="sb-t">{t}</div><div class="sb-ph" style="background:{bg}">{sticker(slug)}<span class="sb-chip">{chip}</span></div>'
                        f'<div class="sb-l">{label}</div></div>')
            board = ('<div class="storyboard">' + phone("0-2 sec", "sweet-salty", "hear me out", "Shot 1<br>the wait, what?", "#FFE8E8") + arrow
                     + phone("2-8 sec", "texture", "watch this", "Shot 2<br>the transformation", "#FFF6DC") + arrow
                     + phone("8-12 sec", "breakfast", "10/10, no notes", "Shot 3<br>the payoff", "#DFF9F0") + "</div>")
            pages.append(text_page(f"""
<h1 class="display">The filming formula</h1>
<p class="lead">Every recipe's film plan is the same three-shot structure. Seven to fifteen seconds. No talking required.</p>
{board}
<div class="cards tight">
 <div class="card" style="background:#FFE8E8"><b>Shot 1 · The "wait, what?"</b>The weird ingredient meeting the normal one. Overhead or close-up. Your hook goes here as big, centred on-screen text in the first second.</div>
 <div class="card" style="background:#FFF0E0"><b>Shot 2 · The transformation</b>The pour, the melt, the flip, the drizzle. Slow it down 50%. This is the shot people rewatch.</div>
 <div class="card" style="background:#E0F7F4"><b>Shot 3 · The payoff</b>The bite, the crunch, the cross-section, the reaction. Phone close so the sound carries. End on the face or a "recipe in caption" line.</div>
 <div class="card" style="background:#ECE8FF"><b>Caption</b>The full recipe in the caption, ingredients first, so people save it. End with a question: "would you try it?"</div>
</div>
<h2>Light, sound, length</h2>
<p>Shoot by a window, phone on a stand, 9:16. Original audio on for the crunch and sizzle; add a trending sound at low volume if you want. Seven to twelve seconds for a single combo, up to twenty for a three-step recipe. Post the weird-score fours and fives first.</p>
<h2>The comment plan</h2>
<p>Pin a comment with the recipe link or "full recipe in my bio". Reply to the first ten "absolutely not" comments with "try it and report back". Those replies are free reach.</p>
""", n))
        elif key == "score":
            rows = "".join("<tr><td></td><td></td><td></td><td></td><td></td></tr>" for _ in range(15))
            pages.append(text_page(f"""
<h1 class="display">Taste-test<br>scorecard</h1>
<p class="lead">Rate every combo on camera. The numbers become content: "ranking every weird combo I tried this month".</p>
<table class="score"><tr><th>Recipe</th><th>Weird (1-5)</th><th>Taste (1-10)</th><th>Make again?</th><th>Views / saves</th></tr>{rows}</table>
<p class="hand" style="font-size:24px;color:#7B61FF;margin-top:16px">Print this page. Fill it in with a pen. Film the pen.</p>
""", n, corner="umami"))
        elif key == "swaps":
            sw = [
                ("#FFE8E8", "No chili crisp", "2 tbsp neutral oil, 1 tsp chili flakes, 1 tsp crispy fried onions, a pinch of salt and sugar."),
                ("#FFF0E0", "No hot honey", "Honey + a pinch of chili flakes, 30 seconds in the microwave. Or honey + a few drops of hot sauce."),
                ("#E0F7F4", "No miso", "A pinch of extra salt plus 1/2 tsp soy sauce. You lose some depth, not the recipe."),
                ("#ECE8FF", "No Tajín", "Equal parts chili powder and flaky salt with a grating of lime zest."),
                ("#FFF6DC", "No gochujang", "Sriracha plus a teaspoon of brown sugar and a few drops of soy sauce."),
                ("#DFF9F0", "No cottage cheese", "Thick Greek yogurt in the bowls; ricotta in the cookie dough."),
                ("#FDE2EA", "No kataifi", "Crushed cornflakes or crispy rice cereal toasted in butter. Not the same, still crunchy."),
                ("#f4f5f7", "Vegetarian or vegan", "Bacon: smoked tempeh. Fish sauce: soy sauce + lime. Parmesan: nutritional yeast + salt. Whipped egg whites: aquafaba."),
                ("#FFE8E8", "Peanut-free", "Sunflower seed butter instead of peanut butter, from a peanut-free facility. Skip the peanut garnish; toasted seeds work."),
                ("#FFF0E0", "Gluten-free", "Tamari for soy sauce; GF bread, pasta, pretzels and buns. Gochujang and imitation crab usually contain wheat."),
                ("#E0F7F4", "Dairy-free", "Plant butter, oat milk, coconut yogurt, dairy-free ice cream and chocolate. Nutritional yeast for parmesan."),
                ("#ECE8FF", "Egg-free", "Egg-free mayo; plant milk + a spoon of flour instead of egg in dredges; aquafaba for whipped whites."),
            ]
            cards = "".join(f'<div class="card" style="background:{bg}"><b>{E(t)}</b>{E(b)}</div>' for bg, t, b in sw)
            pages.append(text_page(f"""
<h1 class="display">Swaps &amp;<br>substitutions</h1>
<div class="cards">{cards}</div>
<div class="callout">{icon("warn", "#c2410c", "2.2")}<div><b>Swapping can add an allergen.</b> Re-check labels after any swap. Oven and air-fryer settings are for fan ovens; add 10-15°C (20-25°F) for conventional.</div></div>
""", n, corner="fat-acid"))
        elif key == "back":
            pages.append(f"""
<section class="page cover"><div class="bg" style="background:{INK}"></div>
  {srow(SLUGS[:4], 0.85, 1.55)}
  <div class="title display" style="font-size:84px;top:3.0in">Now go<br>make the<br><span style="color:#FFC43D">weird thing.</span></div>
  <div class="tag" style="top:5.85in;font-size:19px;color:#fff">Post it. Tag the combo. Pin the recipe. Reply to the doubters.</div>
  {srow(SLUGS[4:], 7.0, 1.55, "c3")}
  <div class="tag" style="top:9.35in;font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:#9a9ea8;max-width:7.2in;white-space:nowrap">Unhinged Kitchen · 50 weird food combos that actually taste good</div>
  {stripes()}
</section>""")
    return "".join(pages), len(plan), pn


# ---------- free book ----------
def build_free(paid_pn):
    free = [r for r in RECIPES if r.get("free")]
    plan = ["cover", "intro", "safety"] + [("recipe", r["id"]) for r in free] + ["upsell"]
    pn = {k: i for i, k in enumerate(plan, 1)}
    pages = []
    for key in plan:
        n = pn[key]
        if key == "cover":
            pages.append(f"""
<section class="page cover"><div class="bg" style="background:{INK}"></div>
  <div class="kicker">Free sample of Unhinged Kitchen</div>
  <div class="badge" style="background:#06D6A0;color:{INK}">Free<br>10 of 50<br>recipes</div>
  <div class="title display" style="font-size:112px">The<br><span style="color:#06D6A0">Starter</span><br>Pack</div>
  <div class="sub" style="top:4.42in">10 weird food combos<br>that actually taste good</div>
  {srow(SLUGS[:4], 5.4, 1.5)}
  {srow(SLUGS[4:], 7.05, 1.5, "c3")}
  <div class="tag" style="top:8.85in">A free taste of Unhinged Kitchen: ten of the fifty. Sweet on salty, spicy on cold, pickles where pickles shouldn't be.</div>
  <div class="pills" style="top:9.75in"><span>10 recipes</span><span>Flavour stats</span><span>Allergen &amp; safety notes</span></div>
  {stripes()}
</section>""")
        elif key == "intro":
            items = "".join(f'<div class="fl"><span class="fl-n display" style="background:{CH[r["chapter"]]["color"]}">{r["id"]:02d}</span>'
                            f'<span class="fl-name">{E(r["name"])}</span><span class="fl-p">p.{pn[("recipe", r["id"])]}</span></div>' for r in free)
            pages.append(text_page(f"""
<h1 class="display">Ten combos.<br>Zero excuses.</h1>
<p class="lead">Every one of these sounds wrong and tastes right. Each page gives you the hook, why it works, the ingredients, the method and its flavour stats. Make one tonight.</p>
<p>The <b>weird score</b> is how much pushback you'll get. Ones and twos are crowd-pleasers. Fives are the ones half your friends refuse to try and then ask for the recipe. The numbers are the recipe's place in the full book of fifty.</p>
<h2>What's in here</h2>
<div class="flist">{items}</div>
<h2>Allergens and safety</h2>
<p>Each recipe lists what it contains from the big eight (peanuts, tree nuts, dairy, eggs, wheat/gluten, soy, fish/shellfish, sesame), with peanuts in red. "Check labels" names the ingredients that change by brand. It's a guide, not a guarantee: read packaging and skip anything that isn't safe for you. Page {pn['safety']} covers kitchen safety, and recipes that need extra care carry an orange safety note.</p>
{sig("Make the weird thing.", "#FF5A5F", ["spicy-sweet", "texture", "fat-acid"])}
""", n, free=True, cls="flex", corner="breakfast"))
        elif key == "safety":
            pages.append(safety_page(n, free=True))
        elif key[0] == "recipe":
            pages.append(recipe_page(BYID[key[1]], n, with_film=False, free=True))
        elif key == "upsell":
            mini = recipe_page(BYID[24], paid_pn[("recipe", 24)]).replace('<section class="page recipe"', '<section class="mini-page recipe"')
            pages.append(text_page(f"""
<h1 class="display">Want the<br>other forty?</h1>
<p class="lead">Unhinged Kitchen has all fifty combos, and every single one comes with the part this free book leaves out: <b>the content plan</b>.</p>
<div class="up-grid">
<div class="cta" style="background:#FFF6DC">
 <h2 class="display">What the full book adds</h2>
 <p>• <b>40 more recipes</b> across 7 chapters: Sweet × Salty, Spicy × Sweet, Fat × Acid, Umami Bombs, Texture Chaos, Breakfast Rebellion, Drinks &amp; Dessert Chaos</p>
 <p>• A <b>film-it plan on every recipe</b>: the hook, three on-screen text ideas, the exact three shots and a caption starter</p>
 <p>• The 20-item pantry, the six flavour rules, a <b>30-day posting calendar</b>, a <b>40-line hook bank</b>, the filming formula, a scorecard and swaps for every allergy</p>
 <div class="price display">${E(args.price)}</div>
 <p class="muted" style="margin:0">Instant PDF download · {E(args.link)}</p>
</div>
<div><div class="mini-wrap">{mini}</div><div class="mini-cap">A real page from the full book:<br>recipe 24, with its film plan.</div></div>
</div>
<div class="how">
 <div class="how-i">{sticker("sweet-salty")}<div><b>1 · Pick a combo</b>Fifty that sound wrong and taste right.</div></div>
 <div class="how-i">{sticker("texture")}<div><b>2 · Film 3 shots</b>Every page tells you exactly what to shoot.</div></div>
 <div class="how-i">{sticker("drinks-dessert")}<div><b>3 · Post and reply</b>Hooks and a 30-day calendar included.</div></div>
</div>
<p class="hand" style="font-size:26px;color:#7B61FF;margin-top:16px">See you in the comments.</p>
""", n, free=True))
    return "".join(pages), len(plan)


def wrap(body, title):
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{E(title)}</title><style>{CSS}</style></head><body>{body}</body></html>"


paid, np_, paid_pn = build_paid()
free, nf = build_free(paid_pn)
open(os.path.join(OUT, "unhinged-kitchen.html"), "w").write(wrap(paid, "Unhinged Kitchen"))
open(os.path.join(OUT, "starter-pack.html"), "w").write(wrap(free, "The Starter Pack"))
print(f"paid: {np_} pages, free: {nf} pages")
