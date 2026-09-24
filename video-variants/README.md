# Video variants

Turns each source clip into 10 ready-to-post variants with on-screen text and background music,
and files them in Google Drive under **AI Influencers / katie / BANK** with a tracker sheet.

## What each variant gets

- **Its own on-screen text.** All 10 variants of a clip have a different headline, body line and
  call to action ("(read caption)", "Read caption ↓", "Here's the list ↓"...), laid out like the
  reference screenshots. Lines are matched to what the clip shows (wall sit, skincare, makeup, hair,
  fitness, dance, fashion, morning, city, glow, couple). Edit them in `engine/hooks.py`.
- **Its own look**: 4 font styles (TikTok Classic, condensed, Impact-style headline, all caps),
  sizes from 92% to 112%, and white, cream, yellow or a pastel picked to suit the clip's colours.
  Some variants put the CTA in a solid white box.
- **Music**: every video has music. Clips whose own sound is already music keep it. Otherwise one of 18
  original tracks (`engine/music/tracks`, composed for this project, royalty-free) is mixed in:
  under the clip's own sound (10 dB below speech) or on its own when the clip is silent. The style fits
  the theme (upbeat for fitness and dance, house for fashion, piano/lo-fi for skincare and glow, acoustic
  for morning and city), and each variant uses a different track or a different part of one.
- **Face-safe placement**: faces are detected on frames throughout the clip (three detectors, including
  one that finds heads in profile). Text never overlaps a face at any point in the clip, stays centred
  within 82% of the width, and keeps between 22% and 78% of the screen height.
- **Solid, still text**: rendered once and laid over every frame, so it can't move, flicker or fade.
- **An invisible colour tweak**: brightness within ~1.5/255 levels, contrast and gamma within 0.8%,
  saturation within 1.6%, very light sharpening (measured 40+ dB from the original: looks identical).
- **Quality**: 1080x1920 H.264 (CRF 16, preset slow), same length as the source.

## BANK layout (Google Drive)

```
BANK/
  Katie Video Bank Tracker     Google Sheet: one tab per group, one row per video,
                               Status dropdown (Not posted / Posted / Skip / Needs fix), account, date
  README_FOR_AI.md             how AI tools should read and update the bank
  bank_index.json              every clip and video with Drive ids, text, style and music
  1_NEW_veo3/<clip>/           new Veo3 clips: <GROUP>-<CODE>_<slug>_v01.mp4 ... _v10.mp4
  2_OLD_reused_veo3/<clip>/    old Veo3 clips that were posted before
  3_SEEDANCE_2.5/<clip>/       Seedance 2.5 clips
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
Regenerate the music library: `python3 music_gen.py` (needs `fluidsynth`; downloads the GeneralUser GS
soundfont, which is free for commercial music).
