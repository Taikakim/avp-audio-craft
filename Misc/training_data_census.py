#!/usr/bin/env python3
"""Training-data census — what corpora and databases exist, and how to read them.

Agents keep re-deriving this by hand (one session spent six tool calls
rediscovering which stores have latents vs targets, then missed the npz-based
target stores entirely). Run this instead:

    python3 Misc/training_data_census.py                 # markdown to stdout
    python3 Misc/training_data_census.py --out docs/data.md

The question it answers is NOT "how many files" but **what can this store
train?** A latent dir with no per-crop scalars and no timeseries companion
cannot train a control head no matter how many .npy it holds.

TWO NAMING TRAPS this tool exists to defuse:
  1. `.npy` is ALWAYS the latent; `.npz` is ALWAYS a target/companion, never a
     latent. So a store can be 100% .npz and hold no model input at all.
  2. Several TARGET stores are named `latents_*` (`latents_sa3_chroma`,
     `latents_sa3_stem_chroma`, `latents_sa3_proll`, ...). The name lies; the
     contents are classified here by actually opening one file.

Both data drives are REMOVABLE. `MISSING` means unmounted, not deleted.

Stdlib + numpy (numpy only to peek at one npz per store).
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sqlite3
import sys

MANTU = "/run/media/kim/Mantu"
LEHTO = "/run/media/kim/Lehto"
LEHTO_BACKUP = f"{LEHTO}/latents-all-backup"
KOSMOS = "/run/media/kim/Kosmos"
UUID = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d"
NVME = "/home/kim/Projects"

# Presence of ANY of these in a crop .json is what the `scalars` column reports.
TARGET_SCALARS = ("onset_density", "onset_per_beat", "spectral_flatness",
                  "bpm_essentia", "lufs", "syncopation")

def unlisted_section():
    """Stores on disk that NO curated list above names.

    Why this exists (W, 2026-09-17): every table in this file is a HAND-MAINTAINED list of
    tuples, so a store is in the census only if someone remembered to add it. That is a
    silent failure mode -- a new directory is simply invisible, and the doc looks complete
    while being wrong. Project guidance flagged exactly this ("/home/kim/Projects has a host
    of latents"), and the sweep found four the lists had missed: latents_avp_originals_morphL3
    (288 melody targets), latents_sa3_f0_sample, latents_sa3_subset300, plus the
    mir-same-chroma CHECKOUT, which is correctly not a store -- and the point is that the
    census now SAYS so rather than staying quiet.

    This does not replace the curated tables: those carry the provenance and the caveats that
    make a store usable, which no scan can infer. It is the completeness check on them.
    """
    listed = PRIMARY + DERIVED + LEGACY + TS_STORES
    known = {os.path.realpath(p) for _, p, _ in listed}
    # basename -> the path this document currently tells you to use
    by_name = {os.path.basename(p.rstrip("/")): p for _, p, _ in listed}
    rows, dupes, roots = [], [], [NVME, LEHTO, KOSMOS, MANTU, UUID]
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            entries = sorted(os.listdir(root))
        except OSError:
            continue
        for name in entries:
            d = os.path.join(root, name)
            if not os.path.isdir(d) or os.path.realpath(d) in known:
                continue
            try:
                kids = os.listdir(d)
            except OSError:
                continue
            npy = sum(1 for f in kids if f.endswith(".npy"))
            npz = sum(1 for f in kids if f.endswith(".npz"))
            if npy + npz < 8:            # not a store; a checkout or scratch dir
                continue
            if name in by_name:
                dupes.append((name, d, npy, npz, by_name[name]))
            else:
                rows.append((name, d, npy, npz))
    out = []
    if dupes:
        # A SECOND COPY is not a missing store -- it is a WRONG PATH in this document, and a
        # more dangerous defect. MASTER §5: pointing a dataloader at the removable Lehto copy
        # instead of the NVMe mirror is what made SA3 training crawl/hang at step 0 (cold
        # random reads at ~2 MB/s). If this document names the slow copy, it hands every
        # reader that bug.
        out += ["\n## Duplicate copies — this document may name the WRONG one\n",
                "Same store basename found at a path the tables do not use. **Prefer the "
                "local NVMe copy for any dataloader** (MASTER §5: cold random reads off the "
                "removable drive crawl and were a real cause of step-0 hangs). Removable "
                "drives also unmount; a `Projects/` path does not.\n",
                "| store | .npy | .npz | also on disk at | census currently says |",
                "|---|---:|---:|---|---|"]
        for name, d, npy, npz, canon in dupes:
            out.append(f"| `{name}` | {npy} | {npz} | `{d}` | `{canon}` |")
    if rows:
        out += ["\n## Unlisted stores (found by sweep, NOT in any curated table above)\n",
                "Directories under the four data roots holding >= 8 `.npy`/`.npz` files that no "
                "table above names. **A row here is a gap in this document, not a verdict on "
                "the data** — it has no provenance because nobody wrote one. Add it to "
                "`PRIMARY`/`DERIVED`/`LEGACY` with a real description, or confirm it is "
                "scratch.\n",
                "| store | .npy | .npz | path |", "|---|---:|---:|---|"]
        for name, d, npy, npz in rows:
            out.append(f"| `{name}` | {npy} | {npz} | `{d}` |")
    if not out:
        out = ["\n## Unlisted stores\n", "None — every store on disk is named above.\n"]
    return out


PRIMARY = [
    ("latents_sa3", f"{NVME}/latents_sa3",
     "**GOA** (Goa_Separated). The canonical SA3 set; the 2026-06 onset head trained here."),
    ("latents_goa_bigset", f"{KOSMOS}/latents_goa_bigset",
     "**goa_archive** crops. Latents only — crop .json carries NO control scalars."),
    ("latents_goa_aug8", f"{KOSMOS}/latents_goa_aug8",
     "8x pitch/stretch augmentation of goa. Augment metadata only, no control scalars."),
    ("suomisoundi_latents", f"{KOSMOS}/suomisoundi_latents",
     "**Suomisoundi**. No crop scalars; per-frame targets must come from the whole-track store."),
    ("latents_avp", f"{KOSMOS}/latents_avp",
     "**avp** own-music, augmented. Full scalars + per-crop timeseries. (Copy on Lehto backup.) "
     "⚠️ the per-crop `prompt` field is ARTIST NAME ONLY (3 distinct values over all "
     "2393 items: 'aavepyora'/'aavepyorä'/'') -- NOT a usable caption. Real tiered captions "
     "(t1/t2/t3) are `lumi/avp_captions_tiered.json`, keyed by item stem, all 2393 match "
     "(CONTINUITY, 2026-09-23)."),
    ("latents_avp_aug10", f"{LEHTO_BACKUP}/latents_avp_aug10", "avp 10x augmentation."),
    ("latents_avp_originals", f"{LEHTO_BACKUP}/latents_avp_originals", "avp unaugmented."),
    ("latents_avp_aavepyora", f"{LEHTO_BACKUP}/latents_avp_aavepyora", "aavepyora subset."),
    ("latents_avp_summamutikka", f"{LEHTO_BACKUP}/latents_avp_summamutikka",
     "summamutikka subset."),
    ("latents_chill", f"{LEHTO_BACKUP}/latents_chill",
     "**ai-music curated**: Chill Dataset."),
    ("latents_organic_dance", f"{LEHTO_BACKUP}/latents_organic_dance",
     "**ai-music curated**: organic dance."),
    ("latents_prog_psytechno", f"{LEHTO_BACKUP}/latents_prog_psytechno",
     "**ai-music curated**: Prog & Psytechno."),
    ("latents_prog_trance_melodic_techno", f"{LEHTO_BACKUP}/latents_prog_trance_melodic_techno",
     "**ai-music curated**: Progressive Trance & Melodic Techno."),
    ("sa3-latch-latents", f"{LEHTO}/sa3-latch-latents", "LatCH-specific encode."),
    ("latents_sa3_lora300", f"{LEHTO}/latents_sa3_lora300", "300-track LoRA subset."),
]

DERIVED = [
    ("latents_sa3_chroma", f"{LEHTO_BACKUP}/latents_sa3_chroma", "SAME chroma targets — NOT latents."),
    ("latents_sa3_stem_chroma", f"{KOSMOS}/latents_sa3_stem_chroma", "per-stem chroma targets — NOT latents."),
    ("latents_sa3_ctrl", f"{LEHTO_BACKUP}/latents_sa3_ctrl", "control-arm latents."),
    ("latents_avp_ctrl", f"{LEHTO_BACKUP}/latents_avp_ctrl", "avp control-arm latents."),
    ("latents_sa3_metrical", f"{KOSMOS}/latents_sa3_metrical", "metrical probe set."),
    ("latents_sa3_metrical_shuffled", f"{LEHTO_BACKUP}/latents_sa3_metrical_shuffled", "metrical NULL control."),
    ("latents_sa3_proll", f"{LEHTO_BACKUP}/latents_sa3_proll", "pianoroll targets."),
    ("latents_sa3_melody", f"{KOSMOS}/latents_sa3_melody", "melody probe set."),
    ("latents_sa3_notegrid88", f"{LEHTO_BACKUP}/latents_sa3_notegrid88", "88-key notegrid targets."),
    ("latents_sa3_morphL2", f"{LEHTO_BACKUP}/latents_sa3_morphL2", "morph variant."),
    ("latents_sa3_morphL3", f"{LEHTO_BACKUP}/latents_sa3_morphL3", "morph variant."),
    ("latents_sa3_morphL4", f"{LEHTO_BACKUP}/latents_sa3_morphL4", "morph variant."),
    ("latents_sa3_morphIOI3", f"{LEHTO_BACKUP}/latents_sa3_morphIOI3", "morph variant."),
]

LEGACY = [
    # Both retired for real (not just unmounted) as of 2026-09-22/23 -- SAO-Small's
    # old 64-dim VAE latents (`latents`, `latents_stems`), confirmed unusable for SA3
    # back in ghost-note.tasks.md 2026-05-26 ("no shortcut around a re-encode").
]

TS_STORES = [
    ("Kosmos/timeseries", f"{KOSMOS}/timeseries",
     "goa (4461) + the 4 ai-music curated sets (574). Base 100Hz + expanded at native rates."),
    ("suomisoundi_timeseries", f"{LEHTO}/suomisoundi_data/suomisoundi_timeseries",
     "Suomisoundi whole-track, 50 fields."),
    ("goa_archive_features/npz", f"{UUID}/goa_archive_features/npz",
     "goa_archive, **FULL TRACK** (dur_analyzed_s p50 362 s, max 4440). **`f__`/`r__` key "
     "prefixes.** Carries the 24 EXPANDED fields ONLY — the base 20 were never run here."),
    ("suomisoundi_features/npz", f"{LEHTO}/suomisoundi_data/suomisoundi_features/npz",
     "Suomisoundi, same `f__`/`r__` layout as goa_archive."),
]

DATABASES = [
    ("mir per-crop TimeseriesDB", f"{NVME}/mir/data/timeseries.db",
     "Per-crop timeseries for the **legacy** SAO-Small grid (21.53 Hz, T=256). "
     "`gzip(msgpack)` blobs keyed by crop stem. Used by the legacy LatCH dataset."),
    ("eval clip metrics", f"{NVME}/SAO/eval/clip_metrics.db",
     "Every rendered eval clip's measured DSP + Audiobox metrics. The disintegration "
     "gate, the boards, and `score_and_publish.py` all read this."),
]


def npy_shape(path: str) -> str:
    """Read a .npy header only — never load a 14 GB store into RAM."""
    try:
        with open(path, "rb") as fh:
            if fh.read(6) != b"\x93NUMPY":
                return "?"
            major = fh.read(1)[0]
            fh.read(1)
            hlen = int.from_bytes(fh.read(2 if major == 1 else 4), "little")
            hdr = ast.literal_eval(fh.read(hlen).decode("latin1").strip())
        return f"{tuple(hdr['shape'])} {hdr['descr'].lstrip('<|')}"
    except Exception:
        return "?"


def classify_npz(path: str) -> str:
    """Open ONE npz and say what kind of thing this store holds."""
    try:
        import numpy as np
        with np.load(path, allow_pickle=False) as z:
            keys = [k for k in z.files if k != "__meta__"]
            if any(k.startswith("f__") for k in keys):
                return "whole-track features (f__/r__)"
            if any(k.endswith("_ts") for k in keys):
                return f"per-crop timeseries ({len(keys)} fields)"
            shapes = {k: z[k].shape for k in keys[:3]}
            vals = list(shapes.values())
            if any(len(s) == 3 and s[1] in (12, 128) for s in vals):
                return f"chroma targets {vals[0]}"
            if len(keys) == 1 and len(vals[0]) == 2:
                return f"LATENTS as npz {vals[0]}"
            return "other: " + ", ".join(f"{k}{v}" for k, v in shapes.items())
    except Exception as e:
        return f"unreadable ({type(e).__name__})"


def scan(path: str) -> dict:
    r = {"present": os.path.isdir(path), "npy": 0, "json": 0, "ts": 0, "npz": 0,
         "shape": "", "scalars": [], "npz_kind": ""}
    if not r["present"]:
        return r
    f_npy = f_npz = f_json = None
    try:
        with os.scandir(path) as it:
            for e in it:
                n = e.name
                if n.endswith(".TIMESERIES.npz"):
                    r["ts"] += 1
                    f_npz = f_npz or e.path
                elif n.endswith(".npz"):
                    r["npz"] += 1
                    f_npz = f_npz or e.path
                elif n.endswith(".npy"):
                    r["npy"] += 1
                    f_npy = f_npy or e.path
                elif n.endswith(".json"):
                    r["json"] += 1
                    f_json = f_json or e.path
    except OSError:
        pass
    if f_npy:
        r["shape"] = npy_shape(f_npy)
    if f_npz:
        r["npz_kind"] = classify_npz(f_npz)
    if f_json:
        try:
            with open(f_json) as fh:
                d = json.load(fh)
            r["scalars"] = [k for k in TARGET_SCALARS if k in d]
        except Exception:
            pass
    return r


def trains(r: dict) -> str:
    if not r["present"]:
        return "—"
    if not r["npy"]:
        return "**targets only** (no model input)"
    out = ["base/LoRA"]
    if r["scalars"]:
        out.append("scalar control")
    if r["ts"]:
        out.append("LatCH")
    return ", ".join(out)


def table(rows, title, note=""):
    out = [f"\n## {title}\n"]
    if note:
        out.append(note + "\n")
    out.append("| store | .npy | .npz | crop scalars | latent shape | can train | notes |")
    out.append("|---|---:|---|---|---|---|---|")
    for label, path, desc in rows:
        r = scan(path)
        if not r["present"]:
            out.append(f"| `{label}` | MISSING | | | | — | {desc} |")
            continue
        npz = f"{r['npz'] + r['ts']:,}" + (f" — {r['npz_kind']}" if r["npz_kind"] else "")
        sc = (", ".join(r["scalars"][:2]) + ("…" if len(r["scalars"]) > 2 else "")
              if r["scalars"] else "**none**")
        out.append(f"| `{label}` | {r['npy']:,} | {npz} | {sc} | {r['shape']} | "
                   f"{trains(r)} | {desc} |")
    return out


def human(n: int) -> str:
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}G"


def db_section():
    out = ["\n## Databases\n"]
    out.append("| database | size | tables | what |")
    out.append("|---|---|---|---|")
    for label, path, note in DATABASES:
        if not os.path.exists(path):
            out.append(f"| `{label}` | MISSING | | {note} |")
            continue
        size = human(os.path.getsize(path))
        parts = []
        try:
            c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            for (t,) in c.execute("select name from sqlite_master where type='table'"):
                try:
                    n = c.execute(f'select count(*) from "{t}"').fetchone()[0]
                    parts.append(f"`{t}` {n:,} rows")
                except sqlite3.Error:
                    parts.append(f"`{t}` ?")
            c.close()
        except sqlite3.Error as e:
            parts.append(f"unreadable ({e})")
        out.append(f"| `{label}` | {size} | {'; '.join(parts)} | {note} |")
    for label, path, _ in DATABASES:
        out.append(f"\n- `{label}` → `{path}`{'' if os.path.exists(path) else '  (MISSING)'}")
    return out


ACCESS = '''
## How to read each store

### Per-crop TimeseriesDB (legacy SAO-Small grid)

```python
import sys; sys.path.insert(0, "/home/kim/Projects/mir/src")
from core.timeseries_db import TimeseriesDB

db = TimeseriesDB.open()                  # data/timeseries.db
arrays = db.get("Artist - Title_0")       # {field: np.ndarray} or None
db.has("Artist - Title_0"); db.count()
```

Run it with **`mir/bin/python`** (numpy 1.26 + essentia); `.venv` silently degrades madmom.

### Whole-track timeseries → a crop window (THE CORRECT CONSUMER)

Each field has its **own** rate (0.2–100 Hz). Use mir's consumer, which derives the rate
from `n_frames / duration`, masked-mean-pools the sentinel fields (`f0_*_ts`, where `0.0`
means unvoiced), and mode-pools the categorical ones (`chords_idx_ts`):

```python
import sys; sys.path.insert(0, "/home/kim/Projects/mir/src/tools")
from crop_timeseries_resample import build_crop_timeseries

out = build_crop_timeseries(arrays, meta, start_sec, end_sec, n_frames)
```

⚠️ **`stable-audio-tools/scripts/whole_track_target_source.py` applies the single
top-level `frame_rate` (100 Hz) to EVERY field.** That is right for the 20 base fields and
wrong for the 26 expanded ones — a ~1 Hz field gets sliced at a 100× offset, so `get()`
returns `None` and the crop is **silently dropped** rather than erroring. It is still fine
for base-field LatCH dataloading.

### The `f__`/`r__` stores (goa_archive, suomisoundi features)

Different layout from the `.TIMESERIES.npz` stores — arrays under `f__<field>`, their rates
under `r__<field>`, metadata under `meta` (not `__meta__`):

```python
import numpy as np
with np.load(path, allow_pickle=False) as z:
    genre = z["f__effnet_genre400_ts"]        # (T, 400)
    rate  = float(z["r__effnet_genre400_ts"]) # Hz
```

A plain `"effnet_genre400_ts" in z.files` check returns **False** here — that prefix has
already cost one session a wrong "the field is absent" conclusion.

### Eval clip metrics

```python
import sqlite3
c = sqlite3.connect("file:/home/kim/Projects/SAO/eval/clip_metrics.db?mode=ro", uri=True)
c.execute("select path, rms, crest, flatness, ce, pq from metrics limit 5").fetchall()
```
'''

ITEM_NOTE = '''
## What a stored item actually is (read before quoting any count)

**Every `.npy` is `(256, 4096)` = 380.44 s at 10.7666 Hz** — one fixed ~6.3-minute window.
Not a short excerpt, and not "the whole track":

- A source track **longer** than 380.44 s produces SEVERAL items (`crop_idx` 0, 1, 2 …).
  Goa sources run 382–1320 s (median 473), so ~2 items per track is typical — 5,401 items
  over 4,461 tracks.
- A source track **shorter** than 380.44 s is zero-padded, and `padding_mask` says how much
  is real (50 of 200 sampled `latents_goa_bigset` items carry padding; some are 20% pad).
  The avp encode instead DROPPED sub-380 s tracks rather than padding them.

**"crop" is overloaded in this codebase, which is the thing to watch:**

| the word | means | where |
|---|---|---|
| a crop / `crop_idx` / "per-crop .json" | one STORED 380 s item | the tables here, the sidecars |
| `--crop-frames` (default **1024** = 95.1 s) | the TRAINING WINDOW sliced out of that 4096-frame item, first-N or random beat-aligned (`--random-crop`) | `control/sa3_control/train.py` |

So a log line like `[data] 805 crops, 400 tracks; crop 1024f (95.1s)` means 805 stored items,
each of which the trainer reads a 1024-frame window from. **The tables below count stored
items**, not training windows and not tracks.

**Two `.json` conventions — `seconds_total` does not mean the same thing in both:**

- `latents_sa3` / avp / ai-music: `seconds_total` = the ITEM's own length (380.436), with
  `source_total_samples` carrying the track length, plus the full control scalars.
- `latents_goa_bigset`: `seconds_total` = the SOURCE TRACK duration (152–702 s), and there
  are no control scalars at all.
'''


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="write markdown here instead of stdout")
    args = ap.parse_args()

    out = ["# Data — corpora, targets, and databases\n",
           "**Generated by `Misc/training_data_census.py` — re-run it rather than trusting "
           "these numbers.** Counts drift; the structure does not.\n",
           "Two naming traps this exists to defuse:\n",
           "1. **`.npy` is always the latent; `.npz` is always a target or companion, never a "
           "model input.** A store can be 100% `.npz` and train nothing on its own.",
           "2. **Several TARGET stores are named `latents_*`** — `latents_sa3_chroma`, "
           "`latents_sa3_stem_chroma`, `latents_sa3_proll`. The name lies; the `.npz` column "
           "says what is actually inside.\n",
           "All three data drives are removable — `MISSING` means unmounted, not deleted.\n"]

    out.append(ITEM_NOTE)

    out += table(PRIMARY, "Primary SA3 corpora (256-dim, 10.767 Hz, T=4096)")
    out += table(DERIVED, "Derived / experiment-specific",
                 "Mostly targets and probe sets. Read the `.npz` column before assuming "
                 "these are latents.")
    out += table(LEGACY, "LEGACY SAO-Small / SA1 grid",
                 "**64-dim @ 21.53 Hz — a different latent grid. Never mix into an SA3 run.**")

    out += unlisted_section()

    out.append("\n## Whole-track timeseries (per track, sliced at consumer time)\n")
    out.append("| store | files | notes |")
    out.append("|---|---:|---|")
    for label, path, note in TS_STORES:
        if not os.path.isdir(path):
            out.append(f"| `{label}` | MISSING | {note} |")
            continue
        n = sum(1 for e in os.scandir(path) if e.name.endswith(".npz"))
        out.append(f"| `{label}` | {n:,} | {note} |")

    out += db_section()
    out.append(ACCESS)

    out.append("## Reading the tables\n")
    out.append("- **crop scalars** = the crop `.json` carries control targets "
               f"(checked: {', '.join(TARGET_SCALARS)}). Needed for FiLM / scalar control adapters.")
    out.append("- **can train** — `base/LoRA` needs no targets; `scalar control` needs the crop "
               "scalars; `LatCH` needs per-frame targets (per-crop `.TIMESERIES.npz`, or sliced "
               "from a whole-track store).")
    out.append("- A store with latents but **no** scalars/ts can still join a base or LoRA run, "
               "and can be *upgraded* by generating targets for it.")
    out.append("- **`goa_archive` features are FULL-TRACK** (`dur_analyzed_s` p50 362 s, max 4440) — "
               "the extractor's `--seconds` arg is vestigial and never reaches `ExpandedExtractor`. "
               "The real limit is WHICH fields: it holds the **24 expanded fields only** "
               "(novelty_curve, loudness_ebu, chroma_linmap, dissonance, genre/mood/instrument, "
               "MAEST, attack, stereo). The **base 20 are absent** — no `onset_envelope_ts`, no "
               "`rms_energy_*_ts`, no `beat_activation_ts`/`downbeat_activation_ts`, no `hpcp_ts`, "
               "no `spectral_flatness_ts`/`spectral_flux_ts`. So goa_archive can target a chroma, "
               "novelty, loudness or genre head today, but an **onset- or rms-density head needs "
               "`mir/src/spectral/whole_track_timeseries.py` run over the archive first** "
               "(CPU-only: the expanded pass took 66.3 h at 3 workers for 23,228 tracks and never "
               "touched the GPU).")
    out.append("\n## Paths\n")
    for label, path, _ in PRIMARY + DERIVED + LEGACY:
        out.append(f"- `{label}` → `{path}`{'' if os.path.isdir(path) else '  (MISSING)'}")
    for label, path, _ in TS_STORES:
        out.append(f"- `{label}` → `{path}`{'' if os.path.isdir(path) else '  (MISSING)'}")

    text = "\n".join(out) + "\n"
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
        print(f"wrote {args.out} ({len(text.splitlines())} lines)")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
