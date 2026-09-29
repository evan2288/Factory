# memecpm — the clipping offer

Proposed structure, prices and reasoning. Change any number; the site copy in `03-SITE-COPY.md` is written
so the tiers can be edited in one place.

## Positioning

**"Send one video. Get a hundred clips. Pay for what gets seen."**

Three things the offer has that competitors don't, in the order they should appear on the page:

1. **Proof in orders, not views.** $10,453 tracked Amazon sales, 299 orders, organic only, third-party
   dashboard. Lead with it.
2. **Volume.** 100–300 posting-ready clips a month from footage the brand already has, at a fraction of
   freelancer cost, delivered as an organised bank with a tracker so a team can post from it without
   thinking.
3. **Distribution you can pay for by the view.** A page network plus a vetted clipper community, with
   comment-to-DM automation that carries the brand's link. This is the "CPM" in memecpm.

## The tiers

| | **Pilot** | **Clips** | **Clips + Distribution** | **Pay per view** |
|---|---|---|---|---|
| Price | **$200 once** | **$750 / month** | **$1,500 / month** | **$2.50 per 1,000 verified views**, $1,000 minimum/month |
| Clips | 25 clips from 1 video, 7 days | 100 clips/month from up to 4 source videos | 200 clips/month from up to 8 source videos | 200 clips/month included |
| Hook variants | 2 per clip | 3 per clip | 3 per clip | 3 per clip |
| Delivered as | Drive folder + tracker sheet | Weekly batches to a Drive bank + tracker | Weekly batches + posting calendar | Weekly batches + posting calendar |
| Captions, 9:16 reframe, on-screen hook, music bed | ✓ | ✓ | ✓ | ✓ |
| Posted daily across the memecpm page network | – | – | ✓ | ✓ |
| Clipper community campaign (paid per view) | – | – | starter pool included ($300 of views) | the whole plan |
| Free guide + ManyChat comment-to-DM funnel | – | – | ✓ | ✓ |
| Weekly report (views, clicks, top clips) | – | Monthly | Weekly | Weekly, with verified view log |
| Rounds of changes per batch | 1 | 3 | 3 | 3 |
| Credited to month one | ✓ | | | |

**Add-ons**
- AI spokesperson videos (the current product) for brands with no footage: **$25 per finished video**,
  minimum 10. Same consistent character across every video.
- Extra source videos: **$75 each**.
- Rush (48-hour first batch): **+$200**.

### Why these numbers

- **$750 for 100 clips = $7.50 a clip.** Freelancers charge $15–60; the cheapest DIY tool is $19–99 and
  the brand still does the work. $7.50 with delivery, captions and a tracker is obviously good value and
  still leaves margin because production is automated.
- **$1,500 keeps the current top price** but roughly quintuples the deliverable (200 clips vs 40 videos)
  and adds a real posting network. Existing prospects see the same number with a much bigger "what
  you get".
- **$2.50 CPM** sits above the $1–1.25 clippers typically get on Whop-style networks (margin for
  memecpm and for QC/verification) and far below the $10–30 brands pay Meta. It also lets the page
  say, truthfully, "cheaper than ads, and you only pay for views that happened". $1,000 minimum keeps
  it from being a tyre-kicker product and equals 400k verified views.
- **The $200 pilot stays.** It's the best-converting element on the current page. Making it "25 clips
  from one video" instead of "5 AI videos" makes it feel five times bigger for the same money.
- **Founding-client cap:** "taking 5 brands this quarter at these rates". A real number makes the
  founding-rate line believable.

### Unit economics (rough, for Evan only)

- Clips tier: production cost is cloud time (currently promo credits; later the desktop clip maker at
  near-zero marginal cost) plus ~1 hour of Evan's review per batch. Margin is essentially the whole
  $750.
- Distribution tier: posting to owned pages costs time (scheduler + ~30 min/day). The $300 starter
  clipper pool at ~$1.25/1k = ~240k views bought for the brand, funded from the $1,500.
- Pay-per-view: charge $2.50, pay clippers $1.00–1.50, keep $1.00–1.50 per 1,000 for QC, verification,
  briefing and the pages network. At $1,000/month that's $400–600 gross margin plus the clips are
  already produced by the pipeline.

## What "a clip" means (define it on the page and in contracts)

A finished clip is: 9:16 (1080×1920), 8–60 seconds, cut from the client's footage at a moment chosen
for a hook, with the speaker kept in frame, burned-in captions, an on-screen hook line in the first
second, a music bed where appropriate, exported in H.264 ready to post, and listed in the tracker with
its hook text, source timestamp and suggested caption. Each hook variant is a different opening line
and/or text style on the same cut; variants count toward the clip total (100 clips = ~33 cuts × 3 hooks).
Put this definition in the FAQ so "100 clips" is never argued about later.

## Fulfilment: how the pipeline produces a batch

1. **Intake.** Client uploads footage to a shared Drive folder (or sends links). Brief form captures:
   product, approved claims, banned claims, CTA, link, brand words, competitors not to mention.
2. **Transcribe** each source (Whisper). Build a moment list: quotes, demonstrations, before/afters,
   numbers, objections answered, anything with a natural hook. Score by hook strength + self-containment.
3. **Cut** the top moments into 8–60 s segments with clean in/out points (sentence boundaries, silence).
4. **Reframe to 9:16** with face/subject tracking (the same detectors as the Katie engine), keeping the
   speaker centred and the text-safe zones clear.
5. **Captions** (word-timed, TikTok style) + **hook text** in the first frame from a hook library
   tuned per client (the `hooks.py` pattern: themed lines, never repeated within a batch).
6. **Music bed** at −16 LUFS under speech from the original-track library, or the clip's own audio kept
   when it is already music.
7. **Variants:** 2–3 hooks per cut, text style/colour rotated, invisible micro-grade so posts don't
   trip duplicate detection across accounts.
8. **QC:** face-overlap check, caption timing check, loudness check, contact-sheet preview per source.
9. **Deliver:** Drive bank per client (`<Client>/BANK/<month>/<source>/…`), tracker Google Sheet
   (Status dropdown, hook text, suggested caption, posted-to, date), `README_FOR_AI.md` so the client's
   own AI tools can pull from it.
10. **Distribution** (if bought): posting calendar, page-network scheduling, clipper brief sent to the
    community with the rules in `04-CLIPPER-KIT/`, view verification, weekly report.

Items 2–9 are a build on top of `video-variants/engine` (transcription + moment selection + cutting +
reframing are the new parts). Roughly two days of engine work to get a first client batch out.

## Who it's for (say it on the page)

Best fit: skincare, hair, wellness, supplement and pet brands on Amazon, TikTok Shop or Shopify **who
already have footage** (founder videos, demos, UGC, a podcast or a YouTube channel). Also creators and
coaches with long-form content who want short-form volume without hiring an editor.

Not a fit: brands with zero footage who don't want the AI add-on; anything in restricted categories
(gambling, adult, crypto without compliance review); anyone who wants to buy fake engagement.

## Risk reversal (keep + extend)

- **On time or your money back.** First batch within 7 days of the brief.
- **Up to 3 rounds of changes per batch.** Same as now.
- **Pilot is a deposit.** $200 comes off month one.
- **New: unusable-clip replacement.** Any clip you can't post for a reason on our side (bad cut,
  caption error, wrong aspect) is replaced free, no cap.
- **New: pay-per-view is verified.** Views are counted from platform analytics screenshots at 72 hours
  and 30 days; anything flagged as boosted or bot traffic is removed before billing.

## Objections and the answers (feed the FAQ)

- *"I don't have footage."* → AI add-on, or we script a 20-minute founder video for you to film on your
  phone and clip from that.
- *"Who owns the clips?"* → You do, outright, once the invoice is paid. We keep the right to show them
  as examples unless you say no.
- *"Will clips get my account banned?"* → We post on our network and on clippers' pages, not yours,
  unless you ask. Every paid post carries #ad or a paid-partnership label.
- *"What counts as a view?"* → Platform-reported views on posts that stayed live 30 days, tier-1
  audience majority, engagement above the platform floor. Same rules the big campaigns use.
- *"Can I use the clips in ads?"* → Yes, included.
- *"What if a clip says something we can't claim?"* → The brief lists approved and banned claims;
  every batch is checked against it before delivery.
