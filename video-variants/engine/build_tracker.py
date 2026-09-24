"""Build the BANK tracker (Google Sheet), bank_index.json and README_FOR_AI.md."""
from __future__ import annotations

import datetime as dt
import json
import os

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

TRACKER_NAME = "Katie Video Bank Tracker"
STATUSES = ["Not posted", "Posted", "Skip", "Needs fix"]
# group -> (sheet tab / label, short description)
GROUPS = {
    "NEW": ("New Veo3", "new Veo3 clips, never posted before"),
    "OLD": ("Old reused Veo3", "Veo3 clips that were already posted before"),
    "SEED": ("Seedance 2.5", "Seedance 2.5 clips made on Higgsfield"),
}
HEAD_FONT = Font(bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="222222")


def file_url(i):
    return f"https://drive.google.com/file/d/{i}/view" if i else ""


def folder_url(i):
    return f"https://drive.google.com/drive/folders/{i}" if i else ""


def one_line(t: dict) -> str:
    body = " ".join(t["body"].split())
    return " / ".join(x for x in (t["headline"], body, t["cta"]) if x)


def music_label(m: dict) -> str:
    if m.get("track"):
        how = "added" if m["mode"] == "music_only" else "mixed under clip sound"
        return f"{m['track'].rsplit('.', 1)[0]} ({how})"
    return "clip's own music"


def collect(sources, rc, remote, bank_id, work):
    files = json.loads(rc("lsjson", "-R", "--files-only", remote(bank_id)))
    dirs = json.loads(rc("lsjson", "-R", "--dirs-only", remote(bank_id)))
    fid = {f["Path"]: f["ID"] for f in files}
    did = {d["Path"]: d["ID"] for d in dirs}
    rows = []
    for s in sources:
        folder = f"{s['source_id']}_{s['slug']}"
        jpath = os.path.join(work, "bank", s["bank_folder"], folder, f"{folder}.json")
        if not os.path.exists(jpath):
            continue
        res = json.load(open(jpath))
        base = f"{s['bank_folder']}/{folder}"
        entry = {
            "source_id": s["source_id"], "group": s["group"], "group_label": GROUPS[s["group"]][0],
            "theme": s["theme"], "note": s["note"], "original_name": s["original_name"],
            "original_drive_id": s["original_drive_id"], "sound": res.get("sound", {}).get("plan", {}),
            "folder": base, "folder_drive_id": did.get(base),
            "preview_drive_id": fid.get(f"_previews/{folder}_preview.jpg"),
            "data_drive_id": fid.get(f"_data/{folder}.json"),
            "variants": [],
        }
        for v in res["variants"]:
            path = f"{base}/{v['file']}"
            entry["variants"].append({
                "video_id": v["video_id"], "file": v["file"], "path": path, "drive_id": fid.get(path),
                "url": file_url(fid.get(path)), "variant": v["variant"], "text": v["text"], "style": v["style"],
                "family": v["family"], "size_pct": v["size_pct"], "headline_color": v["headline_color"],
                "body_color": v["body_color"], "cta_box": v["cta_box"], "text_box_xywh": v["text_box"],
                "music": v["music"], "duration_s": v["duration_s"], "bytes": v["bytes"],
            })
        rows.append(entry)
    return rows, fid, did


def _header(ws, cols):
    ws.append([c for c, _ in cols])
    for i, (_, w) in enumerate(cols, 1):
        cell = ws.cell(1, i)
        ws.column_dimensions[cell.column_letter].width = w
        cell.font, cell.fill = HEAD_FONT, HEAD_FILL


VIDEO_COLS = [("Video ID", 16), ("Status", 13), ("Posted to (account)", 22), ("Date posted", 13),
              ("Clip ID", 12), ("Variant", 8), ("Theme", 10), ("On-screen text", 62), ("Text style", 40),
              ("Music", 36), ("Video", 9), ("File name", 44), ("Folder", 46), ("Drive file ID", 36),
              ("Length (s)", 10)]


def build_xlsx(rows, path):
    wb = Workbook()
    wb.remove(wb.active)
    tabs = {}
    for g, (label, _) in GROUPS.items():
        if not any(e["group"] == g for e in rows):
            continue
        ws = wb.create_sheet(label)
        _header(ws, VIDEO_COLS)
        n = 1
        for e in (e for e in rows if e["group"] == g):
            for v in e["variants"]:
                n += 1
                ws.append([v["video_id"], "Not posted", "", "", e["source_id"], v["variant"], e["theme"],
                           one_line(v["text"]), v["style"], music_label(v["music"]),
                           f'=HYPERLINK("{v["url"]}","Open")' if v["url"] else "", v["file"], e["folder"],
                           v["drive_id"] or "", round(v["duration_s"] or 0, 1)])
        end_col = ws.cell(1, len(VIDEO_COLS)).column_letter
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = f"A1:{end_col}{n}"
        dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=False)
        ws.add_data_validation(dv)
        dv.add(f"B2:B{max(n, 2)}")
        rng = f"A2:{end_col}{max(n, 2)}"
        for status, colour in (("Posted", "C8E6C9"), ("Skip", "E0E0E0"), ("Needs fix", "FFCDD2")):
            ws.conditional_formatting.add(rng, FormulaRule(formula=[f'$B2="{status}"'],
                                                           fill=PatternFill("solid", fgColor=colour)))
        tabs[g] = label

    src = wb.create_sheet("Clips")
    _header(src, [("Clip ID", 12), ("Group", 16), ("Theme", 10), ("Original clip", 36), ("Posted", 8),
                  ("Variants", 9), ("Sound", 44), ("Preview (all 10)", 16), ("Folder", 10), ("Notes", 40)])
    for r, e in enumerate(rows, 2):
        tab = tabs[e["group"]]
        src.append([e["source_id"], e["group_label"], e["theme"], e["original_name"],
                    f"=COUNTIFS('{tab}'!$E:$E,A{r},'{tab}'!$B:$B,\"Posted\")", len(e["variants"]),
                    e["sound"].get("reason", ""),
                    f'=HYPERLINK("{file_url(e["preview_drive_id"])}","See preview")' if e["preview_drive_id"] else "",
                    f'=HYPERLINK("{folder_url(e["folder_drive_id"])}","Open")' if e["folder_drive_id"] else "",
                    e["note"]])
    src.freeze_panes = "B2"

    how = wb.create_sheet("How to use")
    how.column_dimensions["A"].width = 120
    for line in HOW_TO:
        how.append([line])
    for row in how.iter_rows():
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
    how["A1"].font = Font(bold=True, size=14)
    wb.save(path)


HOW_TO = [
    "Katie Video Bank - how to use this sheet",
    "There is one tab per group: New Veo3 (never posted), Old reused Veo3 (clips posted before) and Seedance 2.5. "
    "Every row is one finished video.",
    "After posting a video, set Status to Posted (the row turns green) and fill in the account and date. "
    "Use Skip for ones you don't want and Needs fix for problems.",
    "Filter the Status column to 'Not posted' to see what's left. Filter by Theme or Clip ID to find a type of video.",
    "Each clip has 10 variants (v01-v10): the same footage with different on-screen text, font, size, colour and "
    "background music, plus an invisible colour tweak. Spread variants of the same clip across days and accounts.",
    "The Clips tab shows one row per original clip, how many of its variants are posted, and a preview image of all 10.",
    "Folders in BANK: 1_NEW_veo3, 2_OLD_reused_veo3 and 3_SEEDANCE_2.5, with one sub-folder per clip. "
    "_previews has a contact sheet per clip. _data and bank_index.json are for AI tools.",
    "AI tools: read README_FOR_AI.md in the BANK folder first.",
]


def readme(rows, tracker_id, bank_id, generated):
    total = sum(len(e["variants"]) for e in rows)
    lines = []
    for g, (label, desc) in GROUPS.items():
        c = sum(1 for e in rows if e["group"] == g)
        v = sum(len(e["variants"]) for e in rows if e["group"] == g)
        if c:
            lines.append(f"- **{label}** ({desc}): {c} clip{'s' * (c != 1)} -> {v} videos, tab \"{label}\"")
    groups = "\n".join(lines)
    return f"""# Katie Video Bank - README for AI tools

Generated {generated}. {total} videos from {len(rows)} source clip{'s' * (len(rows) != 1)}.
{groups}

## Where things are
- BANK folder id: `{bank_id}` (AI Influencers / katie / BANK)
- Tracker (Google Sheet): "{TRACKER_NAME}", id `{tracker_id or 'see BANK folder'}`
  - One tab per group (see above). One row per video. Column B **Status** is the source of truth:
    `Not posted` | `Posted` | `Skip` | `Needs fix`. Columns C/D = account posted to, date posted.
  - Tab **Clips**: one row per source clip, posted count, preview link.
- `bank_index.json`: every clip and video with Drive file ids, on-screen text, style, music and folder.
  (It does not track posting; the sheet does.)
- `_previews/<clip>_preview.jpg`: all 10 variants of a clip side by side.
- `_data/<clip>.json`: full render details for a clip (text position, colour grade, sound, checks).
- `_posted_log/`: fallback posting log (see below).

## Folders and naming
- `1_NEW_veo3/`, `2_OLD_reused_veo3/`, `3_SEEDANCE_2.5/`, then one sub-folder per clip.
- Video id: `<GROUP>-<CODE>-vNN`, e.g. `NEW-R01-v03`, `OLD-07-v10`, `SEED-02-v01`.
- File: `<GROUP>-<CODE>_<slug>_vNN.mp4` inside `<group folder>/<GROUP>-<CODE>_<slug>/`.
- OLD clips were posted before; prefer NEW and SEED when choosing.
- Each of a clip's 10 variants has different on-screen text, font/size/colour and background music.
- All videos are 1080x1920 H.264 with AAC audio, same length as the source clip.

## Picking videos to post
1. Read the sheet tab for the group you want. Only pick rows with Status `Not posted`.
2. Treat a video as posted if the sheet says `Posted` OR a matching file exists in `_posted_log/`.
3. Avoid posting two variants of the same Clip ID to the same account within 7 days,
   and mix themes across a day's posts.
4. Get the file by its Drive file id (sheet column N, or `bank_index.json`).

## Marking a video as posted
- Preferred: edit the sheet row - Status `Posted`, account in column C, date (YYYY-MM-DD) in column D.
- If you cannot edit sheets, create an empty text file in `_posted_log/` named
  `<video_id>__<account>__<YYYY-MM-DD>.txt` (e.g. `NEW-R01-v03__katieswellness__2026-09-25.txt`).
  Whoever next has sheet access should copy these into the sheet.
"""


def build_and_upload(sources, rc, remote, bank_id, work, log):
    rows, fid, _ = collect(sources, rc, remote, bank_id, work)
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = os.path.join(work, "tracker")
    os.makedirs(out, exist_ok=True)
    xlsx = os.path.join(out, f"{TRACKER_NAME}.xlsx")
    build_xlsx(rows, xlsx)

    top = json.loads(rc("lsjson", remote(bank_id)))
    existing = [f for f in top if f["Name"].startswith(TRACKER_NAME)]
    name = TRACKER_NAME if not existing else f"{TRACKER_NAME} - rebuilt {generated[:10]}"
    if existing:
        log(f"A tracker already exists (keeping it, since it holds posting marks); new one saved as '{name}'")
    rc("copyto", xlsx, remote(bank_id, f"{name}.xlsx"), "--drive-import-formats", "xlsx")
    top = json.loads(rc("lsjson", remote(bank_id)))
    tracker = next((f for f in top if f["Name"].startswith(name)), None)
    tracker_id = tracker["ID"] if tracker else None

    index = {
        "about": "Katie video bank: every finished video with Drive ids. Posting status lives in the tracker sheet.",
        "generated": generated, "bank_folder_id": bank_id,
        "tracker": {"name": name, "id": tracker_id},
        "groups": {g: {"label": label, "description": desc} for g, (label, desc) in GROUPS.items()},
        "statuses": STATUSES,
        "clips": rows,
    }
    with open(os.path.join(out, "bank_index.json"), "w") as f:
        json.dump(index, f, indent=2)
    with open(os.path.join(out, "README_FOR_AI.md"), "w") as f:
        f.write(readme(rows, tracker_id, bank_id, generated))
    rc("copyto", os.path.join(out, "bank_index.json"), remote(bank_id, "bank_index.json"))
    rc("copyto", os.path.join(out, "README_FOR_AI.md"), remote(bank_id, "README_FOR_AI.md"))
    rc("mkdir", remote(bank_id, "_posted_log"))
    log(f"Tracker: https://docs.google.com/spreadsheets/d/{tracker_id}" if tracker_id else "Tracker uploaded")
