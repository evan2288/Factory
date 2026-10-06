"""Builds the paid and free cookbooks as print-ready HTML (then pdf.mjs turns them into PDFs).

Usage: python3 build.py [--author "@handle"] [--price 19] [--link "https://..."]
"""
import argparse
import html
import os

from recipes import CHAPTERS, RECIPES, FREE_IDS, PANTRY, PRINCIPLES, HOOKS

ap = argparse.ArgumentParser()
ap.add_argument("--author", default="")
ap.add_argument("--price", default="19")
ap.add_argument("--link", default="link in bio")
args = ap.parse_args()

OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)
CH = {c[0]: dict(slug=c[0], name=c[1], blurb=c[2], color=c[3], tint=c[4]) for c in CHAPTERS}
E = html.escape

FONTS = open(os.path.join(os.path.dirname(__file__), "fonts", "embedded.css")).read()
CSS = FONTS + """
@page { size: 8.5in 11in; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: 'DM Sans', system-ui, sans-serif; color: #15161a; background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { width: 8.5in; height: 11in; position: relative; overflow: hidden; page-break-after: always; break-after: page; padding: 0.6in 0.65in; background: #fff; }
.page:last-child { page-break-after: auto; }
.display { font-family: 'Anton', Impact, sans-serif; text-transform: uppercase; letter-spacing: 0.01em; line-height: 0.92; }
.hand { font-family: 'Caveat', cursive; }
.muted { color: #6b6f7a; }
.num { position: absolute; bottom: 0.35in; right: 0.65in; font-size: 10px; color: #9a9ea8; letter-spacing: 0.12em; }
.foot { position: absolute; bottom: 0.35in; left: 0.65in; font-size: 10px; color: #9a9ea8; letter-spacing: 0.12em; text-transform: uppercase; }

/* cover */
.cover { padding: 0; }
.cover .bg { position: absolute; inset: 0; }
.cover .title { position: absolute; left: 0.65in; right: 0.65in; top: 1.3in; color: #fff; font-size: 128px; }
.cover .sub { position: absolute; left: 0.65in; right: 0.65in; top: 6.1in; color: #fff; font-size: 30px; font-weight: 700; line-height: 1.15; }
.cover .tag { position: absolute; left: 0.65in; top: 7.9in; color: #fff; font-size: 16px; opacity: 0.9; max-width: 5.4in; line-height: 1.5; }
.cover .author { position: absolute; left: 0.65in; bottom: 0.7in; color: #fff; font-size: 14px; letter-spacing: 0.2em; text-transform: uppercase; }
.cover .badge { position: absolute; right: 0.65in; top: 0.7in; width: 1.55in; height: 1.55in; border-radius: 50%; background: #15161a; color: #fff; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 13px; font-weight: 700; line-height: 1.2; padding: 10px; transform: rotate(8deg); }
.blob { position: absolute; border-radius: 50%; opacity: 0.9; }

/* chapter opener */
.chapter { padding: 0; }
.chapter .band { position: absolute; inset: 0; }
.chapter .n { position: absolute; left: 0.65in; top: 0.8in; color: rgba(255,255,255,0.55); font-size: 240px; }
.chapter .t { position: absolute; left: 0.65in; right: 0.65in; top: 4.6in; color: #fff; font-size: 92px; }
.chapter .b { position: absolute; left: 0.65in; right: 1.6in; top: 7.4in; color: #fff; font-size: 19px; line-height: 1.5; }
.chapter .list { position: absolute; left: 0.65in; right: 0.65in; bottom: 0.7in; color: rgba(255,255,255,0.92); font-size: 12.5px; columns: 2; column-gap: 24px; line-height: 1.7; }

/* recipe */
.recipe .head { display: flex; gap: 14px; align-items: flex-start; margin-bottom: 10px; }
.recipe .idn { flex: none; width: 54px; height: 54px; border-radius: 14px; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 26px; }
.recipe h1 { margin: 0; font-size: 44px; }
.recipe .meta { display: flex; gap: 18px; margin: 10px 0 14px; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #6b6f7a; align-items: center; }
.recipe .meta b { color: #15161a; }
.weird { display: inline-flex; gap: 4px; vertical-align: middle; }
.weird i { width: 11px; height: 11px; border-radius: 50%; background: #e2e4e9; display: inline-block; }
.hook { border-left: 5px solid; padding: 10px 16px; margin: 0 0 14px; font-size: 19px; line-height: 1.3; font-weight: 500; background: #fafafb; border-radius: 0 10px 10px 0; }
.hook small { display: block; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #6b6f7a; margin-bottom: 4px; }
.why { font-size: 13.5px; line-height: 1.55; color: #3c3f48; margin: 0 0 16px; }
.why b { color: #15161a; }
.cols { display: grid; grid-template-columns: 2.55in 1fr; gap: 26px; }
.ing h3, .steps h3, .film h3 { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; margin: 0 0 8px; color: #6b6f7a; }
.ing ul { list-style: none; margin: 0; padding: 0; font-size: 13px; line-height: 1.5; }
.ing li { padding: 5px 0; border-bottom: 1px solid #ececf0; }
.steps ol { margin: 0; padding-left: 0; list-style: none; counter-reset: s; font-size: 13.5px; line-height: 1.55; }
.steps li { position: relative; padding: 0 0 10px 34px; counter-increment: s; }
.steps li::before { content: counter(s); position: absolute; left: 0; top: 0; width: 24px; height: 24px; border-radius: 50%; color: #fff; font-weight: 700; font-size: 12px; display: flex; align-items: center; justify-content: center; }
.film { margin-top: 14px; border-radius: 14px; padding: 14px 16px; }
.film .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; font-size: 12.5px; line-height: 1.45; }
.film .grid div b { display: block; font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 3px; }
.film .texts { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
.film .cap { margin-top: 12px; font-size: 12.5px; line-height: 1.45; color: #3c3f48; }
.film .cap b { display: block; font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 3px; color: #15161a; }
.film .texts span { background: #15161a; color: #fff; border-radius: 999px; padding: 4px 10px; font-size: 11.5px; font-weight: 500; }
.tip { margin-top: 12px; font-size: 12.5px; color: #3c3f48; }
.tip b { font-weight: 700; }

/* text pages */
.text h1 { font-size: 64px; margin: 0 0 18px; }
.text h2 { font-size: 22px; margin: 22px 0 8px; }
.text p { font-size: 14.5px; line-height: 1.6; margin: 0 0 12px; max-width: 6.4in; }
.text .lead { font-size: 18px; line-height: 1.5; color: #3c3f48; }
.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 16px; }
.card { border-radius: 14px; padding: 16px 18px; font-size: 13px; line-height: 1.5; }
.card b { display: block; font-size: 15px; margin-bottom: 4px; }
.pantry { columns: 2; column-gap: 28px; font-size: 13px; line-height: 1.5; margin-top: 12px; }
.pantry div { break-inside: avoid; padding: 8px 0; border-bottom: 1px solid #ececf0; }
.pantry b { display: block; }
.toc { columns: 2; column-gap: 32px; font-size: 13px; line-height: 1.75; margin-top: 10px; }
.toc .c { font-weight: 700; margin-top: 10px; break-after: avoid; }
.toc .r { display: flex; justify-content: space-between; gap: 8px; }
.toc .r span:last-child { color: #9a9ea8; }
.cal { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-top: 14px; }
.cal div { border-radius: 10px; padding: 9px 9px 8px; font-size: 11px; line-height: 1.3; min-height: 0.95in; }
.cal b { display: block; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 4px; opacity: 0.7; }
.hooks { columns: 2; column-gap: 28px; font-size: 12.5px; line-height: 1.45; margin-top: 10px; }
.hooks div { break-inside: avoid; padding: 5px 0 5px 24px; position: relative; border-bottom: 1px solid #ececf0; }
.hooks div::before { content: '“'; position: absolute; left: 0; top: 2px; font-family: 'Anton'; font-size: 24px; color: #c7cad2; }
.score { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; }
.score th, .score td { border: 1px solid #e2e4e9; padding: 10px 8px; text-align: left; }
.score th { background: #f4f5f7; font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; }
.score td { height: 40px; }
.cta { border-radius: 18px; padding: 26px 28px; margin-top: 22px; }
.cta h2 { margin: 0 0 8px; font-size: 32px; }
.cta p { margin: 0 0 8px; font-size: 14px; }
.cta .price { font-size: 48px; margin: 10px 0 2px; }
.big-list { font-size: 15px; line-height: 1.65; margin: 10px 0 0 18px; padding: 0; }
"""


def weird(n):
    return '<span class="weird">' + "".join(f'<i style="background:{"var(--c)" if i < n else "#e2e4e9"}"></i>' for i in range(5)) + "</span>"


def recipe_page(r, pageno, with_film=True, free=False):
    c = CH[r["chapter"]]
    ing = "".join(f"<li>{E(i)}</li>" for i in r["ingredients"])
    steps = "".join(f"<li>{E(s)}</li>" for s in r["steps"])
    film = ""
    if with_film:
        shots = "".join(f"<div><b>{E(s.split(':')[0])}</b>{E(s.split(':', 1)[1].strip())}</div>" for s in r["film"])
        texts = "".join(f"<span>{E(t)}</span>" for t in r["text"])
        caption = f"{r['hook']} Full recipe below. Would you try it? #weirdfoodcombos #{c['slug'].replace('-', '')}"
        film = (f'<div class="film" style="background:{c["tint"]}"><h3>Film it · 3 shots</h3><div class="grid">{shots}</div>'
                f'<div class="texts">{texts}</div><div class="cap"><b>Caption starter</b>{E(caption)}</div></div>')
    tip = f'<div class="tip"><b>Tip.</b> {E(r["tip"])}</div>' if r.get("tip") else ""
    return f"""
<section class="page recipe" style="--c:{c['color']}">
  <div class="head"><div class="idn display" style="background:{c['color']}">{r['id']:02d}</div><h1 class="display">{E(r['name'])}</h1></div>
  <div class="meta"><span>Weird score {weird(r['weird'])}</span><span><b>{r['time']} min</b></span><span>Serves <b>{r['serves']}</b></span><span>{E(c['name'])}</span></div>
  <div class="hook" style="border-color:{c['color']}"><small>The hook</small>{E(r['hook'])}</div>
  <p class="why"><b>Why it works.</b> {E(r['why'])}</p>
  <div class="cols">
    <div class="ing"><h3>Ingredients</h3><ul>{ing}</ul></div>
    <div class="steps"><h3>Method</h3><ol style="--c:{c['color']}">{steps}</ol>{tip}</div>
  </div>
  {film}
  <div class="foot">{'The Starter Pack' if free else 'Unhinged Kitchen'}</div><div class="num">{pageno}</div>
</section>"""


# Steps use the chapter colour for the counters.
CSS += "\n.steps li::before { background: var(--c); }"


def cover(title, sub, tag, badge, bg, blobs):
    author = f'<div class="author">{E(args.author)}</div>' if args.author else ""
    bl = "".join(f'<div class="blob" style="{b}"></div>' for b in blobs)
    return f"""
<section class="page cover"><div class="bg" style="background:{bg}">{bl}</div>
  <div class="badge">{badge}</div>
  <div class="title display">{title}</div>
  <div class="sub">{sub}</div>
  <div class="tag">{tag}</div>{author}
</section>"""


def chapter_page(c, idx, recipes, pageno):
    items = "".join(f"<div>{r['id']:02d} · {E(r['name'])}</div>" for r in recipes)
    return f"""
<section class="page chapter"><div class="band" style="background:{c['color']}"></div>
  <div class="n display">{idx:02d}</div>
  <div class="t display">{E(c['name'])}</div>
  <div class="b">{E(c['blurb'])}</div>
  <div class="list">{items}</div>
  <div class="num" style="color:rgba(255,255,255,.7)">{pageno}</div>
</section>"""


def text_page(body, pageno, free=False, style=""):
    return f'<section class="page text" style="{style}">{body}<div class="foot">{"The Starter Pack" if free else "Unhinged Kitchen"}</div><div class="num">{pageno}</div></section>'


def build_paid():
    pages = []
    pages.append(cover("Unhinged<br>Kitchen", "50 weird food combos<br>that actually taste good",
                       "Sweet on salty. Spicy on cold. Pickles where pickles shouldn't be. Every recipe comes with the hook, the on-screen text and the three shots to film it.",
                       "50 recipes<br>+ content plans", "#15161a",
                       ["left:-1.2in;top:5.2in;width:5in;height:5in;background:#FF5A5F",
                        "right:-1.6in;top:2.4in;width:4.2in;height:4.2in;background:#FFC43D",
                        "left:3.2in;bottom:-2.2in;width:4.6in;height:4.6in;background:#7B61FF;opacity:.85",
                        "right:0.4in;bottom:1.2in;width:2in;height:2in;background:#2EC4B6"]))
    n = 2
    # Intro
    pages.append(text_page(f"""
<h1 class="display">Read this<br>first</h1>
<p class="lead">This isn't a cookbook with pretty pictures of things you'll never make. It's fifty combinations that sound wrong, taste right, and film well.</p>
<p>Every recipe has the same five parts: <b>the hook</b> (what you say in the first second of the video), <b>why it works</b> (the one line of flavour science that makes people trust you), the ingredients and method, and a <b>film-it plan</b>: three shots and three on-screen text lines. Make the food, shoot the three shots, post. That's the whole system.</p>
<p>The <b>weird score</b> is how much pushback you'll get in the comments. Ones and twos are crowd-pleasers. Fives are the ones that go viral because half the comments are "absolutely not" and the other half are "I tried it and I'm sorry I doubted you". Post the fives.</p>
<h2>How to use the book</h2>
<p>Start with the <b>Pantry</b> page: twenty ingredients cover most of the book. Then pick any chapter. The <b>30-day calendar</b> at the back gives you a recipe a day for a month if you don't want to think. The <b>hook bank</b> is for when you've run out of first lines.</p>
<p class="hand" style="font-size:24px;color:#FF5A5F;margin-top:26px">Make the weird thing. Then film it.</p>
""", n)); n += 1
    # TOC
    toc = ""
    pn = {}
    cur = n + 3  # intro(2), toc(3), principles(4), pantry(5) -> chapters from 6
    cur = 6
    for i, c in enumerate(CHAPTERS, 1):
        cc = CH[c[0]]
        rs = [r for r in RECIPES if r["chapter"] == cc["slug"]]
        pn[cc["slug"]] = cur
        cur += 1
        toc += f'<div class="c" style="color:{cc["color"]}">{i:02d} · {E(cc["name"])}</div>'
        for r in rs:
            pn[r["id"]] = cur
            toc += f'<div class="r"><span>{E(r["name"])}</span><span>{cur}</span></div>'
            cur += 1
    bonus_start = cur
    toc += '<div class="c">Bonus</div>'
    for name in ["30-day posting calendar", "The hook bank", "The filming formula", "Taste-test scorecard", "Substitutions"]:
        toc += f'<div class="r"><span>{name}</span><span>{cur}</span></div>'
        cur += 1
    pages.append(text_page(f'<h1 class="display">What\'s<br>inside</h1><div class="toc">{toc}</div>', n)); n += 1
    # Principles
    cards = "".join(f'<div class="card" style="background:{CHAPTERS[i % 7][4]}"><b>{E(t)}</b>{E(b)}</div>' for i, (t, b) in enumerate(PRINCIPLES))
    pages.append(text_page(f'<h1 class="display">Why weird<br>works</h1><p class="lead">Six rules explain every recipe in this book. Learn them and you can invent your own combos on camera.</p><div class="cards">{cards}</div>', n)); n += 1
    # Pantry
    pantry = "".join(f"<div><b>{E(a)}</b>{E(b)}</div>" for a, b in PANTRY)
    pages.append(text_page(f'<h1 class="display">The 20-item<br>pantry</h1><p class="lead">Buy these once. They show up in most of the fifty.</p><div class="pantry">{pantry}</div>', n)); n += 1
    # Chapters + recipes
    for i, c in enumerate(CHAPTERS, 1):
        cc = CH[c[0]]
        rs = [r for r in RECIPES if r["chapter"] == cc["slug"]]
        pages.append(chapter_page(cc, i, rs, n)); n += 1
        for r in rs:
            pages.append(recipe_page(r, n)); n += 1
    # Calendar
    order = [r for r in RECIPES]
    # Mix chapters so a week never has two from the same chapter back to back.
    cal = []
    buckets = {c[0]: [r for r in RECIPES if r["chapter"] == c[0]] for c in CHAPTERS}
    while len(cal) < 30:
        for c in CHAPTERS:
            if buckets[c[0]] and len(cal) < 30:
                cal.append(buckets[c[0]].pop(0))
    cells = "".join(f'<div style="background:{CH[r["chapter"]]["tint"]}"><b>Day {i + 1}</b>{E(r["name"])}<br><span class="muted">p.{pn[r["id"]]}</span></div>' for i, r in enumerate(cal))
    pages.append(text_page(f'<h1 class="display">30-day<br>posting calendar</h1><p class="lead">One recipe a day, chapters rotated so the feed never looks samey. Weekends off if you want them.</p><div class="cal">{cells}</div>', n)); n += 1
    # Hook bank
    hooks = "".join(f"<div>{E(h)}</div>" for h in HOOKS)
    pages.append(text_page(f'<h1 class="display">The hook<br>bank</h1><p class="lead">Forty first lines that stop the scroll. Say it in the first second, over the first shot.</p><div class="hooks">{hooks}</div>', n)); n += 1
    # Filming formula
    pages.append(text_page("""
<h1 class="display">The filming<br>formula</h1>
<p class="lead">Every recipe's film plan is the same three-shot structure. Seven to fifteen seconds. No talking required.</p>
<div class="cards">
 <div class="card" style="background:#FFE8E8"><b>Shot 1 · The "wait, what?"</b>The weird ingredient meeting the normal one. Overhead or close-up. Your hook line goes here as on-screen text, big, centred, in the first second.</div>
 <div class="card" style="background:#FFF0E0"><b>Shot 2 · The transformation</b>The pour, the melt, the flip, the drizzle. Slow it down 50%. This is the shot people rewatch.</div>
 <div class="card" style="background:#E0F7F4"><b>Shot 3 · The payoff</b>The bite, the crunch, the cross-section, the reaction. Put the phone close to the food so the sound carries. End on the reaction face or the "read caption" text.</div>
 <div class="card" style="background:#ECE8FF"><b>Caption</b>The full recipe in the caption, ingredients first. People save videos with the recipe in the caption at about twice the rate. End with a question: "would you try it?"</div>
</div>
<h2>Light, sound, length</h2>
<p>Shoot by a window, phone on a stand, 9:16. Original audio on for the crunch and sizzle; add a trending sound at low volume if you want. Seven to twelve seconds for a single combo; up to twenty for a three-step recipe. Post the weird-score 4s and 5s first.</p>
<h2>The comment plan</h2>
<p>Pin a comment with the recipe link or "full recipe in my bio". Reply to the first ten "absolutely not" comments with "try it and report back"; those replies are free reach.</p>
""", n)); n += 1
    # Scorecard
    rows = "".join("<tr><td></td><td></td><td></td><td></td><td></td></tr>" for _ in range(9))
    pages.append(text_page(f"""
<h1 class="display">Taste-test<br>scorecard</h1>
<p class="lead">Rate every combo on camera. The numbers become content: "ranking every weird combo I tried this month".</p>
<table class="score"><tr><th>Recipe</th><th>Weird (1–5)</th><th>Taste (1–10)</th><th>Would make again?</th><th>Views / saves</th></tr>{rows}</table>
<p class="hand" style="font-size:22px;color:#7B61FF;margin-top:18px">Print this page. Fill it in with a pen. Film the pen.</p>
""", n)); n += 1
    # Substitutions
    pages.append(text_page("""
<h1 class="display">Swaps &amp;<br>substitutions</h1>
<div class="cards">
 <div class="card" style="background:#FFE8E8"><b>No chili crisp</b>Mix 2 tbsp neutral oil, 1 tsp chili flakes, 1 tsp fried onions or crushed peanuts, pinch of salt and sugar.</div>
 <div class="card" style="background:#FFF0E0"><b>No hot honey</b>Honey + a pinch of chili flakes, 30 seconds in the microwave. Or honey + a few drops of hot sauce.</div>
 <div class="card" style="background:#E0F7F4"><b>No miso</b>Use a pinch of extra salt plus 1/2 tsp soy sauce. You lose some depth, not the recipe.</div>
 <div class="card" style="background:#ECE8FF"><b>No Tajín</b>Equal parts chili powder and flaky salt with a grating of lime zest.</div>
 <div class="card" style="background:#FFF6DC"><b>No gochujang</b>Sriracha plus a teaspoon of brown sugar and a few drops of soy.</div>
 <div class="card" style="background:#DFF9F0"><b>No cottage cheese</b>Thick Greek yogurt in the bowls; ricotta in the cookie dough.</div>
 <div class="card" style="background:#FDE2EA"><b>No kataifi</b>Crushed cornflakes or crispy rice cereal toasted in butter. Not the same, still crunchy.</div>
 <div class="card" style="background:#f4f5f7"><b>Vegetarian / vegan</b>Bacon → smoked tempeh or coconut bacon; fish sauce → soy + a squeeze of lime; parmesan → nutritional yeast + salt; eggs in mousse → whipped aquafaba.</div>
</div>
<p style="margin-top:22px" class="muted">Temperatures: oven and air-fryer settings are for fan ovens. Add 10–15°C (20–25°F) for conventional. Cook poultry to 74°C/165°F.</p>
""", n)); n += 1
    pages.append(f"""
<section class="page cover"><div class="bg" style="background:#15161a">
<div class="blob" style="left:-1in;top:-1in;width:4in;height:4in;background:#FF7A1A"></div>
<div class="blob" style="right:-1.4in;bottom:-1.2in;width:5in;height:5in;background:#06D6A0"></div></div>
<div class="title display" style="font-size:72px;top:3.6in">Now go<br>make the<br>weird thing.</div>
<div class="tag" style="top:7.6in">Post it. Tag the combo. Pin the recipe. Reply to the doubters.</div>
<div class="author">{E(args.author) if args.author else 'Unhinged Kitchen'}</div>
</section>""")
    return "".join(pages), n


def build_free():
    pages = []
    pages.append(cover("The<br>Starter<br>Pack", "10 weird food combos<br>that actually taste good",
                       "A free taste of Unhinged Kitchen: ten of the fifty. Sweet on salty, spicy on cold, pickles where pickles shouldn't be.",
                       "Free<br>sample", "#15161a",
                       ["left:-1.4in;top:4.6in;width:5in;height:5in;background:#2EC4B6",
                        "right:-1.6in;top:1.8in;width:4.4in;height:4.4in;background:#FF5A5F",
                        "left:3.6in;bottom:-2.4in;width:4.6in;height:4.6in;background:#FFC43D;opacity:.9"]))
    n = 2
    pages.append(text_page(f"""
<h1 class="display">Ten combos.<br>Zero excuses.</h1>
<p class="lead">Every one of these sounds wrong and tastes right. Each page gives you the hook, why it works, the ingredients and the method. Make one tonight.</p>
<p>The <b>weird score</b> is how much pushback you'll get. Ones and twos are crowd-pleasers. Fives are the ones half your friends refuse to try and then ask for the recipe.</p>
<h2>What's in here</h2>
<ol class="big-list">{"".join(f"<li>{E(r['name'])}</li>" for r in RECIPES if r.get('free'))}</ol>
<p class="hand" style="font-size:24px;color:#FF5A5F;margin-top:22px">Make the weird thing.</p>
""", n, free=True)); n += 1
    for r in [r for r in RECIPES if r.get("free")]:
        pages.append(recipe_page(r, n, with_film=False, free=True)); n += 1
    pages.append(text_page(f"""
<h1 class="display">Want the<br>other forty?</h1>
<p class="lead">Unhinged Kitchen has all fifty combos, and every single one comes with the part this free book leaves out: <b>the content plan</b>.</p>
<div class="cta" style="background:#FFF6DC">
 <h2 class="display">What the full book adds</h2>
 <p>• 40 more recipes across 7 chapters: Sweet × Salty, Spicy × Sweet, Fat × Acid, Umami Bombs, Texture Chaos, Breakfast Rebellion, Drinks &amp; Dessert Chaos</p>
 <p>• A <b>film-it plan on every recipe</b>: the hook line, three on-screen text ideas, and the exact three shots to film</p>
 <p>• The 20-item pantry, the six flavour rules so you can invent your own combos, a 30-day posting calendar, a 40-line hook bank, the filming formula, a taste-test scorecard and a substitutions page</p>
 <div class="price display">${E(args.price)}</div>
 <p class="muted">Instant PDF download · {E(args.link)}</p>
</div>
<p class="hand" style="font-size:24px;color:#7B61FF;margin-top:26px">See you in the comments.</p>
""", n, free=True)); n += 1
    return "".join(pages), n


def wrap(body, title):
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{E(title)}</title><style>{CSS}</style></head><body>{body}</body></html>"


paid, np_ = build_paid()
free, nf = build_free()
open(os.path.join(OUT, "unhinged-kitchen.html"), "w").write(wrap(paid, "Unhinged Kitchen"))
open(os.path.join(OUT, "starter-pack.html"), "w").write(wrap(free, "The Starter Pack"))
print(f"paid: {np_} pages, free: {nf} pages")
