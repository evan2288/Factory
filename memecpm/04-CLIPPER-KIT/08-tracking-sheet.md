# Campaign tracker sheet (Google Sheets)

One workbook per campaign, or one workbook with a tab per campaign. Columns for the `Submissions` tab:

| Column | Type | Notes |
|---|---|---|
| Submitted at | timestamp | from the form webhook |
| Clipper | text | Discord handle |
| Page | URL | the page the clip was posted on |
| Post link | URL | required |
| Clip ID | text | from the content folder tracker (e.g. `BRAND-03-v02`) |
| Platform | dropdown | TikTok / Reels / Shorts |
| Views 72 h | number | filled by Evan |
| Likes 72 h | number | |
| Views 30 d | number | the paid number |
| Likes 30 d | number | |
| Engagement 30 d | formula | `=IF(Views30>0, Likes30/Views30, "")` |
| Live at 30 d | checkbox | |
| Caption OK | checkbox | required line + tag present |
| Rules OK | checkbox | >10 s, captions, #ad, folder clip |
| Verified | formula | `=AND(LiveAt30d, CaptionOK, RulesOK, Engagement30d>=Floor)` |
| Payable views | formula | `=IF(Verified, Views30d, 0)` |
| Payout | formula | `=Payable/1000*Rate` (Rate and Floor live in the `Settings` tab) |
| Paid | checkbox | |
| Paid on | date | |
| Notes | text | rejection reason, dispute |

`Settings` tab: Rate per 1,000, Engagement floor, Campaign pool, Pool spent (`=SUMIF(Paid,TRUE,Payout)`),
Pool remaining.

`Clippers` tab (one row per clipper): handle, pages, tier-1 %, approved date, total verified views
(`SUMIF`), total paid, strikes, Top Clipper flag.

`Brand report` tab (what the brand sees, exported weekly): posts live, total verified views, top 10
posts with links, engagement average, clicks (from the link tracker / ManyChat), spend.

The Katie BANK tracker (`video-variants/engine/build_tracker.py`) already generates a sheet with
dropdowns, conditional formatting and COUNTIFS from a JSON index; the same script can produce this
workbook from the campaign's clip index with a small column change.
