#!/usr/bin/env python3
"""build_goa_archive_sidecar.py -- T1/T2/T3 caption sidecar for the goa_archive_extracted
big-set live-encode finetune (task #90, CONTINUITY delegation via DM 2026-08-03, Kim direct).

Originally scoped as a style-cluster + cluster-borrow-fill build (like build_longform_sidecars.py's
merged_clusters_k48 pattern), but Kim spotted that goa_archive_captions/ now has FULL per-track
coverage at both T2 and T3 (23231 Flamingo jsons, 23240 Granite jsons -- essentially every track in
the corpus), so the entire reason for clustering -- filling gaps via same-style borrowing -- is moot.
This is a straight 3-way join instead, no cluster/fallback logic:

  T1 = caption_tools.build_t1(genres, moods, bpm=None, year) from goa_archive_features npz
       (effnet_genre400/moodtheme mean-pooled top classes above a probability floor; bpm not
       available in this feature set -- build_t1 handles that gracefully, omits the bpm clause).
       year = best-effort regex off the Flamingo json's own 'rel' path (goa_archive has no
       structured year field; many folder/file names embed one, e.g. "...-1997-NCR").
  T2 = one random variant from each of granite/<key>.json's short_genremood / short_technical /
       short_mood lists, comma-joined SA3-prompt-style. Random (seeded by key, so builds are
       reproducible) rather than always variant[0], for corpus-wide phrasing diversity.
  T3 = json/<key>.json's captions.full, TRIMMED to the last complete sentence -- every sampled
       caption in this batch cuts off mid-sentence (fixed generation-length cap, "truncated_to_s"
       300/600s), so feeding the raw text would train the model on habitually-unfinished captions.

Keyed on the Flamingo json's own 'rel' field (relative to the LUMI-side goa_archive root), matching
the key_fn plan already settled with CONTINUITY (make_caption_sampler's default key_fn collides on
basename across albums -- pass a custom key_fn keyed on info['relpath'] at train_lora.py's call site,
matching this sidecar's keys, not editing caption_tools.py itself).

Run (mir venv, needs numpy but no torch): mir/bin/python eval/build_goa_archive_sidecar.py
    [--limit N] [--out PATH]
"""
import argparse
import glob
import json
import os
import random
import re
import sys
from pathlib import Path

import numpy as np

SAO = Path("/home/kim/Projects/SAO")
sys.path.insert(0, str(SAO / "stable-audio-3" / "scripts"))
from caption_tools import build_t1  # noqa: E402

# DEFAULTS ONLY — override with --features-dir / --captions-dir. These were hardcoded, which broke
# the moment we needed a SECOND captions set: the 2026-08-18 re-caption writes to
# goa_archive_captions_hinted (kept separate so the unhinted set survives as the control), and a
# hardcoded path cannot read it. Also on the standing no-hardcoded-drive-paths directive (Kim
# 2026-08-17) — 144 files carry `/run/media/kim/...` literals and 9 point at a drive label that no
# longer exists, so these get lifted as each file is touched.
FEATURES = Path(os.environ.get(
    "GOA_FEATURES_DIR",
    "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/goa_archive_features"))
CAPTIONS = Path(os.environ.get(
    "GOA_CAPTIONS_DIR",
    "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/goa_archive_captions"))
MODELS_ESSENTIA = Path("/home/kim/Projects/mir/models/essentia")

CLASS_JSON = {
    "effnet_genre400_ts": "genre_discogs400-discogs-effnet-1.json",
    "effnet_moodtheme_ts": "mtg_jamendo_moodtheme-discogs-effnet-1.json",
}
PROB_FLOOR = 0.15   # a class must clear this mean-pooled prob to make the T1 tag list
TOP_K = 3

YEAR_RE = re.compile(r"(?:19[6-9]\d|20[0-2]\d)")


def _load_class_names():
    out = {}
    for field, fname in CLASS_JSON.items():
        p = MODELS_ESSENTIA / fname
        if p.exists():
            out[field] = json.loads(p.read_text())["classes"]
    return out


def _clean_genre_label(name):
    # effnet_genre400 classes are Discogs "Parent---Subgenre" pairs (e.g.
    # "Electronic---Goa Trance") -- the "---" hierarchy separator has no place
    # literally in a natural-language caption; keep the subgenre, it's the
    # informative half (this whole corpus is already "Electronic").
    return name.split("---")[-1] if "---" in name else name


def _top_tags(npz, field, names, floor=PROB_FLOOR, k=TOP_K):
    key = f"f__{field}"
    if key not in npz or not npz[key].size:
        return []
    pooled = npz[key].mean(axis=0)
    order = np.argsort(pooled)[::-1][:k]
    tags = [names[i] for i in order if pooled[i] >= floor and i < len(names)]
    if field == "effnet_genre400_ts":
        tags = [_clean_genre_label(t) for t in tags]
    return tags


def _guess_year(rel):
    m = YEAR_RE.search(rel)
    return int(m.group(0)) if m else None


def _last_complete_sentence(text):
    """Trim a Flamingo caption to its last complete sentence (generation was length-capped,
    so the raw text routinely ends mid-clause -- feeding that as-is trains the model to trail
    off). Falls back to the raw text if no sentence boundary is found at all (short captions)."""
    if not text:
        return text
    ends = [m.end() for m in re.finditer(r"[.!?](?:\"|')?(?:\s|$)", text)]
    if not ends:
        return text.strip()
    return text[:ends[-1]].strip()


def _t2_from_granite(entry, rng):
    parts = []
    for field in ("short_genremood", "short_technical", "short_mood"):
        variants = entry.get(field) or []
        if variants:
            parts.append(rng.choice(variants))
    return ", ".join(parts) if parts else None


def main():
    # must precede any reference to these names in this scope (argparse defaults read them below)
    global CAPTIONS, FEATURES
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="cap tracks (smoke test)")
    ap.add_argument("--out", type=Path,
                    default=FEATURES / "goa_archive_caption_sidecar.json")
    ap.add_argument("--captions-dir", type=Path, default=CAPTIONS,
                    help="dir holding json/<key>.json (Music Flamingo, -> T3) and granite/<key>.json "
                         "(-> T2). Point this at goa_archive_captions_hinted for the 2026-08-18 "
                         "re-caption; the unhinted set is kept alongside as a control. "
                         f"(default {CAPTIONS})")
    ap.add_argument("--features-dir", type=Path, default=FEATURES,
                    help=f"dir holding npz/<key>.npz for the T1 effnet tags (default {FEATURES})")
    args = ap.parse_args()
    # rebind the module-level paths the body reads, so both the flag and the env var work
    CAPTIONS, FEATURES = args.captions_dir, args.features_dir
    print(f"[sidecar] captions <- {CAPTIONS}")
    print(f"[sidecar] features <- {FEATURES}")
    for _d, _what in ((CAPTIONS / "json", "T3 Music Flamingo"), (CAPTIONS / "granite", "T2 granite")):
        if not _d.is_dir():
            raise SystemExit(f"[sidecar] FATAL: {_what} dir missing: {_d}")
    # A stale derivative is the trap that cost us a full audit cycle on 2026-08-17: granite was
    # regenerated but the sidecar was not rebuilt, so the audit re-measured the OLD captions and
    # reported the contamination as if the fix had failed. Print how fresh the inputs are so a
    # stale source is visible here rather than three steps downstream.
    for _d, _label in ((CAPTIONS / "json", "T3"), (CAPTIONS / "granite", "T2")):
        try:
            _f = max(_d.iterdir(), key=lambda p: p.stat().st_mtime)
            import datetime as _dt
            _ts = _dt.datetime.fromtimestamp(_f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"[sidecar] {_label} newest input: {_ts}")
        except Exception:
            pass

    class_names = _load_class_names()
    print(f"[sidecar] class tables: {list(class_names.keys())}")

    t3_files = sorted(glob.glob(str(CAPTIONS / "json" / "*.json")))
    if args.limit:
        t3_files = t3_files[: args.limit]
    print(f"[sidecar] {len(t3_files)} T3 (Flamingo) files")

    table = {}
    n_t1 = n_t2 = n_t3 = n_npz_missing = 0
    for i, t3_path in enumerate(t3_files):
        key = os.path.splitext(os.path.basename(t3_path))[0]
        t3_entry = json.loads(Path(t3_path).read_text())
        rel = t3_entry.get("rel")
        if not rel:
            continue

        npz_path = FEATURES / "npz" / f"{key}.npz"
        genres, moods = [], []
        if npz_path.exists():
            npz = np.load(npz_path)
            genres = _top_tags(npz, "effnet_genre400_ts", class_names.get("effnet_genre400_ts", []))
            moods = _top_tags(npz, "effnet_moodtheme_ts", class_names.get("effnet_moodtheme_ts", []))
        else:
            n_npz_missing += 1
        year = _guess_year(rel)
        t1 = build_t1(genres, moods, None, year)
        if t1:
            n_t1 += 1

        granite_path = CAPTIONS / "granite" / f"{key}.json"
        t2 = None
        if granite_path.exists():
            rng = random.Random(key)  # deterministic per-track, varied across the corpus
            t2 = _t2_from_granite(json.loads(granite_path.read_text()), rng)
            if t2:
                n_t2 += 1

        raw_t3 = (t3_entry.get("captions") or {}).get("full")
        t3 = _last_complete_sentence(raw_t3) if raw_t3 else None
        if t3:
            n_t3 += 1

        table[rel] = {"t1": t1 or None, "t2": t2, "t3": t3}

        if (i + 1) % 2000 == 0:
            print(f"[sidecar] {i + 1}/{len(t3_files)}  t1={n_t1} t2={n_t2} t3={n_t3}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(table, indent=1))
    print(f"[sidecar] DONE: {len(table)} tracks -> {args.out}")
    print(f"[sidecar] coverage: t1={n_t1} t2={n_t2} t3={n_t3} "
          f"(npz missing for {n_npz_missing} tracks -> t1 falls back to empty)")


if __name__ == "__main__":
    main()
