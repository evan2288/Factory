"""On-screen text for each clip, picked by what the clip shows.

Every variant of a clip gets a different hook (headline + body) and a
different call to action, so no two of a clip's 10 videos say the same thing.
Layout follows the reference screenshots. Lines are tips and prompts rather
than first-person age or results claims.

Edit freely: `\n` forces a line break, `\n\n` leaves a paragraph gap.
Each theme needs at least 10 hooks so a clip's variants never repeat.
"""
from __future__ import annotations

import re

from vv_text import Hook

HOOKS: dict[str, list[tuple[str, str]]] = {
    "wallsit": [
        ("2 minutes a day", "Hold this wall sit every day for a month\n\nand watch what changes..."),
        ("Try this for 30 days", "One wall sit. Two minutes.\nEvery single day."),
        ("The 2-minute habit", "most women over 50 skip\n(and really shouldn't)"),
        ("No gym needed", "Just a wall and 2 minutes a day.\nHere's how to start."),
        ("Strong legs at any age", "start with this simple\n2-minute hold"),
        ("Hold it for 2 minutes", "Your legs and posture\nwill thank you later"),
        ("The wall sit challenge", "30 days. 2 minutes a day.\nAre you in?"),
        ("Do this while your coffee brews", "a 2-minute wall sit\nevery single morning"),
        ("Small habit, big difference", "2 minutes against the wall\nevery day for a month"),
        ("Start with 30 seconds", "then add 15 more each week\nuntil you hit 2 minutes"),
        ("Build strength quietly", "2 minutes a day, no equipment,\nno excuses"),
        ("The easiest exercise to stick with", "Back to the wall, knees bent,\nhold for 2 minutes"),
    ],
    "skincare": [
        ("Skincare after 50", "The simple morning steps\nworth doing every day"),
        ("Glowing skin habits", "5 boring things to start in your 40s\nbefore it's too late"),
        ("Age like fine wine", "10 small skin habits\nthat add up over the years"),
        ("The 30-second step", "most people skip\nin their skincare routine"),
        ("Cold water mornings", "Why so many women are adding\nthis to their routine"),
        ("Sunscreen every day", "even when it's cloudy.\nHere's the rest of the list"),
        ("Keep it simple", "Cleanse, moisturise, protect.\nThe routine that actually lasts"),
        ("Night routine check", "3 steps to do before bed,\nevery single night"),
        ("Your skin loves consistency", "Small steps every day\nbeat big routines once a week"),
        ("Skincare you can stick to", "A 5-minute routine\nfor busy mornings"),
        ("Don't skip your neck", "The skincare step\nmost of us forget"),
        ("Hydration first", "Water, moisturiser and sleep\ndo more than you think"),
    ],
    "makeup": [
        ("Makeup after 50", "3 tiny tricks for a fresh look\nthat never looks cakey"),
        ("Less is more", "The 5-minute routine\nfor a natural, lifted look"),
        ("The lip liner trick", "that makes lips look fuller\nin seconds"),
        ("Red lip rules", "for looking polished\nat any age"),
        ("Stop doing this", "3 makeup habits that can\nmake you look older"),
        ("Brows frame everything", "Soft strokes, not harsh lines.\nHere's how"),
        ("Cream blush > powder", "for a fresh, dewy glow\nthat lasts all day"),
        ("Skip the heavy foundation", "Try this lighter routine\nfor a natural finish"),
        ("Mascara tip", "Wiggle at the root,\nthen sweep up"),
        ("Glow in 5 minutes", "The quick routine\nfor busy mornings"),
        ("Makeup that lifts", "Where to place blush and highlighter\nfor a fresher look"),
        ("Soft glam, zero effort", "4 products,\n5 minutes, done"),
    ],
    "hair": [
        ("Hair after 50", "4 salon secrets for shinier,\nfuller-looking hair"),
        ("Healthy hair habits", "worth starting in your 40s"),
        ("Good hair days", "start the night before.\nHere's how."),
        ("Silk pillowcase?", "One small swap\nyour hair will love"),
        ("Heat less, shine more", "3 ways to style\nwithout frying your hair"),
        ("The salon blowout trick", "you can do at home\nin 10 minutes"),
        ("Volume at the roots", "The simple trick\nfor fuller-looking hair"),
        ("Trim every 8 weeks", "and 4 more habits\nfor healthy ends"),
        ("Hair flip ready", "The 3-step routine\nfor soft, bouncy hair"),
        ("Scalp care matters", "Healthy hair starts\nat the roots"),
    ],
    "fitness": [
        ("Never too late to get strong", "Start with 10 minutes a day\nand build from there"),
        ("Your age says slow down", "Your body says not yet"),
        ("Strength after 50", "The 3 moves worth doing\nevery single week"),
        ("Move every day", "It's the closest thing we have\nto a fountain of youth"),
        ("Stronger every year", "5 boring habits that\nkeep you moving for life"),
        ("Lift something heavy", "Strength training is\nworth it at every age"),
        ("Consistency beats intensity", "20 minutes, 4 times a week.\nThat's the whole secret"),
        ("Don't skip leg day", "Strong legs keep you\nmoving for decades"),
        ("Walk, lift, stretch", "The simple weekly plan\nthat actually works"),
        ("Start where you are", "Every rep counts.\nHere's a beginner plan"),
        ("Pull-up goals", "How to build up to\nyour first one"),
        ("The best workout", "is the one you'll actually do.\nFind yours"),
    ],
    "dance": [
        ("Joy is a habit", "Dance, laugh and\nnever act your age"),
        ("Never stop dancing", "Moving for fun counts\nas exercise too"),
        ("Life's too short", "to sit this one out.\n5 habits for your happiest decade yet"),
        ("Dance like nobody's watching", "Your heart and your mood\nwill thank you"),
        ("Cardio doesn't have to be boring", "Put on a song\nand move for 10 minutes"),
        ("Find your happy place", "Good music\nand a dance floor"),
        ("Say yes to the dance class", "It's never too late\nto learn something new"),
        ("Move for joy", "not punishment.\nThat's the whole mindset"),
        ("Friday night energy", "Good music, good people,\nzero excuses"),
        ("Dancing counts", "30 minutes of dancing\nis a real workout"),
    ],
    "fashion": [
        ("Style at any age", "5 rules for dressing\nwith confidence after 50"),
        ("Timeless, not trendy", "The 10 pieces every closet\nover 40 needs"),
        ("Confidence is the best outfit", "3 styling tricks that\nalways look expensive"),
        ("Front row energy", "Dress for the life\nyou actually want"),
        ("The little black dress rule", "Every closet needs one.\nHere's how to style it"),
        ("Heels or flats?", "How to look put together\nin both"),
        ("Quiet luxury on a budget", "5 pieces that always\nlook expensive"),
        ("Tailoring is everything", "The small fix that makes\nany outfit look better"),
        ("Dress up on a Tuesday", "Life's too short\nfor boring outfits"),
        ("The perfect fit", "3 things to check\nbefore you buy"),
        ("Elegance never ages", "Simple lines, good fabric,\ngreat posture"),
        ("Build a capsule wardrobe", "20 pieces,\nendless outfits"),
    ],
    "morning": [
        ("Coffee first", "then these 3 habits\nbefore 9am"),
        ("Morning non-negotiables", "5 small habits that\nset up the whole day"),
        ("Tried so many things?", "These are the habits\nactually worth your time"),
        ("For the next 8 weeks", "get obsessed with these\n10 boring habits"),
        ("Protein at breakfast", "The simple swap\nthat keeps you full longer"),
        ("Phone down for 30 minutes", "The morning habit\nthat changes your whole day"),
        ("Slow down your mornings", "Water, sunlight, movement,\nthen coffee"),
        ("Your 7am routine", "Small habits,\nbig difference"),
        ("Start the day on purpose", "3 things to do\nbefore you open your email"),
        ("Main character mornings", "The routine that makes\nevery day feel lighter"),
    ],
    "city": [
        ("Walk every day", "10 boring habits that\nquietly change everything"),
        ("Life hacks for aging well", "that nobody tells you\nin your 40s"),
        ("5 things to stop doing after 50", "if you want to feel\nyounger every year"),
        ("For the next 8 weeks", "get obsessed with these\n10 boring habits"),
        ("10,000 steps?", "Here's why walking is\nstill underrated"),
        ("Get outside every day", "Sunlight, fresh air\nand a good walk"),
        ("Walking is the new gym", "How to make your daily walk\ncount more"),
        ("Green smoothie season", "3 easy recipes\nthat actually taste good"),
        ("The 20-minute walk", "after meals.\nA habit worth trying"),
        ("Your city is your gym", "Stairs, walks and\nlots of fresh air"),
    ],
    "glow": [
        ("Glow from the inside out", "10 boring habits that\nshow up on your skin"),
        ("Natural glow checklist", "Sleep, water, sunscreen\nand these 7 more"),
        ("Aging like fine wine", "Start these 10 habits\nbefore it's too late"),
        ("Slow mornings", "The self-care habits\nworth making time for"),
        ("Life hacks for aging well", "that nobody talks about"),
        ("Sleep is skincare", "7 to 8 hours does more\nthan you think"),
        ("Self-care isn't selfish", "10 minutes a day,\njust for you"),
        ("The glow-up list", "Small habits that\nadd up fast"),
        ("Feel good at every age", "5 habits to start\nthis week"),
        ("Your future self will thank you", "Start these habits today"),
        ("Simple, not easy", "The daily habits that\nactually make a difference"),
        ("Soft life routine", "Slow mornings, early nights,\nand a lot of water"),
    ],
    "couple": [
        ("Still choosing each other", "5 habits that keep love\nfun at any age"),
        ("Date night never stops", "Keep the spark alive\nwith these small habits"),
        ("Love looks good on you", "The little things\nthat matter most"),
        ("Best friends first", "5 habits of couples\nwho last"),
        ("Laugh together every day", "It's the easiest\nrelationship habit"),
        ("Mirror selfie tradition", "Some things\nnever get old"),
        ("Still getting ready together", "The small rituals\nthat keep you close"),
        ("Keep dating each other", "Ideas for easy\nweeknight dates"),
        ("Growing better together", "Habits that make\nlife lighter"),
        ("Small moments, big love", "Here's how to\nmake more of them"),
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
