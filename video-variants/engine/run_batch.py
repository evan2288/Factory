"""Batch: Drive source folders -> 10 text variants per clip -> Drive BANK folder.

    python run_batch.py            # everything (resumes where it left off)
    python run_batch.py --limit 2  # first 2 clips only (smoke test)
    python run_batch.py --no-upload --only FRESH-R01

Needs GDRIVE_TOKEN in the environment: the JSON token printed by
`rclone authorize "drive"` (see ../README.md). Work files live in $VV_WORK
(default /home/user/vv-work) so reruns skip finished clips.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from hooks import theme_for  # noqa: E402

BANK_FOLDER_ID = "1K2HSgUVV4k6Na-7X1i008AIlmV7QF0QJ"  # AI Influencers/katie/BANK
SOURCES = [
    # group, Drive folder id (or local dir), BANK sub-folder, note for the tracker
    ("NEW", "15OwffDOBfUBH8nZ2ziWiK8ytU0uEIoFw", "1_NEW_veo3", "New Veo3 clip (never posted)"),
    ("OLD", "1XV5WfJepS-HvrUXc1E2GC76ejcyB1ZNm", "2_OLD_reused_veo3", "Old reused Veo3 clip (posted before)"),
    ("SEED", os.path.join(HERE, "..", "batches", "batch-01", "seedance-2.5"), "3_SEEDANCE_2.5", "Seedance 2.5 (Higgsfield)"),
]
# The Seedance files have no descriptive names, so their themes are set by hand.
SEED_META = {
    "seedance-2.5_01.mp4": ("undereye-skincare", "skincare"),
    "seedance-2.5_02.mp4": ("wallsit-living-room", "wallsit"),
    "seedance-2.5_03.mp4": ("makeup-sponge", "makeup"),
}
WORK = os.environ.get("VV_WORK", "/home/user/vv-work")
RCLONE_CONF = os.path.join(WORK, "rclone.conf")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------ rclone

def rclone_bin() -> str:
    for p in (shutil.which("rclone"), "/tmp/gobuild/bin/rclone", os.path.join(WORK, "bin", "rclone")):
        if p and os.path.exists(p):
            return p
    log("building rclone from source (about a minute)...")
    env = dict(os.environ, GOPATH=os.path.join(WORK, "go"), GOBIN=os.path.join(WORK, "bin"), GOFLAGS="-mod=mod")
    subprocess.run(["go", "install", "github.com/rclone/rclone@latest"], check=True, env=env)
    return os.path.join(WORK, "bin", "rclone")


def write_rclone_conf() -> None:
    raw = os.environ.get("GDRIVE_TOKEN", "").strip()
    if not raw:
        sys.exit("GDRIVE_TOKEN is not set. Add it in the environment settings (see video-variants/README.md).")
    if not raw.startswith("{"):
        try:
            raw = base64.b64decode(raw + "===").decode()
        except Exception:
            pass
    m = re.search(r"\{.*\}", raw, re.S)
    tok = json.loads(m.group(0)) if m else {}
    if "refresh_token" not in tok and "token" in tok:  # some tools wrap it
        tok = json.loads(tok["token"]) if isinstance(tok["token"], str) else tok["token"]
    if "refresh_token" not in tok:
        sys.exit("GDRIVE_TOKEN doesn't look like an rclone Drive token (no refresh_token).")
    os.makedirs(WORK, exist_ok=True)
    lines = ["[gd]", "type = drive", "scope = drive", f"token = {json.dumps(tok)}"]
    if os.environ.get("GDRIVE_CLIENT_ID"):
        lines += [f"client_id = {os.environ['GDRIVE_CLIENT_ID']}",
                  f"client_secret = {os.environ.get('GDRIVE_CLIENT_SECRET', '')}"]
    with open(RCLONE_CONF, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(RCLONE_CONF, 0o600)


RCLONE = None


def rc(*args, capture=True, check=True) -> str:
    cmd = [RCLONE, "--config", RCLONE_CONF, "--retries", "5", "--low-level-retries", "20", *args]
    r = subprocess.run(cmd, capture_output=capture, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"rclone {' '.join(args[:2])} failed: {(r.stderr or '')[-800:]}")
    return r.stdout if capture else ""


def remote(folder_id: str, path: str = "") -> str:
    return f"gd,root_folder_id={folder_id}:{path}"


# ----------------------------------------------------------------- catalog

def slug_of(name: str) -> tuple[str, str]:
    stem = os.path.splitext(name)[0]
    m = re.match(r"^([A-Za-z]*\d+)[_\- ]+(.*)$", stem)
    code, rest = (m.group(1), m.group(2)) if m else (stem, stem)
    return code.upper(), re.sub(r"[^a-z0-9]+", "-", rest.lower()).strip("-")


def list_sources() -> list[dict]:
    out = []
    for group, where, folder, note in SOURCES:
        if os.path.isdir(where):
            files = [{"Name": n, "Size": os.path.getsize(os.path.join(where, n)), "ID": None}
                     for n in sorted(os.listdir(where)) if n.lower().endswith(".mp4")]
        else:
            files = json.loads(rc("lsjson", "--files-only", remote(where)))
            files = sorted((f for f in files if f["Name"].lower().endswith(".mp4")), key=lambda f: f["Name"])
        for f in files:
            if group == "SEED":
                slug, theme = SEED_META.get(f["Name"], (None, None))
                num = int(re.findall(r"\d+", os.path.splitext(f["Name"])[0])[-1])  # "seedance-2.5_03" -> 3
                code = f"{num:02d}"
                slug = slug or slug_of(f["Name"])[1]
                theme = theme or theme_for(f["Name"])
            else:
                code, slug = slug_of(f["Name"])
                theme = theme_for(f["Name"])
            out.append({
                "source_id": f"{group}-{code}", "group": group, "bank_folder": folder, "note": note,
                "original_name": f["Name"], "original_drive_id": f.get("ID"), "origin": where,
                "slug": slug, "theme": theme, "size": f["Size"],
            })
    return out


def load_catalog(sources: list[dict]) -> list[dict]:
    """Number each clip within its theme (drives which text and music it gets).

    Numbers are saved, so rerunning after new clips arrive never changes the
    text or music of clips that are already in BANK.
    """
    path = os.path.join(WORK, "catalog.json")
    old = {}
    if os.path.exists(path):
        old = {s["source_id"]: s for s in json.load(open(path))}
    counters: dict[str, int] = {}
    for s in old.values():
        counters[s["theme"]] = max(counters.get(s["theme"], 0), s["clip_index"] + 1)
    for s in sources:
        prev = old.get(s["source_id"])
        if prev and prev["theme"] == s["theme"]:
            s["clip_index"] = prev["clip_index"]
        else:
            s["clip_index"] = counters.get(s["theme"], 0)
            counters[s["theme"]] = s["clip_index"] + 1
    with open(path, "w") as f:
        json.dump(sources, f, indent=2)
    return sources


# ------------------------------------------------------------------ worker

def process_source(s: dict, upload: bool, keep_local: bool) -> dict:
    """Download, render 10 variants, verify, upload. Runs in a worker process."""
    from make_variants import make_variants
    from vv_detect import HeadDetector

    t0 = time.time()
    src_dir = os.path.join(WORK, "src", s["group"])
    os.makedirs(src_dir, exist_ok=True)
    src = os.path.join(src_dir, s["original_name"])
    if not os.path.exists(src):
        if os.path.isdir(s["origin"]):
            shutil.copy(os.path.join(s["origin"], s["original_name"]), src)
        else:
            rc("copyto", remote(s["origin"], s["original_name"]), src)
    folder = f"{s['source_id']}_{s['slug']}"
    out_dir = os.path.join(WORK, "bank", s["bank_folder"], folder)
    det = HeadDetector()
    lines = []
    try:
        res = make_variants(src, out_dir, s["source_id"], s["slug"], s["theme"], s["clip_index"], n=10,
                            detector=det, log=lines.append)
    finally:
        det.close()
    bad = [v["file"] for v in res["variants"] if not v["verified"] or not v["text_clear_of_faces"]]
    res.update({"group": s["group"], "theme": s["theme"], "bank_folder": s["bank_folder"], "folder": folder,
                "original_name": s["original_name"], "original_drive_id": s["original_drive_id"],
                "note": s["note"], "problems": bad})
    with open(os.path.join(out_dir, f"{folder}.json"), "w") as f:
        json.dump(res, f, indent=2)
    if upload:
        dest = remote(BANK_FOLDER_ID, f"{s['bank_folder']}/{folder}")
        rc("copy", out_dir, dest, "--include", "*.mp4", "--transfers", "4", "--drive-chunk-size", "32M")
        rc("copyto", os.path.join(out_dir, f"{folder}_preview.jpg"), remote(BANK_FOLDER_ID, f"_previews/{folder}_preview.jpg"))
        rc("copyto", os.path.join(out_dir, f"{folder}.json"), remote(BANK_FOLDER_ID, f"_data/{folder}.json"))
        listed = json.loads(rc("lsjson", "--files-only", dest))
        remote_sizes = {f["Name"]: f["Size"] for f in listed}
        missing = [v["file"] for v in res["variants"] if remote_sizes.get(v["file"]) != v["bytes"]]
        if missing:
            raise RuntimeError(f"{folder}: upload check failed for {missing}")
        if not keep_local:
            for v in res["variants"]:
                os.remove(os.path.join(out_dir, v["file"]))
        os.remove(src)
    res["log"] = lines
    res["total_s"] = round(time.time() - t0, 1)
    return res


# -------------------------------------------------------------------- main

def main():
    global RCLONE
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--keep-local", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--skip-tracker", action="store_true")
    ap.add_argument("--offline", action="store_true", help="local Seedance clips only, no Drive (for testing)")
    a = ap.parse_args()

    os.makedirs(WORK, exist_ok=True)
    free_gb = 0.0
    if a.offline:
        a.no_upload = True
        SOURCES[:] = [x for x in SOURCES if os.path.isdir(x[1])]
    else:
        RCLONE = rclone_bin()
        write_rclone_conf()
        about = json.loads(rc("about", "gd:", "--json"))
        free_gb = (about.get("free") or 0) / 1e9
        log(f"Drive connected. Free space: {free_gb:.1f} GB")

    sources = load_catalog(list_sources())
    counts = {g: sum(1 for s in sources if s["group"] == g) for g, *_ in SOURCES}
    log(f"Found {len(sources)} clips {counts} -> {len(sources) * 10} videos")
    if free_gb and free_gb < len(sources) * 10 * 0.006:
        log(f"WARNING: estimated output ~{len(sources) * 10 * 0.004:.1f} GB may not fit in {free_gb:.1f} GB free")

    state_path = os.path.join(WORK, "state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    already = sum(1 for s in sources if state.get(s["source_id"], {}).get("done"))
    todo = [s for s in sources if (not a.only or s["source_id"] in a.only)
            and not state.get(s["source_id"], {}).get("done")]
    if a.limit:
        todo = todo[:a.limit]
    log(f"{len(todo)} clips to process now ({already} already in BANK)")

    failures = []
    with cf.ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(process_source, s, not a.no_upload, a.keep_local): s for s in todo}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            s = futs[fut]
            try:
                res = fut.result()
                ok = not res["problems"]
                state[s["source_id"]] = {"done": not a.no_upload, "problems": res["problems"],
                                         "variants": len(res["variants"]), "seconds": res["total_s"]}
                log(f"[{i}/{len(todo)}] {s['source_id']} {s['slug']}: 10 variants "
                    f"{'OK' if ok else 'CHECK ' + str(res['problems'])} ({res['total_s']:.0f}s)")
            except Exception as e:  # keep going; rerun picks it up
                failures.append((s["source_id"], str(e)))
                log(f"[{i}/{len(todo)}] {s['source_id']} FAILED: {e}")
            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)

    if failures:
        log(f"{len(failures)} clips failed; rerun to retry: {[f[0] for f in failures]}")
    if not a.no_upload and not a.skip_tracker:
        from build_tracker import build_and_upload
        build_and_upload(sources, rc, remote, BANK_FOLDER_ID, WORK, log)
    done = sum(1 for v in state.values() if v.get("done"))
    log(f"Finished: {done}/{len(sources)} clips in BANK ({done * 10} videos).")


if __name__ == "__main__":
    main()
