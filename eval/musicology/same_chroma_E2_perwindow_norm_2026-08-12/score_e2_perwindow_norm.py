#!/usr/bin/env python3
"""score_e2_perwindow_norm.py -- E2 from the morphological-space design note
(`papers/deep-research/MORPHOLOGICAL_SPACE_DESIGN_NOTE.md` S0/S4.1/S7-E2).

Question: does replacing CORPUS-DEMEANING (subtract one global corpus-mean 12-d
profile per band, estimated from the time-averaged per-track vectors) with
PER-WINDOW normalization improve the melody/chroma readout metric, especially
on bass? The note predicts bass improves most because bass carries the largest
genre-generic magnitude offset (S4.1).

Three variants scored on the SAME primary (audio-GT) pairs Tier-2 used:
  1. corpus-demean   -- baseline, must reproduce Tier-2/Version-A exactly
                        (bass ~0.214 / mid ~0.536 / air ~0.918 median demeaned cos12).
  2. per-window z-norm -- per FRAME, per band: normalize the 12-d profile by its
                        OWN mean/norm (affine, per-frame) before cosine. The
                        note's literal E2 ask.
  3. per-window rank-norm -- per FRAME, per band: convert the 12-d profile to
                        ranks (ordinal, ties averaged via scipy.stats.rankdata)
                        before cosine. Monotone-invariant, not just affine-
                        invariant -- the S4.1 correction's "real" stronger op.

Each variant gets matched (real track-vs-its-own-GT) AND null (K=5 fixed
derangements, mismatched pred[i] vs gt[perm[i]]) scores, so the reported
number is matched-vs-null gap, not a raw cosine that can be inflated by
genre-homogeneous chroma shape (the "chroma trap", see Tier-2's docstring).

REUSE (verbatim, per CLAUDE.md discovery-first rule -- do not re-derive):
  - compute_same_chroma / fold_to_12          <- mir-same-chroma (harmonic.same_chroma)
  - cos12_timeavg / cos12_vec / BAND_NAMES / FPS  <- Tier-1 score_and_report.py
  - align / gt_chroma_from_source / load_stats / fixed_derangement / quantiles
    <- Tier-2 score_and_report.py
  - the exact primary (audio-GT) track-id sample (n=1200) and cached head
    predictions (/tmp/.../scratchpad/tier2_predicted/*.npy) <- Tier-2, so this
    is directly comparable to the note's S0 numbers, not a fresh sample.

Venv: mir (scipy for rankdata; librosa/soundfile already used upstream).
Run:
  /home/kim/Projects/mir/mir/bin/python score_e2_perwindow_norm.py [--n-null 5]
"""
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from harmonic.same_chroma import compute_same_chroma, fold_to_12  # noqa: E402

# Both Tier-1 and Tier-2 modules are named `score_and_report.py` -- load them
# under distinct module names so the second import doesn't hit sys.modules
# cache and silently return the wrong (Tier-1) module.
import importlib.util


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


TIER1_DIR = Path("/home/kim/Projects/SAO/eval/musicology/same_chroma_readout_2026-08-11")
sys.path.insert(0, str(TIER1_DIR))  # tier1's score_and_report imports mido etc. relative to cwd-free paths
tier1_mod = _load_module("tier1_score_and_report", TIER1_DIR / "score_and_report.py")
cos12_timeavg, cos12_vec, BAND_NAMES, FPS = (
    tier1_mod.cos12_timeavg, tier1_mod.cos12_vec, tier1_mod.BAND_NAMES, tier1_mod.FPS,
)

TIER2_DIR = Path("/home/kim/Projects/SAO/eval/musicology/same_chroma_readout_tier2_muscriptor_2026-08-11")
sys.path.insert(0, str(TIER2_DIR))
tier2_mod = _load_module("tier2_score_and_report", TIER2_DIR / "score_and_report.py")
align, gt_chroma_from_source, load_stats, fixed_derangement, quantiles = (
    tier2_mod.align, tier2_mod.gt_chroma_from_source, tier2_mod.load_stats,
    tier2_mod.fixed_derangement, tier2_mod.quantiles,
)

HERE = Path(__file__).parent
PRED_DIR = Path("/tmp/claude-1000/-home-kim-Projects-SAO/49cd5391-27e7-4545-8295-a1053db2a077/scratchpad/tier2_predicted")
TIER2_RESULTS = TIER2_DIR / "results.json"
# Cache of the expensive pass1 (audio-GT load + fold_to_12) so re-runs adding a new
# scoring variant don't re-pay the ~15min audio-loading cost.
FOLD12_CACHE = Path("/tmp/claude-1000/-home-kim-Projects-SAO/49cd5391-27e7-4545-8295-a1053db2a077/scratchpad/e2_fold12_cache")

EPS = 1e-9


def perwindow_znorm(v):
    """v: (12,) or (...,12,T) with band axis at -2. Normalize each 12-d frame by
    its OWN mean and norm (affine, per-frame). Operates on axis=-2 (the 12 dim)."""
    m = v.mean(axis=-2, keepdims=True)
    d = v - m
    n = np.linalg.norm(d, axis=-2, keepdims=True) + EPS
    return d / n


def perwindow_ranknorm(v12t):
    """v12t: (12,T). Rank each frame's 12-d profile (ties averaged), per-frame,
    along axis 0. Returns (12,T) of ranks in [1,12] (or [0,11] after centering
    doesn't matter for cosine -- rankdata gives 1..12)."""
    T = v12t.shape[-1]
    out = np.empty_like(v12t, dtype=np.float64)
    for t in range(T):
        out[:, t] = rankdata(v12t[:, t])
    return out


def cos12_perframe_generic(a12, b12):
    """a12/b12: (3,12,T) already-normalized-per-frame vectors -> (3,) mean-over-
    frames cosine per band. Same formula as cos12_perframe_mean but local so we
    don't need a second import."""
    num = (a12 * b12).sum(1)
    den = np.linalg.norm(a12, axis=1) * np.linalg.norm(b12, axis=1) + EPS
    c = num / den
    return np.nanmean(c, axis=-1)


def score_variant(name, transform, pred12_list, gt12_list, ids, n_null, rng_seed=12345):
    """transform: fn(x12t (3,12,T)) -> transformed (3,12,T), applied independently
    to pred and gt before cosine. For corpus-demean, transform is None and the
    special-cased block below (matching Tier-2 verbatim) is used instead."""
    n = len(ids)
    rows = []
    for i in range(n):
        p = transform(pred12_list[i]) if transform else pred12_list[i]
        g = transform(gt12_list[i]) if transform else gt12_list[i]
        c = cos12_perframe_generic(p, g)
        rows.append({"id": ids[i], **{f"{b}": float(c[bi]) for bi, b in enumerate(BAND_NAMES)}})

    null_rows = []
    if n >= 3:
        rngN = random.Random(rng_seed)
        perms = fixed_derangement(n, n_null, rngN)
        for perm in perms:
            for i in range(n):
                j = perm[i]
                p = transform(pred12_list[i]) if transform else pred12_list[i]
                g = transform(gt12_list[j]) if transform else gt12_list[j]
                c = cos12_perframe_generic(p, g)
                null_rows.append({f"{b}": float(c[bi]) for bi, b in enumerate(BAND_NAMES)})
    return rows, null_rows


def score_corpus_demean(pred12_list, gt12_list, ids, n_null, rng_seed=12345):
    """Verbatim reproduction of Tier-2's corpus-demean block (score_and_report.py
    score_flavor): time-average each track first, subtract the CORPUS mean of
    those time-averages, then cosine. Sanity-check baseline before trusting the
    per-window variants."""
    n = len(ids)
    pred_ta_stack = np.stack([p.mean(-1) for p in pred12_list], 0)  # (n,3,12)
    gt_ta_stack = np.stack([g.mean(-1) for g in gt12_list], 0)
    pred_bar = pred_ta_stack.mean(0)
    gt_bar = gt_ta_stack.mean(0)
    rows = []
    for i in range(n):
        dp = pred_ta_stack[i] - pred_bar
        dg = gt_ta_stack[i] - gt_bar
        c = cos12_vec(dp, dg)
        rows.append({"id": ids[i], **{f"{b}": float(c[bi]) for bi, b in enumerate(BAND_NAMES)}})

    null_rows = []
    if n >= 3:
        rngN = random.Random(rng_seed)
        perms = fixed_derangement(n, n_null, rngN)
        for perm in perms:
            for i in range(n):
                j = perm[i]
                dp = pred_ta_stack[i] - pred_bar
                dg = gt_ta_stack[j] - gt_bar
                c = cos12_vec(dp, dg)
                null_rows.append({f"{b}": float(c[bi]) for bi, b in enumerate(BAND_NAMES)})
    return rows, null_rows


def summarize(rows, keys):
    out = {}
    for key in keys:
        vals = [r[key] for r in rows if r.get(key) is not None]
        out[key] = quantiles(vals)
    out["n"] = len(rows)
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-null", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0, help="debug: cap n ids (0 = all)")
    args = ap.parse_args()

    if not TIER2_RESULTS.exists():
        print(f"[E2] STOP: Tier-2 results.json missing at {TIER2_RESULTS}", flush=True)
        sys.exit(1)
    tier2 = json.loads(TIER2_RESULTS.read_text())
    ids = [r["id"] for r in tier2["primary_audio_gt"]["rows"]]
    if args.limit:
        ids = ids[: args.limit]
    print(f"[E2] reusing Tier-2's primary (audio-GT) sample: n={len(ids)}", flush=True)

    missing_pred = [fid for fid in ids if not (PRED_DIR / f"{fid}.npy").exists()]
    if missing_pred:
        print(f"[E2] STOP: {len(missing_pred)} cached predictions missing "
              f"(first: {missing_pred[:5]}) -- refusing to re-infer on GPU per guardrails.", flush=True)
        sys.exit(1)

    t0 = time.time()
    FOLD12_CACHE.mkdir(parents=True, exist_ok=True)
    kept_ids, pred12_list, gt12_list = [], [], []
    dropped = []
    n_cache_hit = 0
    for i, fid in enumerate(ids):
        cache_f = FOLD12_CACHE / f"{fid}.npz"
        if cache_f.exists():
            d = np.load(cache_f)
            kept_ids.append(fid)
            pred12_list.append(d["pred12"])
            gt12_list.append(d["gt12"])
            n_cache_hit += 1
            continue
        stats = load_stats(fid)
        if stats is None:
            dropped.append({"id": fid, "reason": "no_stats_json"})
            continue
        pred = np.load(PRED_DIR / f"{fid}.npy")
        try:
            gt = gt_chroma_from_source(stats)
        except Exception as e:
            dropped.append({"id": fid, "reason": f"audio_load_error:{e}"})
            continue
        if gt is None:
            dropped.append({"id": fid, "reason": "no_source_audio"})
            continue
        pred_a, gt_a, T = align(pred, gt)
        p12, g12 = fold_to_12(pred_a), fold_to_12(gt_a)
        kept_ids.append(fid)
        pred12_list.append(p12)
        gt12_list.append(g12)
        np.savez(cache_f, pred12=p12, gt12=g12)
        if (i + 1) % 200 == 0:
            print(f"[E2] pass1 {i+1}/{len(ids)} ({time.time()-t0:.1f}s, kept={len(kept_ids)}, cache_hit={n_cache_hit})", flush=True)
    print(f"[E2] pass1 done: kept={len(kept_ids)} dropped={len(dropped)} cache_hit={n_cache_hit} in {time.time()-t0:.1f}s", flush=True)

    if len(kept_ids) < 0.9 * len(ids):
        print(f"[E2] WARNING: kept only {len(kept_ids)}/{len(ids)} -- "
              f"sample drift vs Tier-2, sanity-check dropped_reasons before trusting results.", flush=True)

    variants = {}

    # ---- 1. corpus-demean (baseline, must reproduce Tier-2/Version-A) ----
    print("[E2] scoring variant 1: corpus-demean (baseline sanity check)...", flush=True)
    rows, null_rows = score_corpus_demean(pred12_list, gt12_list, kept_ids, args.n_null)
    variants["corpus_demean"] = {
        "matched": summarize(rows, BAND_NAMES),
        "null": summarize(null_rows, BAND_NAMES),
        "rows": rows,
    }

    # ---- 2. per-window z-norm ----
    print("[E2] scoring variant 2: per-window z-norm...", flush=True)
    rows, null_rows = score_variant("zn", perwindow_znorm, pred12_list, gt12_list, kept_ids, args.n_null)
    variants["perwindow_znorm"] = {
        "matched": summarize(rows, BAND_NAMES),
        "null": summarize(null_rows, BAND_NAMES),
        "rows": rows,
    }

    # ---- 3. per-window rank-norm ----
    print("[E2] scoring variant 3: per-window rank-norm...", flush=True)
    # Rank must be computed independently per band (12 values within a band, not
    # across all 36), so rank each band's (12,T) slice separately.
    pred12_rank = []
    gt12_rank = []
    for p, g in zip(pred12_list, gt12_list):
        pr = np.stack([perwindow_ranknorm(p[bi]) for bi in range(3)], axis=0)
        gr = np.stack([perwindow_ranknorm(g[bi]) for bi in range(3)], axis=0)
        pred12_rank.append(pr)
        gt12_rank.append(gr)
    rows, null_rows = score_variant("rank", None, pred12_rank, gt12_rank, kept_ids, args.n_null)
    variants["perwindow_ranknorm"] = {
        "matched": summarize(rows, BAND_NAMES),
        "null": summarize(null_rows, BAND_NAMES),
        "rows": rows,
    }

    # ---- 4. per-window rank-CENTERED (diagnostic, negative-result autopsy) ----
    # Raw ranks 1..12 all share the same mean (~6.5), so plain cos12 on ranks (variant
    # 3) is inflated for ANY pair (matched or mismatched) by that shared-offset --
    # exactly the "chroma trap" this repo's own methodology warns about, now hitting
    # the rank transform. Centering the ranks before cosine (== per-frame Spearman's
    # rho, since Pearson-corr-of-ranks == Spearman) removes that artifact and tests
    # the *actual* monotone-invariance hypothesis cleanly. Cheap to add on top of the
    # already-ranked arrays (perwindow_znorm mean-centers + norm-divides axis=-2).
    print("[E2] scoring variant 4: per-window rank-CENTERED (Spearman-rho-equivalent, diagnostic)...", flush=True)
    rows, null_rows = score_variant("rankcenter", perwindow_znorm, pred12_rank, gt12_rank, kept_ids, args.n_null)
    variants["perwindow_rankcenter_spearman"] = {
        "matched": summarize(rows, BAND_NAMES),
        "null": summarize(null_rows, BAND_NAMES),
        "rows": rows,
    }

    # ---- assemble + report ----
    baseline_expected = {"bass": 0.2135, "mid": 0.5360, "air": 0.9179}  # Tier-2/Version-A, median
    baseline_got = {b: variants["corpus_demean"]["matched"][b]["median"] for b in BAND_NAMES}
    sanity_ok = all(abs(baseline_got[b] - baseline_expected[b]) < 0.01 for b in BAND_NAMES)

    results = {
        "provenance": {
            "n_ids_from_tier2": len(ids),
            "n_kept": len(kept_ids),
            "n_dropped": len(dropped),
            "dropped_sample": dropped[:20],
            "n_null_derangements": args.n_null,
            "frame_rate_fps": FPS,
            "sanity_baseline_expected": baseline_expected,
            "sanity_baseline_got": baseline_got,
            "sanity_ok": sanity_ok,
        },
        "variants": {
            k: {"matched": {b: v["matched"][b] for b in BAND_NAMES},
                "null": {b: v["null"][b] for b in BAND_NAMES}}
            for k, v in variants.items()
        },
        "rows_by_variant": {k: v["rows"] for k, v in variants.items()},
    }
    out_path = HERE / "results.json"
    out_path.write_text(json.dumps(results, indent=1, default=str))
    print(f"[E2] wrote {out_path} ({time.time()-t0:.1f}s total)", flush=True)

    print(f"\n[E2] SANITY: baseline reproduction {'OK' if sanity_ok else 'MISMATCH'} "
          f"(expected {baseline_expected}, got {baseline_got})", flush=True)

    print("\n[E2] === TABLE: median cos12 (matched) / matched-null gap ===", flush=True)
    header = f"{'variant':<22} | " + " | ".join(f"{b:>22}" for b in BAND_NAMES)
    print(header, flush=True)
    print("-" * len(header), flush=True)
    for vname, v in variants.items():
        cells = []
        for b in BAND_NAMES:
            m = v["matched"][b]["median"]
            nu = v["null"][b]["median"]
            cells.append(f"{m:>7.3f} (gap {m-nu:+.3f})")
        print(f"{vname:<22} | " + " | ".join(f"{c:>22}" for c in cells), flush=True)


if __name__ == "__main__":
    main()
