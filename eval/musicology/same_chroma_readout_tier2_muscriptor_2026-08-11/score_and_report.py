#!/usr/bin/env python3
"""score_and_report.py -- Stage B of the Tier-2 same_chroma readout test (REAL goa).

Scores the head-predicted 384-d chroma (Stage A, predict_head.py, SAO/.venv, cached
in /tmp/.../scratchpad/tier2_predicted/{id}.npy) against TWO ground-truth flavors on
real goa music:

  PRIMARY  -- audio-derived SAME chroma (compute_same_chroma) on the EXACT source
              audio segment the latent was encoded from. Located via the MuScriptor
              transcription's stats.json (`source_path`/`start_sample`/`end_sample`
              -- written for every attempted transcription regardless of quality, so
              this flavor does NOT need to pass the integrity filter). Non-circular:
              this is genuine nonlinear DSP-extracted chroma from real audio, NOT the
              linear-readout proxy in `latents_sa3_chroma/*.npz` (that proxy is
              target[b] = W[b] @ z + bias[b] applied directly to the SAME latent --
              see extract_same_chroma_targets.py -- which would make the test
              circular against the head's own likely training target family).
  SECONDARY -- MuScriptor-MIDI-derived per-frame band-pitch-class GT (melody-identity,
              transcription-noisy). Gated on the SAME integrity cutoff phase1_features.py
              used (`integrity_flag == true AND integrity_pc_corr >= 0.30`).

*** CHROMA-TRAP GUARD (found during the required single-track sanity check) ***
A raw pooled cos12 on 50 real goa tracks came back suspiciously high on EVERY band
(bass .987/mid .996/air .988 timeavg) -- categorically higher than Tier-1's synthetic
battery (bass .815/mid .861). Inspecting the actual 12-d vectors showed why: goa is
genre-homogeneous (per the 2026-07-22 musicological study -- 3/4 minor, dominant
tonic-heavy rolling bass, same lead-grammar corpus-wide), so BOTH the head's
prediction and the audio-GT are pulled toward a shared "generic goa chroma shape"
independent of any real per-track readout skill -- the exact "chroma trap" already
documented in this repo (`eval/melody_wall_analysis.py`'s whitening note: "RAW chroma
cosine saturates ~0.95 on tonal goa"; WORKLOG 2026-07-12 "matched-key beats wrong-key
0.789 vs 0.751 -- thin absolute margin"). A metric that doesn't control for this can't
tell "the head reads THIS track's content" from "the head outputs a generic goa-ish
vector that trivially resembles any goa track's GT."
Fix, applied below: for every matched (pred[i], gt[i]) pair, ALSO score
mismatched-pair NULLS -- pred[i] against K other tracks' GT (a fixed derangement) --
and a corpus-DEMEANED variant (subtract the corpus-mean 12-d profile from both pred
and gt before cosine, isolating the track-specific residual). The real signal is
matched-vs-null delta and the demeaned cosine, NOT the raw pooled number.

Reused verbatim from Tier-1 (`same_chroma_readout_2026-08-11/score_and_report.py`):
cos12_timeavg, cos12_perframe_mean, notes_from_midi, band_of_pitch, midi_pc_grid,
BAND_NAMES, FPS. compute_same_chroma/fold_to_12 reused verbatim from mir-same-chroma.

Venv: mir (librosa/essentia/mido; soundfile for audio I/O).
Run:
  /home/kim/Projects/mir/mir/bin/python score_and_report.py [--n 1000] [--seed 42] [--n-null 5]
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from harmonic.same_chroma import compute_same_chroma, fold_to_12  # noqa: E402

TIER1_DIR = "/home/kim/Projects/SAO/eval/musicology/same_chroma_readout_2026-08-11"
sys.path.insert(0, TIER1_DIR)
from score_and_report import (  # noqa: E402
    cos12_timeavg, cos12_vec, notes_from_midi, band_of_pitch,
    midi_pc_grid, BAND_NAMES, FPS,
)

HERE = Path(__file__).parent
PRED_DIR = Path("/tmp/claude-1000/-home-kim-Projects-SAO/49cd5391-27e7-4545-8295-a1053db2a077/scratchpad/tier2_predicted")
LATENT_DIR = Path("/home/kim/Projects/latents_sa3")
MUSCRIPTOR_DIR = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/muscriptor_full")
HEAD_CKPT = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_same_chroma_best.pt"
CORR_CUTOFF = 0.30  # same as phase1_features.py


def align(a, b):
    T = min(a.shape[-1], b.shape[-1])
    return a[..., :T], b[..., :T], T


def cos12_perframe_mean(a12, b12):
    """(3,12,T) x (3,12,T) -> (3,) mean-over-frames cosine per band. (Reused formula
    from Tier-1; re-defined here so it also works on cross-track mismatched pairs of
    possibly-different T after align().)"""
    num = (a12 * b12).sum(1)
    den = np.linalg.norm(a12, axis=1) * np.linalg.norm(b12, axis=1) + 1e-9
    c = num / den
    return np.nanmean(c, axis=-1)


def load_stats(fid):
    p = MUSCRIPTOR_DIR / f"{fid}.stats.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def gt_chroma_from_source(stats):
    """PRIMARY GT: compute_same_chroma on the exact source-audio segment the latent
    was encoded from (source_path/start_sample/end_sample from the MuScriptor
    stats.json -- written independent of transcription quality)."""
    path = stats.get("source_path")
    s0, s1 = stats.get("start_sample"), stats.get("end_sample")
    if not path or s0 is None or s1 is None:
        return None
    p = Path(path)
    if not p.exists():
        return None
    y, sr = sf.read(str(p), start=int(s0), frames=int(s1) - int(s0), always_2d=True)
    return compute_same_chroma(y, sr)  # (3,128,T) float32


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


def fixed_derangement(n, k, rng):
    """k derangement-like permutations of range(n): perm[j] != j for (almost) all j
    (best-effort -- small residual fixed points on tiny n are acceptable and rare)."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000, help="random sample size for scoring")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-null", type=int, default=5, help="number of mismatched-pair derangements for the null control")
    args = ap.parse_args()

    pred_ids = sorted(p.stem for p in PRED_DIR.glob("*.npy"))
    print(f"[score] {len(pred_ids)} predicted latents available in {PRED_DIR}", flush=True)
    rng = random.Random(args.seed)
    sample_ids = pred_ids if len(pred_ids) <= args.n else rng.sample(pred_ids, args.n)
    sample_ids = sorted(sample_ids)
    print(f"[score] scoring n={len(sample_ids)} (seed={args.seed})", flush=True)

    # ---- Pass 1: build per-track (3,12,T) folded arrays for PRIMARY (audio-GT) and
    # SECONDARY (MIDI-GT), caching them for the null/demeaned passes below. ----
    primary_ids, primary_pred12, primary_gt12 = [], [], []
    primary_dropped = []
    secondary_ids, secondary_pred12, secondary_bandpc, secondary_hasnotes, secondary_nnotes = [], [], [], [], []
    secondary_dropped = []
    artist_titles = {}

    t0 = time.time()
    for i, fid in enumerate(sample_ids):
        pred = np.load(PRED_DIR / f"{fid}.npy")  # (3,128,T)
        stats = load_stats(fid)
        if stats is None:
            primary_dropped.append({"id": fid, "reason": "no_stats_json"})
            secondary_dropped.append({"id": fid, "reason": "no_stats_json"})
            continue
        artist_titles[fid] = stats.get("source_track")

        # ---- PRIMARY: audio-GT ----
        try:
            gt = gt_chroma_from_source(stats)
        except Exception as e:
            gt = None
            primary_dropped.append({"id": fid, "reason": f"audio_load_error:{e}"})
        if gt is None:
            if not any(d["id"] == fid for d in primary_dropped):
                primary_dropped.append({"id": fid, "reason": "no_source_audio"})
        else:
            pred_a, gt_a, T = align(pred, gt)
            primary_ids.append(fid)
            primary_pred12.append(fold_to_12(pred_a))
            primary_gt12.append(fold_to_12(gt_a))

        # ---- SECONDARY: MuScriptor-MIDI GT ----
        integrity_ok = bool(stats.get("integrity_flag")) and (stats.get("integrity_pc_corr") or -1) >= CORR_CUTOFF
        mid_path = MUSCRIPTOR_DIR / f"{fid}.mid"
        if not integrity_ok:
            secondary_dropped.append({"id": fid, "reason": "integrity_below_cutoff",
                                       "integrity_flag": stats.get("integrity_flag"),
                                       "integrity_pc_corr": stats.get("integrity_pc_corr")})
        elif not mid_path.exists():
            secondary_dropped.append({"id": fid, "reason": "no_mid_file"})
        else:
            try:
                notes = notes_from_midi(mid_path)
                T = pred.shape[-1]
                _, band_pc = midi_pc_grid(notes, T)
                secondary_ids.append(fid)
                secondary_pred12.append(fold_to_12(pred))
                secondary_bandpc.append(band_pc)
                secondary_hasnotes.append([bool(band_pc[bi].sum() > 0) for bi in range(3)])
                secondary_nnotes.append(len(notes))
            except Exception as e:
                secondary_dropped.append({"id": fid, "reason": f"midi_error:{e}"})

        if (i + 1) % 100 == 0:
            dt = time.time() - t0
            print(f"[score] pass1 {i+1}/{len(sample_ids)} ({dt:.1f}s, {dt/(i+1):.3f}s/file, "
                  f"primary={len(primary_ids)} secondary={len(secondary_ids)})", flush=True)
    print(f"[score] pass1 done in {time.time()-t0:.1f}s", flush=True)

    # ---- Pass 2: matched / null / demeaned metrics for PRIMARY ----
    def score_flavor(ids, pred12_list, gt12_list, n_null, allow_null=True):
        n = len(ids)
        rows = []
        for i in range(n):
            ta = cos12_timeavg(pred12_list[i], gt12_list[i])
            pf = cos12_perframe_mean(pred12_list[i], gt12_list[i])
            rows.append({"id": ids[i], **{f"timeavg_{b}": float(ta[bi]) for bi, b in enumerate(BAND_NAMES)},
                         **{f"perframe_{b}": float(pf[bi]) for bi, b in enumerate(BAND_NAMES)}})

        # corpus-demeaned: subtract the corpus-mean time-averaged 12-d profile (per band)
        # from BOTH pred and gt before cosine -- isolates track-specific residual.
        pred_ta_stack = np.stack([p.mean(-1) for p in pred12_list], 0)  # (n,3,12)
        gt_ta_stack = np.stack([g.mean(-1) for g in gt12_list], 0)
        pred_bar = pred_ta_stack.mean(0)  # (3,12)
        gt_bar = gt_ta_stack.mean(0)
        demeaned_rows = []
        for i in range(n):
            dp = pred_ta_stack[i] - pred_bar  # (3,12)
            dg = gt_ta_stack[i] - gt_bar
            c = cos12_vec(dp, dg)  # (3,)
            demeaned_rows.append({"id": ids[i], **{f"demeaned_{b}": float(c[bi]) for bi, b in enumerate(BAND_NAMES)}})

        # null: K derangements, mismatched pred[i] vs gt[perm[i]]
        null_rows = []
        if allow_null and n >= 3:
            rngN = random.Random(12345)
            perms = fixed_derangement(n, n_null, rngN)
            for perm in perms:
                for i in range(n):
                    j = perm[i]
                    ta = cos12_timeavg(pred12_list[i], gt12_list[j])
                    null_rows.append({f"timeavg_{b}": float(ta[bi]) for bi, b in enumerate(BAND_NAMES)})
        return rows, demeaned_rows, null_rows

    print("[score] pass2: matched/demeaned/null for PRIMARY...", flush=True)
    primary_rows, primary_demeaned, primary_null = score_flavor(
        primary_ids, primary_pred12, primary_gt12, args.n_null)

    print("[score] pass2: matched/demeaned/null for SECONDARY...", flush=True)
    secondary_rows, secondary_demeaned, secondary_null = score_flavor(
        secondary_ids, secondary_pred12, secondary_bandpc, args.n_null, allow_null=True)
    # attach n_notes / has_notes to secondary rows
    for i, fid in enumerate(secondary_ids):
        secondary_rows[i]["n_notes"] = secondary_nnotes[i]
        for bi, b in enumerate(BAND_NAMES):
            secondary_rows[i][f"has_notes_{b}"] = secondary_hasnotes[i][bi]
            if not secondary_hasnotes[i][bi]:
                secondary_rows[i][f"timeavg_{b}"] = None
                secondary_rows[i][f"perframe_{b}"] = None

    def summarize(rows, prefix_keys):
        out = {}
        for key in prefix_keys:
            vals = [r[key] for r in rows if r.get(key) is not None]
            out[key] = quantiles(vals)
        out["n"] = len(rows)
        return out

    metric_keys_ta_pf = [f"{m}_{b}" for m in ("timeavg", "perframe") for b in BAND_NAMES]
    metric_keys_demean = [f"demeaned_{b}" for b in BAND_NAMES]

    primary_summary = summarize(primary_rows, metric_keys_ta_pf)
    primary_demeaned_summary = summarize(primary_demeaned, metric_keys_demean)
    primary_null_summary = summarize(primary_null, [f"timeavg_{b}" for b in BAND_NAMES])

    secondary_summary = summarize(secondary_rows, metric_keys_ta_pf)
    secondary_demeaned_summary = summarize(secondary_demeaned, metric_keys_demean)
    secondary_null_summary = summarize(secondary_null, [f"timeavg_{b}" for b in BAND_NAMES])
    for b in BAND_NAMES:
        secondary_summary[f"timeavg_{b}"]["n_with_notes"] = sum(1 for h in secondary_hasnotes if h[BAND_NAMES.index(b)])

    results = {
        "provenance": {
            "head_ckpt": HEAD_CKPT,
            "n_predicted_available": len(pred_ids),
            "n_sampled": len(sample_ids),
            "seed": args.seed,
            "n_null_derangements": args.n_null,
            "frame_rate_fps": FPS,
            "corr_cutoff_secondary": CORR_CUTOFF,
            "chroma_trap_note": "raw pooled cos12 on real goa is inflated by genre-homogeneous "
                                 "chroma shape shared across tracks; matched-vs-null delta and the "
                                 "corpus-demeaned cosine are the trustworthy signals, not the raw number.",
        },
        "primary_audio_gt": {
            "n_paired": len(primary_rows), "n_dropped": len(primary_dropped),
            "dropped_reasons_sample": primary_dropped[:50],
            "matched_raw": primary_summary,
            "demeaned": primary_demeaned_summary,
            "null_mismatched": primary_null_summary,
            "rows": primary_rows,
        },
        "secondary_muscriptor_midi_gt": {
            "n_paired": len(secondary_rows), "n_dropped": len(secondary_dropped),
            "dropped_reasons_sample": secondary_dropped[:50],
            "matched_raw": secondary_summary,
            "demeaned": secondary_demeaned_summary,
            "null_mismatched": secondary_null_summary,
            "rows": secondary_rows,
        },
    }

    out_path = HERE / "results.json"
    out_path.write_text(json.dumps(results, indent=1, default=str))
    print(f"[score] wrote {out_path} ({time.time()-t0:.1f}s total)", flush=True)
    print(f"[score] PRIMARY paired={len(primary_rows)} dropped={len(primary_dropped)}", flush=True)
    print(f"[score] SECONDARY paired={len(secondary_rows)} dropped={len(secondary_dropped)}", flush=True)

    def fmt(d):
        return f"mean={d.get('mean', float('nan')):.3f} median={d.get('median', float('nan')):.3f}"

    for b in BAND_NAMES:
        print(f"[score] PRIMARY {b}: matched {fmt(primary_summary[f'timeavg_{b}'])} | "
              f"null {fmt(primary_null_summary[f'timeavg_{b}'])} | "
              f"demeaned {fmt(primary_demeaned_summary[f'demeaned_{b}'])}", flush=True)


if __name__ == "__main__":
    main()
