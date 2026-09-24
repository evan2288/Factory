"""On-screen text for each clip, picked by what the clip shows.

Layout follows the reference screenshots: short headline, one or two body
lines, then a "(read caption)" style call to action. Lines are tips and
prompts rather than first-person age or results claims.

Edit freely: `\n` forces a line break, `\n\n` leaves a paragraph gap.
"""
from __future__ import annotations

import re

from vv_text import Hook

H = Hook  # short alias for the table below

HOOKS: dict[str, list[Hook]] = {
    "wallsit": [
        H("2 minutes a day", "Hold this wall sit every day for a month\n\nand watch what changes...", "(read caption)"),
        H("Try this for 30 days", "One wall sit. Two minutes.\nEvery single day.", "Read caption ↓"),
        H("The 2-minute habit", "most women over 50 skip\n(and really shouldn't)", "(read caption)"),
        H("No gym needed", "Just a wall and 2 minutes a day.\nHere's how to start.", "Read caption ↓"),
        H("Strong legs at any age", "start with this simple\n2-minute hold", "(read caption)"),
        H("Hold it for 2 minutes", "Your legs and posture\nwill thank you later", "Read caption ↓"),
    ],
    "skincare": [
        H("Skincare after 50", "The simple morning steps\nworth doing every day", "Read caption ↓"),
        H("Glowing skin habits", "5 boring things to start in your 40s\nbefore it's too late", "(read caption)"),
        H("Age like fine wine", "10 small skin habits\nthat add up over the years", "Here's the list ↓"),
        H("The 30-second step", "most people skip\nin their skincare routine", "Read caption ↓"),
        H("Cold water mornings", "Why so many women are adding\nthis to their routine", "(read caption)"),
    ],
    "makeup": [
        H("Makeup after 50", "3 tiny tricks for a fresh look\nthat never looks cakey", "Here's the list ↓"),
        H("Less is more", "The 5-minute routine\nfor a natural, lifted look", "Read caption ↓"),
        H("The lip liner trick", "that makes lips look fuller\nin seconds", "(read caption)"),
        H("Red lip rules", "for looking polished\nat any age", "Read caption ↓"),
        H("Stop doing this", "3 makeup habits that can\nmake you look older", "(read caption)"),
    ],
    "hair": [
        H("Hair after 50", "4 salon secrets for shinier,\nfuller-looking hair", "Read caption ↓"),
        H("Healthy hair habits", "worth starting in your 40s", "(read caption)"),
        H("Good hair days", "start the night before.\nHere's how.", "Read caption ↓"),
    ],
    "fitness": [
        H("Never too late to get strong", "Start with 10 minutes a day\nand build from there", "(read caption)"),
        H("Your age says slow down", "Your body says not yet", "(Read Caption)"),
        H("Strength after 50", "The 3 moves worth doing\nevery single week", "Read caption ↓"),
        H("Move every day", "It's the closest thing we have\nto a fountain of youth", "(read caption)"),
        H("Stronger every year", "5 boring habits that\nkeep you moving for life", "Read caption ↓"),
    ],
    "dance": [
        H("Joy is a habit", "Dance, laugh and\nnever act your age", "(read caption)"),
        H("Never stop dancing", "Moving for fun counts\nas exercise too", "Read caption ↓"),
        H("Life's too short", "to sit this one out.\n5 habits for your happiest decade yet", "(read caption)"),
    ],
    "fashion": [
        H("Style at any age", "5 rules for dressing\nwith confidence after 50", "(read caption)"),
        H("Timeless, not trendy", "The 10 pieces every closet\nover 40 needs", "Here's the list ↓"),
        H("Confidence is the best outfit", "3 styling tricks that\nalways look expensive", "Read caption ↓"),
        H("Front row energy", "Dress for the life\nyou actually want", "(read caption)"),
    ],
    "morning": [
        H("Coffee first", "then these 3 habits\nbefore 9am", "Read caption ↓"),
        H("Morning non-negotiables", "5 small habits that\nset up the whole day", "(read caption)"),
        H("Tried so many things?", "These are the habits\nactually worth your time", "Read caption ↓"),
        H("For the next 8 weeks", "get obsessed with these\n10 boring habits", "(read caption)"),
    ],
    "city": [
        H("Walk every day", "10 boring habits that\nquietly change everything", "(read caption)"),
        H("Life hacks for aging well", "that nobody tells you\nin your 40s", "Read caption ↓"),
        H("5 things to stop doing after 50", "if you want to feel\nyounger every year", "Read caption ↓"),
        H("For the next 8 weeks", "get obsessed with these\n10 boring habits", "(read caption)"),
    ],
    "glow": [
        H("Glow from the inside out", "10 boring habits that\nshow up on your skin", "(read caption)"),
        H("Natural glow checklist", "Sleep, water, sunscreen\nand these 7 more", "Read caption ↓"),
        H("Aging like fine wine", "Start these 10 habits\nbefore it's too late", "(read caption)"),
        H("Slow mornings", "The self-care habits\nworth making time for", "Read caption ↓"),
    ],
    "couple": [
        H("Still choosing each other", "5 habits that keep love\nfun at any age", "(read caption)"),
    ],
}

# First matching rule wins, so order matters (e.g. "redrobe_lipstick" is makeup).
THEME_RULES = [
    ("wallsit", r"wall_?sit"),
    ("skincare", r"skincare|face_?wash|face_?splash|face_?dunk|ice_?bowl|serum|under_?eye|cream"),
    ("makeup", r"lipstick|lip_?liner|lip_?gloss|mascara|makeup|brow|blush|sponge|foundation"),
    ("hair", r"hair|salon"),
    ("fitness", r"gym|push_?up|pull_?up|lunge|workout|yoga|squat|plank|running|jog|stretch|pilates"),
    ("dance", r"danc|party"),
    ("couple", r"couple"),
    ("fashion", r"fashion|dress|suit|lace|boutique|heels|blouse|front_?row|runway|gallery|elevator|outfit"),
    ("morning", r"coffee|mug|yogurt|desk|breakfast|matcha|car_"),
    ("city", r"nyc|paris|street|sidewalk|oldtown|walk|smoothie|city"),
    ("glow", r"selfie|sunlit|closeup|mirror|robe|glow"),
]


def theme_for(name: str) -> str:
    n = name.lower()
    for theme, pat in THEME_RULES:
        if re.search(pat, n):
            return theme
    return "glow"


def assign_hooks(sources: list[dict]) -> None:
    """Give each source a hook, rotating through its theme so neighbours differ."""
    seen: dict[str, int] = {}
    for s in sources:
        t = s.setdefault("theme", theme_for(s["original_name"]))
        k = seen.get(t, 0)
        seen[t] = k + 1
        s["hook"] = HOOKS[t][k % len(HOOKS[t])]
