#!/usr/bin/env python3
"""Generate riffer-evals/dora_results.html — SA3 DoRA finetune comparison page.

GPU 2-seed eval edition. Compares three DoRA finetune variants of SA3 medium-base
on the Goa corpus, rendered on GPU (eval_dora_cpu.py --device cuda) to 3 fixed
prompts x TWO seeds (1234, 42) per checkpoint, PLUS the 9 model-soups:

  * rank-16          — render subdir r16/  (lineage: vjnnndnu ep0-2 + x20b3ygb ep3-7)
  * rank-64-AdamW    — render subdir r64/  (run i8nygj4y, 8 ckpts)
  * rank-128-Fusion  — render subdir r128f/ (run mqe3ne49, 8 ckpts, FusionOpt 2x LR)
  * SOUPS            — renders_soups/ (9 soups: {r16,r64,r128f} x {expasc,expdesc,goodearly})

Each checkpoint/soup's 6 clips (3 prompts x 2 seeds) were scored together by
eval_dora_quality.py on Audiobox CE/PQ/PC/CU + MERT distance-to-Goa (frechet_mid,
cos_dist_mid [the ranker], cos_dist_upper). Pooling both seeds makes the Frechet
less degenerate and the cosine distance more robust.

The page:
  * groups clips by VARIANT (render subdir) + a SOUPS section, labelled clearly;
  * shows each variant's checkpoints/soups x (3 prompts x 2 seeds) as a same-playhead
    clickable cell grid (player copied from latch_sweep.html / onset_eval.html);
  * AAC-encodes every clip to clips_dora_aac/ (128k m4a, skip-if-present, 6 cores —
    capped so a concurrent GPU training run's dataloader isn't starved);
  * per-checkpoint/soup metrics table joined from the two quality_eval.json, sorted
    within each section by cos_dist_mid, best (low cos_dist_mid @ good CE) marked;
  * a curated top summary (light-touch finetune, early-is-best, Fusion wins the
    upper/harmony layer, soups buy robustness not a jump).

Run in the mir venv:
    /home/kim/Projects/mir/mir/bin/python /home/kim/build_dora_results_page.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

RENDER_DIR = Path("/home/kim/Projects/SAO/stable-audio-3/renders_dora2")
QUALITY = RENDER_DIR / "quality_eval.json"
SOUP_DIR = Path("/home/kim/Projects/SAO/stable-audio-3/renders_soups")
SOUP_QUALITY = SOUP_DIR / "quality_eval.json"
CROSS_DIR = Path("/home/kim/Projects/SAO/stable-audio-3/renders_cross")
CROSS_QUALITY = CROSS_DIR / "quality_eval.json"
EVALS_DIR = Path("/home/kim/riffer-evals")
HTML_OUT = EVALS_DIR / "dora_results.html"
AAC_DIR = EVALS_DIR / "clips_dora_aac"

# Cap ffmpeg parallelism: a training run shares the box — leave cores for its dataloader.
ENCODE_WORKERS = 6

# subdir -> variant label.
SUBDIR_VARIANT = {
    "r16": "rank-16",
    "r64": "rank-64-AdamW",
    "r128f": "rank-128-Fusion",
    "r128a": "rank-128-AdamW",
}
# display order of variant sections (the two rank-128 runs sit together)
VARIANT_ORDER = ["rank-16", "rank-64-AdamW", "rank-128-Fusion", "rank-128-AdamW"]
VARIANT_BLURB = {
    "rank-16": "Original DoRA recipe, LoRA rank 16 (AdamW). Lineage spans two runs: "
               "vjnnndnu (total epochs 0-2) then x20b3ygb (continued, total epochs "
               "3-7) — 8 checkpoints in subdir r16/.",
    "rank-64-AdamW": "Rank-64 DoRA, AdamW — 4x adapter capacity over rank-16, "
                     "same optimizer. 8 checkpoints (run i8nygj4y), subdir r64/.",
    "rank-128-Fusion": "Rank-128 DoRA with FusionOpt at 2x LR (components "
                       "mona / ns5 / normuon / sf; shampoo off). 8x capacity + "
                       "the Fusion optimizer. 8 checkpoints (run mqe3ne49), subdir r128f/.",
    "rank-128-AdamW": "Rank-128 DoRA with AdamW — same 8x capacity as rank-128-Fusion "
                      "but the plain optimizer (the controlled comparison: rank vs "
                      "optimizer). 8 checkpoints (run dq0egegi), subdir r128a/. "
                      "<b>Its ep0 is the best single checkpoint overall (cosD_mid 0.0242).</b>",
}

# soup base-id -> human label / source run
SOUP_BASE = {
    "r16": "rank-16",
    "r64": "rank-64-AdamW",
    "r128f": "rank-128-Fusion",
}
SOUP_STRATEGY = {
    "expasc": "exp-ascending (weights more late checkpoints)",
    "expdesc": "exp-descending (weights more early checkpoints)",
    "goodearly": "good-early (uniform over the early/best checkpoints)",
}

PROMPTS = {
    "p0": "aggressive upbeat goa trance",
    "p1": "energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine",
    "p2": "psytrance, 140 bpm",
}
PID_ORDER = ["p0", "p1", "p2"]
SEED_ORDER = [1234, 42]

# A checkpoint with CE below this is "quality-degraded" — not a valid winner even
# if its cos_dist_mid is low (could be distance-via-collapse).
CE_FLOOR = 5.0

# Curated top-summary bullets (the human reading of the four-variant comparison).
SUMMARY_CURATED = [
    "<b>Best single checkpoint = rank-128-AdamW ep0 (cosD_mid 0.0242)</b> — higher "
    "rank wins by <b>~2%</b> over rank-64 ep0 (0.0247), and the gain is at epoch 0. "
    "Finetune stays a <b>light touch</b>: every checkpoint sits at cosD_mid "
    "<b>0.024–0.036</b> from the Goa centroid — DoRA nudges the model, it does not "
    "relocate it.",
    "<b>EARLY-is-best, across all four variants</b>: the lowest distance-to-Goa is at "
    "the earliest epochs; more training <b>drifts away</b> from the Goa distribution "
    "(cosD_mid climbs monotonically with epoch on every rank/optimizer).",
    "<b>Fusion wins the upper / harmony layer, not the mid</b>: rank-128-Fusion has the "
    "lowest cos_dist_upper (<b>0.0159</b>) — closest in MERT's melody/harmony layer — "
    "but it does <i>not</i> win the mid layer (energy/timbre), where rank-128-AdamW ep0 leads.",
    "<b>Within-run soups</b>: expdesc / goodearly beat expasc (early-is-best confirmed in "
    "the weight-average too). Best within-run soup = <b>r16_goodearly 0.0252</b> ≈ best "
    "single — souping buys <b>robustness, not a jump</b>.",
    "<b>Cross-optimiser soups</b> (AdamW × Fusion blends): best <b>Fréchet 0.071</b> and "
    "good CE (<code>cross_10A90F</code> CE 6.77), but they <i>don't</i> beat the best single "
    "on cosD_mid — the blends stay <b>Fusion-dominated and didn't fully fuse</b> "
    "(cosD_mid 0.0266–0.0273).",
    "<b>The modern-psytrance drift is DATA, not capacity</b>: the corpus mixes goa/psytrance "
    "captions over ~1800 tracks (2007–2019). The real lever is a <b>cleaner 90s subset + "
    "early-stop</b>, not more rank or a fancier optimizer.",
]


# --------------------------------------------------------------------------- #
# Clip discovery — singles
# --------------------------------------------------------------------------- #
def parse_clip(wav: Path):
    """Return (variant, subdir, tag, pid, seed) for a single-render wav, or None.

    Name: <tag>__p<i>_seed<seed>.wav  where tag = <run_id>_epoch<N>-step<M>.
    Variant comes from the immediate parent subdir under renders_dora2/.
    """
    m = re.match(r"(.+)__p(\d+)_seed(\d+)\.wav$", wav.name)
    if not m:
        return None
    tag = m.group(1)
    pid = f"p{m.group(2)}"
    seed = int(m.group(3))
    try:
        rel = wav.relative_to(RENDER_DIR)
    except ValueError:
        return None
    subdir = rel.parts[0] if len(rel.parts) > 1 else ""
    variant = SUBDIR_VARIANT.get(subdir)
    if variant is None:
        return None
    return variant, subdir, tag, pid, seed


def discover():
    """variant -> {tag -> {(pid,seed) -> wav Path}}, plus tag -> subdir."""
    by_variant: dict = defaultdict(lambda: defaultdict(dict))
    tag_subdir: dict = {}
    for wav in sorted(RENDER_DIR.rglob("*.wav")):
        p = parse_clip(wav)
        if not p:
            continue
        variant, subdir, tag, pid, seed = p
        by_variant[variant][tag][(pid, seed)] = wav
        tag_subdir[tag] = subdir
    return by_variant, tag_subdir


# --------------------------------------------------------------------------- #
# Clip discovery — soups
# --------------------------------------------------------------------------- #
def parse_soup(wav: Path):
    """Return (tag, pid, seed) for a soup wav, or None.

    Name: soups_dora_<base>_<strategy>__p<i>_seed<seed>.wav
    tag  = soups_dora_<base>_<strategy>
    """
    m = re.match(r"(soups_dora_.+)__p(\d+)_seed(\d+)\.wav$", wav.name)
    if not m:
        return None
    return m.group(1), f"p{m.group(2)}", int(m.group(3))


def soup_base_strategy(tag: str):
    """tag -> (base_id, strategy_id). e.g. soups_dora_r16_goodearly -> (r16, goodearly)."""
    rest = tag[len("soups_dora_"):] if tag.startswith("soups_dora_") else tag
    base, _, strat = rest.rpartition("_")
    return base, strat


def discover_soups():
    """tag -> {(pid,seed) -> wav Path} for the soup renders."""
    by_tag: dict = defaultdict(dict)
    for wav in sorted(SOUP_DIR.rglob("*.wav")):
        p = parse_soup(wav)
        if not p:
            continue
        tag, pid, seed = p
        by_tag[tag][(pid, seed)] = wav
    return by_tag


def discover_cross():
    """tag -> {(pid,seed) -> wav Path} for the cross-optimiser soup renders.

    Name: soups_dora_cross_<NN>A<MM>F__p<i>_seed<seed>.wav  (reuses parse_soup).
    """
    by_tag: dict = defaultdict(dict)
    for wav in sorted(CROSS_DIR.rglob("*.wav")):
        p = parse_soup(wav)
        if not p:
            continue
        tag, pid, seed = p
        by_tag[tag][(pid, seed)] = wav
    return by_tag


def cross_ratio(tag: str):
    """soups_dora_cross_25A75F -> ('25% AdamW / 75% Fusion', '25A75F')."""
    m = re.search(r"cross_(\d+)A(\d+)F", tag)
    if not m:
        return tag, tag
    a, f = m.group(1), m.group(2)
    return f"{a}% AdamW / {f}% Fusion", f"{a}A{f}F"


# --------------------------------------------------------------------------- #
# AAC encode (128k, skip-if-present, capped workers)
# --------------------------------------------------------------------------- #
def _encode(args):
    stem, src, dst = args
    if Path(dst).exists():
        return stem, True, "exists"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
             "-c:a", "aac", "-b:a", "128k", dst],
            check=True,
        )
        return stem, True, "encoded"
    except Exception as exc:
        return stem, False, str(exc)


def encode_clips(clip_map):
    """AAC-encode a flat {stem -> wav Path} map into AAC_DIR.
    Returns wavpath(str) -> rel aac path."""
    AAC_DIR.mkdir(parents=True, exist_ok=True)
    jobs = []
    keyed = []  # (wav_str, stem)
    for stem, wav in clip_map.items():
        dst = str(AAC_DIR / f"{stem}.m4a")
        jobs.append((stem, str(wav), dst))
        keyed.append((str(wav), stem))
    online = {}
    nenc = nexist = nfail = 0
    with ProcessPoolExecutor(max_workers=ENCODE_WORKERS) as ex:
        results = {stem: (ok, msg) for stem, ok, msg in ex.map(_encode, jobs)}
    for wav_str, stem in keyed:
        ok, msg = results[stem]
        if ok:
            online[wav_str] = f"clips_dora_aac/{stem}.m4a"
            if msg == "exists":
                nexist += 1
            else:
                nenc += 1
        else:
            nfail += 1
            print(f"[warn] encode failed {stem}: {msg}", flush=True)
    print(f"[info] AAC: {nenc} encoded, {nexist} reused, {nfail} failed "
          f"({ENCODE_WORKERS} workers)", flush=True)
    return online


def build_clip_map(by_variant, by_soup, by_cross=None):
    """Flat {stem -> wav Path} over singles, soups and cross-soups."""
    cm = {}
    for variant, tags in by_variant.items():
        for tag, cells in tags.items():
            for (pid, seed), wav in cells.items():
                cm[f"{tag}__{pid}_seed{seed}"] = wav
    for tag, cells in by_soup.items():
        for (pid, seed), wav in cells.items():
            cm[f"{tag}__{pid}_seed{seed}"] = wav
    for tag, cells in (by_cross or {}).items():
        for (pid, seed), wav in cells.items():
            cm[f"{tag}__{pid}_seed{seed}"] = wav
    return cm


# --------------------------------------------------------------------------- #
# metrics from quality_eval.json
# --------------------------------------------------------------------------- #
def load_metrics(path):
    if not path.exists():
        print(f"[warn] {path} missing — no metrics will be shown")
        return {}, {}
    d = json.load(open(path))
    meta = d.get("meta", {})
    by_tag = {r["tag"]: r for r in d.get("checkpoints", [])}
    return by_tag, meta


def local_epoch(tag: str) -> int:
    m = re.search(r"epoch(\d+)", tag)
    return int(m.group(1)) if m else -1


def total_epoch(tag: str) -> int:
    """Total-epoch label for the r16 lineage: vjnnndnu = ep0-2, x20b3ygb continues
    at ep3-7 (= local epoch + 3). Single-run variants use their local epoch."""
    ep = local_epoch(tag)
    if ep < 0:
        return -1
    if tag.startswith("x20b3ygb"):
        return ep + 3
    return ep


def _metrics_row(tag, m, extra=None):
    row = {
        "tag": tag,
        "n_clips": m.get("n_clips"),
        "CE": m.get("CE"), "PQ": m.get("PQ"),
        "PC": m.get("PC"), "CU": m.get("CU"),
        "frechet_mid": m.get("frechet_mid"),
        "cos_dist_mid": m.get("cos_dist_mid"),
        "cos_dist_upper": m.get("cos_dist_upper"),
    }
    if extra:
        row.update(extra)
    return row


def _pick_best(rows):
    """Lowest cos_dist_mid among CE>=floor rows (else lowest overall)."""
    valid = [r for r in rows if r["cos_dist_mid"] is not None
             and (r["CE"] is None or r["CE"] >= CE_FLOOR)]
    if valid:
        return min(valid, key=lambda r: r["cos_dist_mid"])
    scored = [r for r in rows if r["cos_dist_mid"] is not None]
    return min(scored, key=lambda r: r["cos_dist_mid"]) if scored else None


def _grid_cells(cells_by_key, online):
    cells = []
    for pid in PID_ORDER:
        for seed in SEED_ORDER:
            wav = cells_by_key.get((pid, seed))
            f = online.get(str(wav)) if wav else None
            if f is None and wav and wav.exists():
                f = os.path.relpath(wav, EVALS_DIR)
            cells.append({"pid": pid, "seed": seed, "f": f})
    return cells


# --------------------------------------------------------------------------- #
# build page data
# --------------------------------------------------------------------------- #
def build_data(by_variant, tag_subdir, by_tag, meta, by_soup, soup_tags, online,
               by_cross=None, cross_tags=None):
    variants = []
    variant_best = {}  # variant -> best row (valid CE) by cos_dist_mid

    for variant in VARIANT_ORDER:
        tags = by_variant.get(variant, {})
        if not tags:
            continue
        rows = []
        for tag in tags:
            m = by_tag.get(tag, {})
            rows.append(_metrics_row(tag, m, {
                "subdir": tag_subdir.get(tag, ""),
                "epoch": total_epoch(tag),
            }))
        rows.sort(key=lambda r: (r["cos_dist_mid"] is None,
                                 r["cos_dist_mid"] if r["cos_dist_mid"] is not None else 9e9))
        best = _pick_best(rows)
        if best:
            best["is_best"] = True
            variant_best[variant] = best

        grid_tags = sorted(tags, key=lambda t: (total_epoch(t), t))
        grid = []
        for tag in grid_tags:
            m = by_tag.get(tag, {})
            grid.append({
                "tag": tag, "epoch": total_epoch(tag), "subdir": tag_subdir.get(tag, ""),
                "cos_dist_mid": m.get("cos_dist_mid"), "CE": m.get("CE"),
                "is_best": tag == (best["tag"] if best else None),
                "cells": _grid_cells(tags[tag], online),
            })

        variants.append({
            "variant": variant,
            "blurb": VARIANT_BLURB.get(variant, ""),
            "rows": rows,
            "grid": grid,
            "best_tag": best["tag"] if best else None,
        })

    # ---- soups section ----
    soup_section = None
    if by_soup:
        rows = []
        for tag in soup_tags:
            base, strat = soup_base_strategy(tag)
            m = soup_tags[tag]
            rows.append(_metrics_row(tag, m, {
                "base": SOUP_BASE.get(base, base),
                "strategy": strat,
                "strategy_full": SOUP_STRATEGY.get(strat, strat),
            }))
        rows.sort(key=lambda r: (r["cos_dist_mid"] is None,
                                 r["cos_dist_mid"] if r["cos_dist_mid"] is not None else 9e9))
        sbest = _pick_best(rows)
        if sbest:
            sbest["is_best"] = True

        grid_tags = sorted(by_soup, key=lambda t: (
            soup_tags.get(t, {}).get("cos_dist_mid") is None,
            soup_tags.get(t, {}).get("cos_dist_mid", 9e9)))
        grid = []
        for tag in grid_tags:
            m = soup_tags.get(tag, {})
            base, strat = soup_base_strategy(tag)
            grid.append({
                "tag": tag,
                "label": f"{SOUP_BASE.get(base, base)} · {strat}",
                "cos_dist_mid": m.get("cos_dist_mid"), "CE": m.get("CE"),
                "is_best": tag == (sbest["tag"] if sbest else None),
                "cells": _grid_cells(by_soup[tag], online),
            })
        soup_section = {
            "rows": rows,
            "grid": grid,
            "best_tag": sbest["tag"] if sbest else None,
        }

    # ---- cross-optimiser soups section ----
    cross_section = None
    if by_cross:
        cross_tags = cross_tags or {}
        rows = []
        for tag in cross_tags:
            full, short = cross_ratio(tag)
            rows.append(_metrics_row(tag, cross_tags[tag], {
                "ratio": short, "ratio_full": full,
            }))
        rows.sort(key=lambda r: (r["cos_dist_mid"] is None,
                                 r["cos_dist_mid"] if r["cos_dist_mid"] is not None else 9e9))
        cbest = _pick_best(rows)
        if cbest:
            cbest["is_best"] = True
        # best Frechet (a separate winner the cross blends actually take)
        frows = [r for r in rows if r["frechet_mid"] is not None]
        cbest_frechet = min(frows, key=lambda r: r["frechet_mid"])["tag"] if frows else None

        grid_tags = sorted(by_cross, key=lambda t: (
            cross_tags.get(t, {}).get("cos_dist_mid") is None,
            cross_tags.get(t, {}).get("cos_dist_mid", 9e9)))
        grid = []
        for tag in grid_tags:
            m = cross_tags.get(tag, {})
            full, short = cross_ratio(tag)
            grid.append({
                "tag": tag, "label": short,
                "cos_dist_mid": m.get("cos_dist_mid"), "CE": m.get("CE"),
                "is_best": tag == (cbest["tag"] if cbest else None),
                "cells": _grid_cells(by_cross[tag], online),
            })
        cross_section = {
            "rows": rows,
            "grid": grid,
            "best_tag": cbest["tag"] if cbest else None,
            "best_frechet_tag": cbest_frechet,
        }

    summary = build_summary(variant_best)

    # meta is embedded wholesale into the served page's data blob; scrub any local
    # absolute path before that happens (caught 2026-07-04, WINTERMUTE — goa_root
    # leaked /run/media/kim/Mantu/ai-music/Goa_Separated verbatim into `const D`).
    safe_meta = dict(meta)
    if "goa_root" in safe_meta:
        safe_meta["goa_root"] = Path(safe_meta["goa_root"]).name

    return {
        "prompts": PROMPTS,
        "pid_order": PID_ORDER,
        "seed_order": SEED_ORDER,
        "meta": safe_meta,
        "ce_floor": CE_FLOOR,
        "variants": variants,
        "soups": soup_section,
        "cross": cross_section,
        "variant_best": {k: {"tag": v["tag"], "cos_dist_mid": v["cos_dist_mid"],
                             "CE": v["CE"]} for k, v in variant_best.items()},
        "summary": summary,
    }


def build_summary(variant_best):
    """Auto best-lines + deltas, beneath the curated narrative."""
    def g(v):
        b = variant_best.get(v)
        return (b["cos_dist_mid"], b["CE"], b["tag"]) if b else (None, None, None)

    r16 = g("rank-16")
    r64 = g("rank-64-AdamW")
    r128 = g("rank-128-Fusion")
    r128a = g("rank-128-AdamW")
    lines = []
    base = r16[0]

    def delta_txt(name, val, base):
        if val is None or base is None:
            return f"{name}: n/a"
        d = val - base
        dir_ = "closer to Goa" if d < 0 else "further from Goa"
        pct = (d / base) * 100 if base else 0
        return f"{name}: cos_dist_mid {val:.4f} ({d:+.4f}, {pct:+.1f}% — {dir_})"

    lines.append(delta_txt("rank-64-AdamW", r64[0], base))
    lines.append(delta_txt("rank-128-Fusion", r128[0], base))
    lines.append(delta_txt("rank-128-AdamW", r128a[0], base))

    cands = [("rank-16", *r16), ("rank-64-AdamW", *r64),
             ("rank-128-Fusion", *r128), ("rank-128-AdamW", *r128a)]
    cands = [c for c in cands if c[1] is not None]
    overall = min(cands, key=lambda c: c[1]) if cands else None

    return {
        "curated": SUMMARY_CURATED,
        "rank16": {"cos_dist_mid": r16[0], "CE": r16[1], "tag": r16[2]},
        "rank64": {"cos_dist_mid": r64[0], "CE": r64[1], "tag": r64[2]},
        "rank128": {"cos_dist_mid": r128[0], "CE": r128[1], "tag": r128[2]},
        "rank128a": {"cos_dist_mid": r128a[0], "CE": r128a[1], "tag": r128a[2]},
        "deltas": lines,
        "overall": ({"variant": overall[0], "cos_dist_mid": overall[1],
                     "CE": overall[2], "tag": overall[3]} if overall else None),
    }


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #
HTML_TMPL = r"""<!doctype html><html><head><meta charset=utf-8>
<title>SA3 DoRA finetune — rank-16 / 64 / 128-Fusion / 128-AdamW + soups (GPU 2-seed)</title><style>
html{overflow-x:hidden}
body{font:12px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:100vw;overflow-x:hidden}
#hdr{position:sticky;top:0;z-index:9;background:#16181c}
#bar{padding:8px 12px;border-bottom:1px solid #2a2a30}
#wrap{padding:12px;max-width:1240px}
h1{font-size:17px;color:#9cf;margin:10px 0 2px}
h2{font-size:15px;color:#7ed;margin:24px 0 2px;border-top:1px solid #2a4a3a;padding-top:12px}
.note{color:#9aa;font-size:11px;margin:4px 0}
.legend{color:#8aa;font-size:11px;margin:4px 0 10px}
.tblwrap{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;font-size:11px;margin:6px 0}
td,th{border:1px solid #26262c;padding:3px 8px;text-align:center}
th{background:#1c1c22;color:#aaa}
td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:1px solid #7cf}
.play{outline:2px solid #5d5 !important}.no{color:#555;cursor:default}
.muted{color:#666}a{color:#7cf}
.best{outline:2px solid #d9a441}
.bestrow td{background:#231d10}
.blurb{color:#bcd;font-size:12px;margin:3px 0 6px;max-width:1040px;line-height:1.5}
.sum{margin:10px 0 6px;padding:12px 14px;background:#13231a;border:1px solid #2a5a3a;border-radius:6px}
.sumhd{font-size:15px;color:#9fe89f;font-weight:bold;margin:0 0 6px}
.sum b{color:#cfe}
.sum code{color:#edb;font-size:11px}
.win{color:#ffd479;font-weight:bold}
.seedhdr{font-size:9px;color:#789}
.curated li{margin:5px 0;color:#cde;font-size:12px;line-height:1.55}
.findings-box{border:1px solid #2a2a30;border-left:3px solid #5d9;background:#13181a;
padding:8px 12px;margin:8px 0 4px;font-size:12px;color:#ddd;max-width:1040px}
.findings-box .lbl{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#7ed;
display:block;margin:0 0 4px}
.status-banner{padding:8px 12px;margin:8px 0 4px;border-left:3px solid #c0392b;
background:#2a1a18;color:#f5b7b1;font-size:12px;border-radius:4px;max-width:1040px}
.status-banner a{color:#ffb3a8}
</style></head><body>
<div id=hdr><div id=bar>&#9654; <b id=np>click a cell to play</b>
 <span id=pos class=muted></span> &nbsp;&middot;&nbsp;
 <span class=muted>switching cells keeps the playhead; re-click stops &middot;
 <span style="color:#5d9">green border = online AAC</span></span></div></div>
<div id=wrap></div>
<script>const D=__DATA__;
const au=new Audio(); let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function cell(id,f,lbl){
  if(!f){return;}
  if(cur===id){au.pause();cur=null;mark();document.getElementById('np').textContent='stopped';return;}
  const pos=(cur!==null&&!au.paused)?au.currentTime:0;
  cur=id;mark();document.getElementById('np').textContent='▶ '+lbl;
  au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
  if(au.readyState>=1)go(); else au.addEventListener('loadedmetadata',go,{once:true});
}
function nf(x,nd){return (x==null)?'·':(+x).toFixed(nd==null?2:nd);}
function ceCol(m){if(m==null)return'#1a1a1f';const t=Math.max(0,Math.min(1,(m-4)/4));return`hsl(${Math.round(t*130)},45%,22%)`;}
let safe=s=>(''+s).replace(/[^A-Za-z0-9_]/g,'');
let h='';
h+=`<h1>SA3 DoRA finetune — distance-to-Goa: rank-16 / rank-64 / rank-128-Fusion / rank-128-AdamW + soups (GPU, 2 seeds)</h1>`;
h+=`<div class=status-banner><b>⚠ SUPERSEDED — early experiment, kept as a dated snapshot.</b> This was the first DoRA rank-ladder pass (Goa in-distribution corpus, audition 2026-07-07). The finer-grained follow-on work on the personal avp corpus — three separable degradation processes (spectral collapse / tempo instability / conditioning collapse), a revised two-island sweet-spot picture, and the caption-diversity fix for conditioning collapse — supersedes the read-out below. See the <a href="https://aavepyora.online/files/avp_master/">avp adapter master page</a> for the current picture; this page is not the current recommendation.</div>`;
h+=`<div class=findings-box><span class=lbl>What we learned</span>Kim's audition 2026-07-07: rank ladder INVERTS — r64 not better than r16, r128 degrades in-dataset goa into diffuse/impact-less after ~5400 steps while out-of-dataset prompts survive (big ranks likely need damping: rsLoRA-style LR/alpha scaling, grad-accum, EMA). After ~2 epochs, prompt+seeds close to the base model drift around the best solution while remote pairs keep learning to the last checkpoint. AdamW-r128 refuses the new style entirely (falls back to 'happy synth music') — same optimizer inertia seen in the FiLM-adapter era; cross-optimizer soups &asymp; fusion-only. Basic soups lose to raw checkpoints. HALL OF FAME: x20b3ygb_epoch3-step5400 — cleanest sound, no spectral diffusion (docs/checkpoint-hall-of-fame.md).</div>`;
const M=D.meta||{};
h+=`<div class=note>Rendered on GPU (fp16, CK flash-attn) to ${D.pid_order.length} prompts × ${D.seed_order.length} seeds (${D.seed_order.join(', ')}) per checkpoint = ${D.pid_order.length*D.seed_order.length} clips/ckpt. Each checkpoint's clips are pooled for scoring (less-degenerate Fréchet, more robust cosine).</div>`;
h+=`<div class=note>Metric: <b>cos_dist_mid</b> = 1 − mean cosine(MERT mid-layer ${JSON.stringify(M.mert_layers_mid||[3,4,5,6])} render embedding, Goa centroid) — lower = closer to the real Goa corpus (${M.n_ref||'?'} refs, ${M.ref_seconds||'?'}s windows). <b>cos_dist_up</b> uses the upper layer ${JSON.stringify(M.mert_layers_upper||[23])} (melody/harmony). The pooled <b>Fréchet</b> (N=${D.pid_order.length*D.seed_order.length}) is reported but cos_dist_mid is the ranker. CE floor for a valid winner: ${D.ce_floor}.</div>`;
h+=`<div class=legend>Prompts: `+D.pid_order.map(p=>`<b>${p}</b>=${D.prompts[p]}`).join(' &nbsp;·&nbsp; ')+`</div>`;

// ---- summary ----
const S=D.summary;
h+=`<div class=sum><div class=sumhd>Verdict — DoRA finetune of SA3 medium-base on Goa (2-seed robust)</div>`;
if(S.curated){h+='<ul class=curated>';S.curated.forEach(l=>{h+=`<li>${l}</li>`;});h+='</ul>';}
function bestLine(name,o){if(!o||o.cos_dist_mid==null)return `<div class=note><b>${name}</b>: not scored</div>`;
  return `<div class=note style="color:#bcd;font-size:12px"><b>${name}</b> best: cos_dist_mid <b>${(+o.cos_dist_mid).toFixed(4)}</b> @ CE ${o.CE==null?'·':(+o.CE).toFixed(2)} <span class=muted>(${o.tag})</span></div>`;}
h+=`<div style="margin:8px 0 2px;color:#cde">Best single checkpoint per variant:</div>`;
h+=bestLine('rank-16', S.rank16);
h+=bestLine('rank-64-AdamW', S.rank64);
h+=bestLine('rank-128-Fusion', S.rank128);
h+=bestLine('rank-128-AdamW', S.rank128a);
h+=`<div style="margin:8px 0 2px;color:#cde">vs rank-16 baseline:</div>`;
S.deltas.forEach(l=>{h+=`<div class=note style="color:#bcd;font-size:12px">&bull; ${l}</div>`;});
if(S.overall){h+=`<div style="margin-top:8px">Overall best single: <span class=win>${S.overall.variant}</span> — cos_dist_mid <b>${(+S.overall.cos_dist_mid).toFixed(4)}</b> @ CE ${S.overall.CE==null?'·':(+S.overall.CE).toFixed(2)} <span class=muted>(${S.overall.tag})</span></div>`;}
h+=`</div>`;

// ---- per-variant section renderer ----
function metricsTable(rows){
  let t='<table><tr><th>checkpoint</th><th>subdir</th><th>ep</th><th>n</th><th>cosD_mid&#9660;</th><th>cosD_up</th><th>frechet</th><th>CE</th><th>PQ</th><th>PC</th><th>CU</th></tr>';
  rows.forEach(r=>{
    const cls=r.is_best?' class=bestrow':'';
    const star=r.is_best?' <span class=win>★best</span>':'';
    t+=`<tr${cls}><td>${r.tag}${star}</td><td class=muted>${r.subdir||'·'}</td><td>${r.epoch==null||r.epoch<0?'·':r.epoch}</td><td class=muted>${r.n_clips==null?'·':r.n_clips}</td>`+
       `<td style="font-variant-numeric:tabular-nums"><b>${nf(r.cos_dist_mid,4)}</b></td>`+
       `<td>${nf(r.cos_dist_upper,4)}</td><td>${nf(r.frechet_mid,3)}</td>`+
       `<td style="background:${ceCol(r.CE)}">${nf(r.CE)}</td>`+
       `<td>${nf(r.PQ)}</td><td>${nf(r.PC)}</td><td>${nf(r.CU)}</td></tr>`;
  });
  return '<div class=tblwrap>'+t+'</table></div>';
}
function playGrid(grid,labelPrefix,labelFn){
  let t='<table><tr><th>checkpoint ＼ prompt·seed</th>';
  D.pid_order.forEach(p=>{D.seed_order.forEach(s=>{t+=`<th>${p}<div class=seedhdr>s${s}</div></th>`;});});
  t+='<th>cosD_mid</th><th>CE</th></tr>';
  grid.forEach(g=>{
    const lbl=labelFn?labelFn(g):g.tag;
    const blab=g.is_best?' <span class=win>★</span>':'';
    t+=`<tr${g.is_best?' class=bestrow':''}><td>${lbl}${blab}</td>`;
    g.cells.forEach(c=>{
      const id=safe(g.tag+'_'+c.pid+'_s'+c.seed);
      if(!c.f){t+=`<td class=no>·</td>`;}
      else{
        const online=c.f.indexOf('clips_dora_aac/')===0;
        const ob=online?';outline:1px solid #2a5a2a':'';
        const bb=g.is_best?';outline:2px solid #d9a441':ob;
        t+=`<td class=c id="${id}" style="background:#181a1f${bb}" onclick="cell('${id}','${c.f}','${labelPrefix} ${lbl} ${c.pid} s${c.seed}')">▶</td>`;
      }
    });
    t+=`<td style="font-variant-numeric:tabular-nums">${nf(g.cos_dist_mid,4)}</td>`+
       `<td style="background:${ceCol(g.CE)}">${nf(g.CE)}</td></tr>`;
  });
  return '<div class=tblwrap>'+t+'</table></div>';
}

// ---- per variant ----
D.variants.forEach(V=>{
  h+=`<h2>${V.variant}</h2>`;
  h+=`<div class=blurb>${V.blurb}</div>`;
  h+=metricsTable(V.rows);
  h+=`<div class=note>Click a cell to play (same playhead — switching keeps position, re-click stops). Columns = prompt × seed.</div>`;
  h+=playGrid(V.grid, V.variant, null);
});

// ---- soups ----
if(D.soups){
  h+=`<h2>Model soups — weight-averaged checkpoints (9 soups)</h2>`;
  h+=`<div class=blurb>Three base runs (rank-16 / rank-64-AdamW / rank-128-Fusion) × three averaging strategies: <b>expasc</b> (exp-ascending, weights later checkpoints more), <b>expdesc</b> (exp-descending, weights earlier checkpoints more), <b>goodearly</b> (uniform over the early/best checkpoints). Souping tests whether a weight average beats the best single late checkpoint.</div>`;
  // soup metrics table (base / strategy columns rather than subdir/epoch)
  h+='<table><tr><th>soup</th><th>base</th><th>strategy</th><th>n</th><th>cosD_mid&#9660;</th><th>cosD_up</th><th>frechet</th><th>CE</th><th>PQ</th><th>PC</th><th>CU</th></tr>';
  D.soups.rows.forEach(r=>{
    const cls=r.is_best?' class=bestrow':'';
    const star=r.is_best?' <span class=win>★best</span>':'';
    h+=`<tr${cls}><td>${r.tag}${star}</td><td class=muted>${r.base}</td><td class=muted title="${r.strategy_full||''}">${r.strategy}</td><td class=muted>${r.n_clips==null?'·':r.n_clips}</td>`+
       `<td style="font-variant-numeric:tabular-nums"><b>${nf(r.cos_dist_mid,4)}</b></td>`+
       `<td>${nf(r.cos_dist_upper,4)}</td><td>${nf(r.frechet_mid,3)}</td>`+
       `<td style="background:${ceCol(r.CE)}">${nf(r.CE)}</td>`+
       `<td>${nf(r.PQ)}</td><td>${nf(r.PC)}</td><td>${nf(r.CU)}</td></tr>`;
  });
  h+='</table>';
  h+=`<div class=note>Click a cell to play (same playhead). Columns = prompt × seed.</div>`;
  h+=playGrid(D.soups.grid, 'soup', g=>g.label||g.tag);
}

// ---- cross-optimiser soups ----
if(D.cross){
  h+=`<h2>Cross-optimiser soups — AdamW × Fusion weight blends (5 soups)</h2>`;
  h+=`<div class=blurb>Weight-averaged blends of the <b>rank-128-AdamW</b> (dq0egegi) and <b>rank-128-Fusion</b> (mqe3ne49) checkpoints at five mix ratios (<code>NNA/MMF</code> = NN% AdamW / MM% Fusion). The question: does averaging <i>across optimizers</i> fuse the AdamW mid-layer win with the Fusion harmony win? Result: the blends take the <b>best Fréchet (0.071)</b> and good CE, but stay <b>Fusion-dominated</b> on cosD_mid (0.0266–0.0273) — they don't beat the best single, i.e. they didn't fully fuse.</div>`;
  h+='<table><tr><th>cross soup</th><th>ratio</th><th>n</th><th>cosD_mid&#9660;</th><th>cosD_up</th><th>frechet</th><th>CE</th><th>PQ</th><th>PC</th><th>CU</th></tr>';
  D.cross.rows.forEach(r=>{
    const cls=r.is_best?' class=bestrow':'';
    const star=r.is_best?' <span class=win>★best</span>':'';
    const fbest=(r.tag===D.cross.best_frechet_tag)?' <span style="color:#7ec8ff">◆best Fréchet</span>':'';
    h+=`<tr${cls}><td>${r.tag}${star}${fbest}</td><td class=muted title="${r.ratio_full||''}">${r.ratio}</td><td class=muted>${r.n_clips==null?'·':r.n_clips}</td>`+
       `<td style="font-variant-numeric:tabular-nums"><b>${nf(r.cos_dist_mid,4)}</b></td>`+
       `<td>${nf(r.cos_dist_upper,4)}</td><td>${nf(r.frechet_mid,3)}</td>`+
       `<td style="background:${ceCol(r.CE)}">${nf(r.CE)}</td>`+
       `<td>${nf(r.PQ)}</td><td>${nf(r.PC)}</td><td>${nf(r.CU)}</td></tr>`;
  });
  h+='</table>';
  h+=`<div class=note>Click a cell to play (same playhead). Columns = prompt × seed.</div>`;
  h+=playGrid(D.cross.grid, 'cross', g=>g.label||g.tag);
}
document.getElementById('wrap').innerHTML=h;
</script></body></html>
"""


def main() -> int:
    by_variant, tag_subdir = discover()
    nclip = sum(len(c) for tags in by_variant.values() for c in tags.values())
    print(f"[info] discovered {nclip} single clips across {len(by_variant)} variants:")
    for v in VARIANT_ORDER:
        if v in by_variant:
            print(f"        {v}: {len(by_variant[v])} checkpoints")
    by_tag, meta = load_metrics(QUALITY)
    print(f"[info] metrics for {len(by_tag)} checkpoints from {QUALITY.name}")

    by_soup = discover_soups()
    nsoupclip = sum(len(c) for c in by_soup.values())
    print(f"[info] discovered {nsoupclip} soup clips across {len(by_soup)} soups")
    soup_tags, _smeta = load_metrics(SOUP_QUALITY)
    print(f"[info] metrics for {len(soup_tags)} soups from {SOUP_QUALITY.name}")

    by_cross = discover_cross()
    ncrossclip = sum(len(c) for c in by_cross.values())
    print(f"[info] discovered {ncrossclip} cross-soup clips across {len(by_cross)} cross-soups")
    cross_tags, _cmeta = load_metrics(CROSS_QUALITY)
    print(f"[info] metrics for {len(cross_tags)} cross-soups from {CROSS_QUALITY.name}")

    clip_map = build_clip_map(by_variant, by_soup, by_cross)
    print(f"[info] AAC-encoding {len(clip_map)} clips -> {AAC_DIR}")
    online = encode_clips(clip_map)
    print(f"[info] {len(online)} AAC clips available online")

    data = build_data(by_variant, tag_subdir, by_tag, meta, by_soup, soup_tags, online,
                      by_cross, cross_tags)
    html = HTML_TMPL.replace("__DATA__", json.dumps(data))
    HTML_OUT.write_text(html)
    print(f"[done] wrote {HTML_OUT} ({len(html)} bytes)")

    S = data["summary"]
    print("\n=== VERDICT (best single per variant) ===")
    for k in ("rank16", "rank64", "rank128", "rank128a"):
        o = S[k]
        print(f"  {k}: cos_dist_mid={o['cos_dist_mid']} CE={o['CE']} tag={o['tag']}")
    for l in S["deltas"]:
        print("  " + l)
    if S["overall"]:
        print(f"  OVERALL BEST single: {S['overall']['variant']} "
              f"cos_dist_mid={S['overall']['cos_dist_mid']:.4f} "
              f"CE={S['overall']['CE']}")
    if data["soups"]:
        print(f"  BEST within-run soup: {data['soups']['best_tag']}")
    if data["cross"]:
        print(f"  BEST cross soup (cosD_mid): {data['cross']['best_tag']}")
        print(f"  BEST cross soup (frechet): {data['cross']['best_frechet_tag']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
