#!/usr/bin/env python3
"""score_stem_vs_mix.py -- kick-contamination test for the `same_chroma` readout head.

Question: Tier-2 (`../same_chroma_readout_tier2_muscriptor_2026-08-11/`) found the head's
demeaned cos12 vs full-mix audio-GT chroma is bass=0.214 / mid=0.536 / air=0.918 -- bass is
by far the weakest band. Is that a HEAD failure, or a GROUND-TRUTH artifact: the full-mix
bass-band chroma GT includes the kick drum (broadband, pitchless low-freq transient) baked
into the same octave band as the bassline, while the head (reading the LATENT, which encodes
the actual harmonic content) correctly ignores it? If so, the head's bass-band prediction
should align BETTER with the isolated, kick-free bassline stem than with the kick-polluted
full-mix GT.

Reuses VERBATIM:
  - Tier-2's cached head predictions (`predict_head.py` output, no re-inference needed --
    cache already covers all 5400 real-goa latents that have a MuScriptor record).
  - Tier-1/Tier-2's cos12_timeavg / cos12_vec / fold_to_12 formulas and the
    matched-raw / null-derangement / corpus-demeaned scoring methodology (chroma-trap fix).
  - Tier-2's PRIMARY (full-mix) GT recipe: compute_same_chroma on the exact source-audio
    segment (source_path/start_sample/end_sample) -- but read those fields straight off
    latents_sa3's OWN {id}.json (verified byte-identical to MuScriptor's stats.json for the
    same id -- see REPORT.md "pairing verification"), so this test needs no MuScriptor
    dependency at all.

NEW ground truth: `latents_sa3_stem_chroma/{id}.npz` (`other` + `bass` keys, (3,128,4096)
fp16) -- `compute_same_chroma` run directly on the isolated BS-RoFormer stems for the exact
same crop window (built by extract_stem_chroma.py, confirmed same `{id}` = same crop as
latents_sa3). No alignment needed against pred (both already T=4096); full-mix GT is aligned
via `align()` (source audio segment length can differ by a few samples).

Venv: mir (compute_same_chroma, soundfile). No torch needed -- predictions are cached.
Run:
  /home/kim/Projects/mir/mir/bin/python score_stem_vs_mix.py [--n 1200] [--seed 42] [--n-null 5]
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

TIER1_DIR = "/home/kim/Projects/SAO/eval/musicology/same_chroma_readout_2026-08-11"
sys.path.insert(0, TIER1_DIR)
from score_and_report import cos12_timeavg, cos12_vec, BAND_NAMES  # noqa: E402

sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from harmonic.same_chroma import compute_same_chroma, fold_to_12  # noqa: E402

HERE = Path(__file__).parent
PRED_DIR = Path("/tmp/claude-1000/-home-kim-Projects-SAO/49cd5391-27e7-4545-8295-a1053db2a077/scratchpad/tier2_predicted")
LATENT_DIR = Path("/home/kim/Projects/latents_sa3")
STEM_CHROMA_DIR = Path("/run/media/kim/Lehto/latents_sa3_stem_chroma")


def align(a, b):
    T = min(a.shape[-1], b.shape[-1])
    return a[..., :T], b[..., :T], T


def load_latent_json(fid):
    p = LATENT_DIR / f"{fid}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def gt_chroma_from_source(meta):
    """Full-mix audio-GT: compute_same_chroma on the exact source-audio segment the
    latent was encoded from (source_path/start_sample/end_sample from latents_sa3's own
    {id}.json -- verified identical to MuScriptor's stats.json for the same id)."""
    path = meta.get("source_path")
    s0, s1 = meta.get("start_sample"), meta.get("end_sample")
    if not path or s0 is None or s1 is None:
        return None
    p = Path(path)
    if not p.exists():
        return None
    y, sr = sf.read(str(p), start=int(s0), frames=int(s1) - int(s0), always_2d=True)
    return compute_same_chroma(y, sr)  # (3,128,T) float32


def fixed_derangement(n, k, rng):
    perms = []
    idx = list(range(n))
    for _ in range(k):
        while True:
            p = idx[:]
            rng.shuffle(p)
            if n <= 1 or all(p[j] != j for j in range(n)):
                perms.append(p)
                break
    return perms


def quantiles(vals):
    if len(vals) == 0:
        return {}
    a = np.asarray(vals, dtype=float)
    a = a[~np.isnan(a)]
    if len(a) == 0:
        return {}
    qs = [10, 25, 50, 75, 90]
    return {
        "mean": float(np.mean(a)), "std": float(np.std(a)),
        "median": float(np.median(a)), "min": float(np.min(a)), "max": float(np.max(a)),
        **{f"p{q}": float(np.percentile(a, q)) for q in qs},
    }


def cos12_perframe_mean(a12, b12):
    num = (a12 * b12).sum(1)
    den = np.linalg.norm(a12, axis=1) * np.linalg.norm(b12, axis=1) + 1e-9
    c = num / den
    return np.nanmean(c, axis=-1)


def score_flavor(ids, a12_list, b12_list, n_null, rng_seed=12345):
    """Reused verbatim (structure) from Tier-2's score_and_report.py score_flavor:
    matched raw (timeavg + perframe), corpus-demeaned, and K-derangement null, for a
    generic (a=list of (3,12,T), b=list of (3,12,T)) pairing -- works for pred-vs-GT AND
    for GT-vs-GT (the diagnostic rows)."""
    n = len(ids)
    rows = []
    for i in range(n):
        ta = cos12_timeavg(a12_list[i], b12_list[i])
        pf = cos12_perframe_mean(a12_list[i], b12_list[i])
        rows.append({"id": ids[i], **{f"timeavg_{b}": float(ta[bi]) for bi, b in enumerate(BAND_NAMES)},
                     **{f"perframe_{b}": float(pf[bi]) for bi, b in enumerate(BAND_NAMES)}})

    a_ta_stack = np.stack([a.mean(-1) for a in a12_list], 0)  # (n,3,12)
    b_ta_stack = np.stack([b.mean(-1) for b in b12_list], 0)
    a_bar = a_ta_stack.mean(0)
    b_bar = b_ta_stack.mean(0)
    demeaned_rows = []
    for i in range(n):
        da = a_ta_stack[i] - a_bar
        db = b_ta_stack[i] - b_bar
        c = cos12_vec(da, db)
        demeaned_rows.append({"id": ids[i], **{f"demeaned_{b}": float(c[bi]) for bi, b in enumerate(BAND_NAMES)}})

    null_rows = []
    if n >= 3:
        rngN = random.Random(rng_seed)
        perms = fixed_derangement(n, n_null, rngN)
        for perm in perms:
            for i in range(n):
                j = perm[i]
                ta = cos12_timeavg(a12_list[i], b12_list[j])
                null_rows.append({f"timeavg_{b}": float(ta[bi]) for bi, b in enumerate(BAND_NAMES)})
    return rows, demeaned_rows, null_rows


def summarize(rows, keys):
    out = {}
    for key in keys:
        vals = [r[key] for r in rows if r.get(key) is not None]
        out[key] = quantiles(vals)
    out["n"] = len(rows)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-null", type=int, default=5)
    args = ap.parse_args()

    metric_keys = [f"{m}_{b}" for m in ("timeavg", "perframe") for b in BAND_NAMES]
    demean_keys = [f"demeaned_{b}" for b in BAND_NAMES]

    pred_ids = sorted(p.stem for p in PRED_DIR.glob("*.npy"))
    print(f"[score] {len(pred_ids)} predicted latents in {PRED_DIR}", flush=True)
    rng = random.Random(args.seed)
    sample_ids = pred_ids if len(pred_ids) <= args.n else rng.sample(pred_ids, args.n)
    sample_ids = sorted(sample_ids)
    print(f"[score] sample n={len(sample_ids)} (seed={args.seed}) -- IDENTICAL sampling call to "
          f"Tier-2's score_and_report.py (same pred_ids pool, same seed/n) => same 1200 tracks", flush=True)

    # ---- Pass 1: load pred, full-mix GT, other-stem GT, bass-stem GT per track ----
    ids_full, pred12_full, mix12_full = [], [], []          # baseline (#1): sanity-check vs Tier-2
    dropped_full = []
    ids_stem, pred12_stem, mix12_stem, other12_stem, bass12_stem = [], [], [], [], []
    dropped_stem = []

    t0 = time.time()
    for i, fid in enumerate(sample_ids):
        pred = np.load(PRED_DIR / f"{fid}.npy")  # (3,128,T)
        meta = load_latent_json(fid)
        if meta is None:
            dropped_full.append({"id": fid, "reason": "no_latent_json"})
            dropped_stem.append({"id": fid, "reason": "no_latent_json"})
            continue
        try:
            mix_gt = gt_chroma_from_source(meta)
        except Exception as e:
            mix_gt = None
            dropped_full.append({"id": fid, "reason": f"audio_load_error:{e}"})
        if mix_gt is None:
            if not any(d["id"] == fid for d in dropped_full):
                dropped_full.append({"id": fid, "reason": "no_source_audio"})
        else:
            pred_a, mix_a, T = align(pred, mix_gt)
            ids_full.append(fid)
            pred12_full.append(fold_to_12(pred_a))
            mix12_full.append(fold_to_12(mix_a))

        stem_p = STEM_CHROMA_DIR / f"{fid}.npz"
        if not stem_p.exists():
            dropped_stem.append({"id": fid, "reason": "no_stem_chroma_npz"})
            continue
        if mix_gt is None:
            dropped_stem.append({"id": fid, "reason": "no_mix_gt_for_diagnostic"})
            continue
        try:
            d = np.load(stem_p)
            other = d["other"].astype(np.float32)  # (3,128,4096)
            bass = d["bass"].astype(np.float32)
        except Exception as e:
            dropped_stem.append({"id": fid, "reason": f"stem_load_error:{e}"})
            continue
        # pred/mix already T=4096 == stem T; align defensively anyway
        pred_s, other_s, T1 = align(pred, other)
        _, bass_s, T2 = align(pred, bass)
        mix_s, _, _ = align(mix_gt, other)
        T3 = min(T1, T2, mix_s.shape[-1])
        ids_stem.append(fid)
        pred12_stem.append(fold_to_12(pred_s[..., :T3]))
        mix12_stem.append(fold_to_12(mix_s[..., :T3]))
        other12_stem.append(fold_to_12(other_s[..., :T3]))
        bass12_stem.append(fold_to_12(bass_s[..., :T3]))

        if (i + 1) % 200 == 0:
            dt = time.time() - t0
            print(f"[score] pass1 {i+1}/{len(sample_ids)} ({dt:.1f}s) full={len(ids_full)} stem={len(ids_stem)}", flush=True)
    print(f"[score] pass1 done in {time.time()-t0:.1f}s -- full_n={len(ids_full)} stem_n={len(ids_stem)}", flush=True)

    # ---- #1 baseline: pred vs full-mix GT, on the FULL n=1200 sample (sanity check vs Tier-2) ----
    print("[score] #1 pred vs full-mix GT (baseline / Tier-2 sanity check)...", flush=True)
    r1, d1, n1 = score_flavor(ids_full, pred12_full, mix12_full, args.n_null)

    # ---- #2/#3/#4 on the common stem-covered subset (apples-to-apples n) ----
    print(f"[score] #2 pred vs other-stem GT, #3 pred vs bass-stem GT, #4 diagnostics "
          f"(common subset n={len(ids_stem)})...", flush=True)
    r1s, d1s, n1s = score_flavor(ids_stem, pred12_stem, mix12_stem, args.n_null)     # pred vs full-mix (subset)
    r2, d2, n2 = score_flavor(ids_stem, pred12_stem, other12_stem, args.n_null)      # pred vs other-stem
    r3, d3, n3 = score_flavor(ids_stem, pred12_stem, bass12_stem, args.n_null)       # pred vs bass-stem  <- THE KICK TEST
    r4a, d4a, n4a = score_flavor(ids_stem, mix12_stem, other12_stem, args.n_null)    # diagnostic: mix GT vs other-stem GT
    r4b, d4b, n4b = score_flavor(ids_stem, mix12_stem, bass12_stem, args.n_null)     # diagnostic: mix GT vs bass-stem GT (kick magnitude)

    def pack(rows, demeaned, nulls):
        return {
            "matched_raw": summarize(rows, metric_keys),
            "demeaned": summarize(demeaned, demean_keys),
            "null_mismatched": summarize(nulls, [f"timeavg_{b}" for b in BAND_NAMES]),
            "n": len(rows),
        }

    results = {
        "provenance": {
            "head_ckpt": "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_same_chroma_best.pt",
            "pred_cache": str(PRED_DIR),
            "pred_cache_reused_from": "same_chroma_readout_tier2_muscriptor_2026-08-11/predict_head.py (no re-inference)",
            "n_predicted_available": len(pred_ids),
            "n_sampled": len(sample_ids),
            "seed": args.seed,
            "n_null_derangements": args.n_null,
            "n_full_mix_pairable": len(ids_full),
            "n_common_subset_with_stem_chroma": len(ids_stem),
            "pairing_verification": "latents_sa3/{id}.json source_path/start_sample/end_sample confirmed "
                                     "byte-identical to muscriptor_full/{id}.stats.json for id=000000 "
                                     "(same source_path, start_sample=44100, end_sample=16821316); "
                                     "extract_stem_chroma.py builds latents_sa3_stem_chroma/{id}.npz directly "
                                     "from latents_sa3/{id}.json's own source_path/start_sample/end_sample "
                                     "(same dir's other.flac/bass.flac), so {id} denotes the exact same crop "
                                     "across latents_sa3, muscriptor_full, and latents_sa3_stem_chroma.",
        },
        "dropped_full_mix_sample": dropped_full[:50],
        "dropped_stem_sample": dropped_stem[:50],
        "1_pred_vs_fullmix_baseline_n1200": pack(r1, d1, n1),
        "1b_pred_vs_fullmix_common_subset": pack(r1s, d1s, n1s),
        "2_pred_vs_other_stem": pack(r2, d2, n2),
        "3_pred_vs_bass_stem_KICK_TEST": pack(r3, d3, n3),
        "4a_diagnostic_fullmix_vs_other_stem": pack(r4a, d4a, n4a),
        "4b_diagnostic_fullmix_vs_bass_stem_KICK_MAGNITUDE": pack(r4b, d4b, n4b),
    }

    out_path = HERE / "results.json"
    out_path.write_text(json.dumps(results, indent=1, default=str))
    print(f"[score] wrote {out_path} ({time.time()-t0:.1f}s total)", flush=True)

    def fmt(d):
        return f"median={d.get('median', float('nan')):.3f}"

    print("\n=== SUMMARY (demeaned median cos12, common subset n=%d) ===" % len(ids_stem))
    for label, pk in [("vs full-mix (subset)", pack(r1s, d1s, n1s)),
                       ("vs other-stem", pack(r2, d2, n2)),
                       ("vs bass-stem (KICK TEST)", pack(r3, d3, n3))]:
        line = f"{label:28s}"
        for b in BAND_NAMES:
            line += f" {b}={fmt(pk['demeaned'][f'demeaned_{b}'])}"
        print(line)
    print("\n=== DIAGNOSTIC (full-mix GT vs stem GT, demeaned median cos12) ===")
    for label, pk in [("mix vs other-stem", pack(r4a, d4a, n4a)),
                       ("mix vs bass-stem (kick mag)", pack(r4b, d4b, n4b))]:
        line = f"{label:28s}"
        for b in BAND_NAMES:
            line += f" {b}={fmt(pk['demeaned'][f'demeaned_{b}'])}"
        print(line)


if __name__ == "__main__":
    main()
