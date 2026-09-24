# Video variants

Turns each source clip into 10 ready-to-post variants with on-screen text, and files them in
Google Drive under **AI Influencers / katie / BANK** with a tracker sheet.

## What each variant gets

- **On-screen text** in the style of the reference screenshots: headline, one or two body lines,
  and a "(read caption)" / "Read caption ↓" call to action. Text is matched to what the clip shows
  (wall sit, skincare, makeup, fashion, fitness, morning, city, dance...) and lives in `engine/hooks.py`.
- **A different look per variant**: 4 font styles (TikTok Classic, condensed, Impact-style headline,
  all caps), sizes from 92% to 112%, and white, cream or a pastel picked to suit the clip's colours.
  Some variants put the CTA in a solid white box.
- **Face-safe placement**: faces are detected on frames throughout the clip (three detectors, including
  one that finds heads in profile). Text never overlaps a face at any point in the clip, stays centred,
  and keeps between 22% and 78% of the screen height (clear of the app's top bar and caption area).
- **Solid, still text**: rendered once and laid over every frame, so it can't move, flicker or fade.
  Letters are fully opaque with a dark outline.
- **An invisible colour tweak**: brightness within ~1.5/255 levels, contrast and gamma within 0.8%,
  saturation within 1.6%, very light sharpening. Each variant is a distinct encode that looks the same.
- **Quality**: 1080x1920 H.264 (CRF 16, preset slow), original audio, same length. Re-encoding alone
  measures ~49 dB PSNR against the source (visually lossless).

## BANK layout (Google Drive)

```
BANK/
  Katie Video Bank Tracker     Google Sheet: one row per video, Status dropdown, account, date
  README_FOR_AI.md             how AI tools should read and update the bank
  bank_index.json              every clip and video with Drive ids, text and style
  1_FRESH_veo3/<clip>/         <GROUP>-<CODE>_<slug>_v01.mp4 ... _v10.mp4
  2_REUSED_veo3/<clip>/        (source clips that were posted before)
  3_SEEDANCE_2.5/<clip>/
  _previews/                   one contact sheet per clip showing all 10 variants
  _data/                       render details per clip
  _posted_log/                 fallback posting log for AI tools that can't edit the sheet
```

## Running it

1. **One-time Drive access.** On a computer with a browser, install rclone (`winget install Rclone.Rclone`
   on Windows) and run `rclone authorize "drive"`. Sign in, allow access, and copy the `{...}` token it
   prints. In Claude Code on the web, open the environment menu in the session title bar, choose Edit,
   and add an environment variable named `GDRIVE_TOKEN` with that token as its value. New sessions pick
   it up. (Revoke any time at myaccount.google.com/permissions.)
2. In a new cloud session:
   ```bash
   cd video-variants/engine
   bash setup.sh
   python3 run_batch.py --limit 1      # optional smoke test
   python3 run_batch.py                # everything; safe to rerun, it resumes
   ```

One clip at a time: `python3 make_variants.py SRC.mp4 OUT_DIR --id SEED-02 --slug wallsit --theme wallsit`.
