"""The four reference videos in Factory Intake (25 Sep batch) and the Katie clip made from each.

Text is copied verbatim from each reference (including its spelling), except the age:
Katie is 65 in every video, so the exact copies get their number redrawn (`renumber`). `elements`
are the pieces of text in the order they appear; `exact` describes where the
reference's own text layer sits so the EXACT COPY variant can lift it.
"""
from __future__ import annotations

from ref_extract import RefElement, RefSpec

REFS = {
    "SEED-04": dict(
        slug="salon-blowout", theme="hair",
        clip="hf_20260926_015426_e3d427bf-9413-4598-ab89-384296c60141.mp4",
        reference="1490276202014583bf9073dfee26e223.mp4",
        text=dict(headline="IM 65", body="Here’s 7 habits\nthat made me\nhotter in my 60s\nthan in my 30s", cta=""),
        ref_look="Heavy italic headline with black outline; white body text with soft shadow",
        exact=RefSpec(roi=(200, 860, 880, 1450), elements=[
            RefElement("headline", 870, 1030, 0.0, outline_px=8, shadow=dict(blur=7, opacity=0.55, dy=2),
                       renumber=dict(text="65", font="Montserrat-ExtraBoldItalic.ttf", scale=0.94)),
            RefElement("body", 1060, 1445, 0.0, outline_px=0, shadow=dict(blur=5, opacity=0.75, dy=2, spread=2)),
        ]),
    ),
    "SEED-05": dict(
        slug="gala-black-dress", theme="fashion",
        clip="hf_20260926_015752_5ad03c31-8300-4487-a0ab-811d80072eef.mp4",
        reference="evelynmercer.glow_3d5ab9207f3d4886a2835c89307a3234.mp4",
        text=dict(headline="I'M 65", body="SECRET HABITS I STOLE FROM\nVICTORIA SECRET MODELS SINCE I\nWAS 32",
                  cta="(READ CAPTION)"),
        ref_look="TikTok Classic white with black outline; (READ CAPTION) pops in at 2.1 s",
        exact=RefSpec(roi=(20, 900, 1060, 1395), elements=[
            RefElement("headline", 905, 1020, 0.0, outline_px=9, shadow=dict(blur=5, opacity=0.35, dy=2),
                       renumber=dict(text="65", font="TikTokSans-Bold.ttf")),
            RefElement("body", 1045, 1245, 0.0, outline_px=4, shadow=dict(blur=5, opacity=0.35, dy=2)),
            RefElement("cta", 1300, 1390, 2.1, outline_px=4, shadow=dict(blur=5, opacity=0.35, dy=2)),
        ]),
    ),
    "SEED-06": dict(
        slug="nyc-green-juice-walk", theme="city",
        clip="hf_20260926_015812_6b4769c0-8495-4298-bf00-38c0ce5248c5.mp4",
        reference="itsjennabeautyus_51b0c512925d4b8a805e3f4776982210.mp4",
        text=dict(headline="I'M 65", body="I've tried every\nf'cking thing to\nreverse my aging",
                  cta="Here's what\nactually worked 👇"),
        ref_look="Heavy sans headline with drop shadow; bold serif body; 👇 emoji",
        exact=RefSpec(roi=(200, 940, 880, 1470), extra_boxes=[(770, 1370, 860, 1460)], elements=[
            RefElement("all", 950, 1460, 0.0, outline_px=2, shadow=dict(blur=6, opacity=0.6, dx=2, dy=4),
                       renumber=dict(text="65", font="TikTokSans-Black.ttf", line_h=112)),
        ]),
    ),
    "SEED-07": dict(
        slug="paris-cafe", theme="city",
        clip="hf_20260926_015826_a2516eb5-899a-484c-8602-a4cbc917d733.mp4",
        reference="jenniferwellnesslife_49adc66b09834ef38fc8f771a54f0c4e.mp4",
        text=dict(headline="I’M 65", body="SECRET HABITS I STOLE FROM\nVICTORIA SECRET MODELS\nSINCE I WAS 32",
                  cta="(READ CAPTION)"),
        ref_look="Inline serif headline with thick black outline; all-caps sans body with outline",
        exact=RefSpec(roi=(150, 1090, 930, 1510), elements=[
            RefElement("headline", 1090, 1272, 0.0, outline_px=14, close_px=6, shadow=dict(blur=5, opacity=0.3, dy=2),
                       renumber=dict(text="65", font="PlayfairDisplay-Black.ttf", inline=(3, 2),
                                     measure="layer", stretch=1.18)),
            RefElement("body", 1285, 1505, 0.0, outline_px=4, shadow=dict(blur=4, opacity=0.35, dy=2)),
        ]),
    ),
}
