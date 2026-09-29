"""On-screen text for each clip, picked by what the clip shows.

Every variant of a clip gets a different hook (headline + body) and a
different call to action, so no two of a clip's 10 videos say the same thing.
Layout follows the reference screenshots. Every line is a health habit / tip
in the "I'm 65" voice; the theme only changes the angle so the words fit the
picture. Nothing is about makeup, hair or fashion.

Edit freely: `\n` forces a line break, `\n\n` leaves a paragraph gap.
Each theme needs at least 10 hooks so a clip's variants never repeat.
"""
from __future__ import annotations

import re

from vv_text import Hook

HOOKS: dict[str, list[tuple[str, str]]] = {
    # Every pool is health habits / tips in the "I'm 65" voice, whatever the clip
    # shows. The theme only nudges the angle (movement, skin, mornings...) so the
    # line still fits the picture; nothing is about makeup, hair or fashion.
    "wallsit": [
        ("I'm 65", "The 2-minute habit\nthat keeps my legs strong"),
        ("I'm 65 and I do this daily", "One wall sit. Two minutes.\nEvery single day."),
        ("I'm 65", "The habit most women over 50 skip\n(and really shouldn't)"),
        ("No gym at 65", "Just a wall and 2 minutes a day.\nHere's how I started."),
        ("Strong legs at 65", "start with this simple\n2-minute hold"),
        ("I'm 65", "7 boring habits that keep me\nmoving like I'm 40"),
        ("The 30-day habit", "that changed how I feel at 65.\n2 minutes a day."),
        ("I'm 65", "Do this while your coffee brews.\nYour knees will thank you."),
        ("Small habit, big difference", "2 minutes against the wall\nevery day for a month"),
        ("Start with 30 seconds", "then add 15 more each week.\nThat's how I got here at 65."),
        ("I'm 65", "Build strength quietly.\n2 minutes a day, no excuses."),
        ("The easiest exercise to stick with", "Back to the wall, knees bent.\nI'm 65 and never miss it."),
    ],
    "skincare": [
        ("I'm 65", "The morning habits that\nkeep my skin healthy"),
        ("I'm 65", "5 boring health habits I started\nin my 40s. Still doing them."),
        ("Aging well at 65", "10 small daily habits\nthat add up over the years"),
        ("I'm 65", "Water, sleep and sunscreen.\nHere's the rest of my list"),
        ("Cold water mornings", "The habit I swear by at 65.\nHere's why."),
        ("I'm 65", "Sunscreen every day,\neven when it's cloudy"),
        ("Keep it simple", "The health routine I've kept\nfor 20 years"),
        ("I'm 65", "3 things I do before bed,\nevery single night"),
        ("Consistency beats everything", "Small habits every day\nbeat big changes once a year"),
        ("I'm 65", "A 5-minute morning routine\nthat keeps me feeling young"),
        ("Hydration first", "Water, sleep and movement\ndo more than you think"),
        ("I'm 65", "The daily habits behind\nhealthy skin at any age"),
    ],
    "makeup": [
        ("I'm 65", "7 health habits that made me\nfeel better than I did at 40"),
        ("I'm 65", "The 5-minute morning routine\nI never skip"),
        ("Feel fresh at 65", "It starts with sleep, water\nand a daily walk"),
        ("I'm 65", "3 habits that keep me\nlooking and feeling well"),
        ("Stop doing this after 50", "3 habits that quietly\nage you faster"),
        ("I'm 65", "What I do every morning\nbefore I leave the house"),
        ("Glow from the inside", "The habits that show up\non your face at 65"),
        ("I'm 65", "Skip the quick fixes.\nHere's what actually works."),
        ("My daily non-negotiables", "at 65: sleep, protein,\nsunlight and movement"),
        ("I'm 65", "The boring habits\nnobody wants to hear about"),
        ("Healthy at 65", "starts the night before.\nHere's my routine."),
        ("I'm 65", "4 small habits,\n5 minutes a day. Done."),
    ],
    "hair": [
        ("I'm 65", "The health habits behind\nfeeling good at any age"),
        ("Healthy at 65", "The habits worth starting\nin your 40s"),
        ("I'm 65", "Good days start\nthe night before. Here's how."),
        ("One small swap", "that improved my sleep at 65.\nHere's the list."),
        ("I'm 65", "Less stress, more sleep.\n3 ways I protect my energy"),
        ("I'm 65", "The 10-minute morning habit\nI never skip"),
        ("Energy at 65", "The simple habits that\nkeep me going all day"),
        ("Every 8 weeks", "I check these 4 health habits.\nHere's the list."),
        ("I'm 65", "The 3-step evening routine\nfor better sleep"),
        ("Health starts at the roots", "Sleep, food, movement.\nI'm 65 and it works."),
    ],
    "fitness": [
        ("I'm 65", "Never too late to get strong.\n10 minutes a day is enough."),
        ("Your age says slow down", "I'm 65 and my body\nsays not yet"),
        ("Strength at 65", "The 3 moves I do\nevery single week"),
        ("I'm 65", "Move every day. It's the closest\nthing we have to a fountain of youth"),
        ("Stronger every year", "5 boring habits that\nkeep me moving at 65"),
        ("I'm 65", "Lift something heavy.\nStrength training is worth it at every age"),
        ("Consistency beats intensity", "20 minutes, 4 times a week.\nThat's the whole secret at 65"),
        ("I'm 65", "Don't skip leg day.\nStrong legs keep you independent."),
        ("Walk, lift, stretch", "The simple weekly plan\nI've followed since 50"),
        ("I'm 65", "Start where you are.\nEvery rep counts."),
        ("I'm 65", "How I built up to\nmy first pull-up"),
        ("The best workout", "is the one you'll actually do.\nI'm 65, here's mine"),
    ],
    "dance": [
        ("I'm 65", "Joy is a health habit.\nDance, laugh, never act your age"),
        ("Never stop moving", "I'm 65. Moving for fun\ncounts as exercise too"),
        ("I'm 65", "5 habits for your\nhappiest, healthiest decade yet"),
        ("Dance like nobody's watching", "Your heart and your mood\nwill thank you at 65"),
        ("I'm 65", "Cardio doesn't have to be boring.\nPut on a song and move for 10 minutes"),
        ("I'm 65", "The mood habit doctors\nkeep telling us about"),
        ("Say yes at 65", "It's never too late\nto learn something new"),
        ("Move for joy", "not punishment.\nThat's the whole mindset at 65"),
        ("I'm 65", "Good music, good people,\nzero excuses"),
        ("Dancing counts", "30 minutes of dancing\nis a real workout at 65"),
    ],
    "fashion": [
        ("I'm 65", "5 health habits that keep me\nconfident at any age"),
        ("I'm 65", "The 10 daily habits\nI've kept since my 40s"),
        ("Confidence at 65", "3 habits that\nchanged everything"),
        ("I'm 65", "Live for the life\nyou actually want. Here's how"),
        ("I'm 65", "Posture, sleep, protein.\nThe habits people never see"),
        ("Feel put together at 65", "It starts with these\n5 morning habits"),
        ("I'm 65", "The boring habits that\nmake the biggest difference"),
        ("Small fixes, big results", "The health habit I wish\nI'd started at 40"),
        ("I'm 65", "Life's too short\nto skip the good habits"),
        ("3 things I check daily", "at 65: water, steps,\nand sleep"),
        ("Elegance never ages", "Good posture, good food,\ngood sleep. I'm 65."),
        ("I'm 65", "Build a routine you'll keep.\nHere's mine"),
    ],
    "morning": [
        ("I'm 65", "Coffee first, then these\n3 habits before 9am"),
        ("Morning non-negotiables", "at 65: 5 small habits\nthat set up the whole day"),
        ("I'm 65", "Tried everything? These are\nthe habits actually worth your time"),
        ("For the next 8 weeks", "get obsessed with these\n10 boring habits. I'm 65 and I did."),
        ("I'm 65", "Protein at breakfast.\nThe swap that keeps me full longer"),
        ("Phone down for 30 minutes", "The morning habit that\nchanged my whole day at 65"),
        ("I'm 65", "Water, sunlight, movement,\nthen coffee"),
        ("My 7am routine at 65", "Small habits,\nbig difference"),
        ("I'm 65", "3 things I do\nbefore I open my email"),
        ("I'm 65", "The routine that makes\nevery day feel lighter"),
    ],
    "city": [
        ("I'm 65", "10 boring habits that\nquietly changed everything"),
        ("I'm 65", "Health hacks for aging well\nthat nobody tells you at 40"),
        ("5 things I stopped doing at 50", "and I feel younger\nevery year at 65"),
        ("For the next 8 weeks", "get obsessed with these\n10 boring habits. I'm 65 and I did."),
        ("I'm 65", "10,000 steps? Here's why\nwalking is still underrated"),
        ("I'm 65", "Get outside every day.\nSunlight, fresh air, a good walk"),
        ("Walking is my gym at 65", "How I make my daily walk\ncount more"),
        ("I'm 65", "3 easy green smoothies\nthat actually taste good"),
        ("The 20-minute walk", "after meals.\nI'm 65 and never skip it"),
        ("I'm 65", "Stairs, walks and\nlots of fresh air"),
    ],
    "glow": [
        ("I'm 65", "10 boring habits that\nshow up on your skin"),
        ("I'm 65", "Sleep, water, sunscreen\nand these 7 more"),
        ("Aging like fine wine", "I'm 65. Start these 10 habits\nbefore it's too late"),
        ("I'm 65", "The self-care habits\nworth making time for"),
        ("I'm 65", "Health hacks for aging well\nthat nobody talks about"),
        ("Sleep is medicine", "7 to 8 hours does more\nthan you think at 65"),
        ("I'm 65", "Self-care isn't selfish.\n10 minutes a day, just for you"),
        ("I'm 65", "Small habits that\nadd up fast"),
        ("Feel good at 65", "5 habits to start\nthis week"),
        ("I'm 65", "Your future self will thank you.\nStart these habits today"),
        ("Simple, not easy", "The daily habits that\nactually make a difference at 65"),
        ("I'm 65", "Slow mornings, early nights,\nand a lot of water"),
    ],
    "couple": [
        ("We're 65", "5 habits that keep us\nhealthy and happy together"),
        ("I'm 65", "Walking together every day.\nThe habit that keeps us close"),
        ("We're 65", "The little health habits\nthat matter most"),
        ("I'm 65", "5 habits of couples\nwho stay active for life"),
        ("Laugh together every day", "It's the easiest\nhealth habit at 65"),
        ("We're 65", "Some habits\nnever get old"),
        ("I'm 65", "The small daily rituals\nthat keep us well"),
        ("We're 65", "Easy weeknight habits\nfor more energy"),
        ("Growing healthier together", "Habits that make\nlife lighter at 65"),
        ("I'm 65", "Small moments, big health.\nHere's how we make more of them"),
    ],
}

CTAS = [
    "(read caption)", "Read caption ↓", "Here's the list ↓", "(Read Caption)", "Details in caption ↓",
    "Read caption ↓", "Save this for later ↓", "(read caption)", "Full list in caption ↓", "Read the caption ↓",
]

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


def hooks_for(theme: str, clip_index: int, n: int = 10) -> list[Hook]:
    """n different hooks for one clip. Clips of the same theme start at different
    points in the list, so neighbouring clips don't get the same line-up."""
    pool = HOOKS[theme]
    if len(pool) < n:
        raise ValueError(f"theme {theme!r} has {len(pool)} hooks; need at least {n}")
    start = (clip_index * 3) % len(pool)
    out = []
    for i in range(n):
        headline, body = pool[(start + i) % len(pool)]
        out.append(Hook(headline, body, CTAS[(clip_index + i) % len(CTAS)]))
    return out
