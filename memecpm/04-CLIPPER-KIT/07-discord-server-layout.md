# memecpm Discord server layout

Small on purpose. Clippers join dozens of servers; the ones they keep open are the ones where the
campaign, the rules and the payout are each one click away.

## Channels

**INFO**
- `#start-here` — pinned "how it works" (announcement D in `01-discord-announcements.md`), read-only
- `#rules` — `05-rules-and-payouts.md`, read-only
- `#apply` — the application link + "you'll hear back in 48 h", read-only
- `#announcements` — new campaigns, payout dates, read-only

**CAMPAIGNS**
- `#campaigns` — one pinned brief per live campaign (`04-campaign-brief-template.md`), read-only
- `#what-is-working` — Monday post with top clips and the pattern, read-only
- `#submissions` — bot-only log of form submissions (optional, for transparency)

**COMMUNITY** (Clipper role only)
- `#general`
- `#help` — questions; answer within a day
- `#wins` — clippers post their best numbers; social proof for recruiting screenshots
- `#payouts` — the twice-monthly "payouts sent" post with totals (no individual amounts)

**STAFF** (private)
- `#review` — approvals, rejections, disputes
- `#brands` — brand-side notes, never visible to clippers

## Roles

- `Applicant` (default on join): sees INFO only
- `Clipper` (approved): sees everything but STAFF
- `Top Clipper` (top 3 on any campaign): same as Clipper + early access to new briefs
- `Staff`

## Bots (free tier is enough)

- **Tally or Typeform → Discord webhook** for applications and submissions into `#submissions`
- **Carl-bot or MEE6** for the reaction-role "I've read the rules" gate before `Clipper` is granted
- **Google Sheets** as the ledger (see `08-tracking-sheet.md`); no need for a paid platform until the
  community is past ~50 active clippers, at which point Whop's Content Rewards is the standard upgrade

## Submission flow

1. Clipper posts → fills the campaign form (post link, page, campaign) within 30 minutes
2. Webhook drops it in `#submissions` and appends to the tracker sheet
3. At 72 h and 30 d, Evan (or a helper) records views in the sheet; the sheet computes payout
4. Payout day: sheet filters "verified, unpaid" → send payments → mark paid → DM #6 to each clipper
   → post totals in `#payouts`

## Server description (for the invite page)

> memecpm — paid clipping campaigns for skincare, wellness and pet brands. Clips already cut and
> captioned; you post, keep it live 30 days, get paid per 1,000 verified views. Tier-1 pages. Payouts
> twice a month.
