#!/usr/bin/env python3
"""Re-score onset control runs with the p95-gated onset meter (mir venv).

C's ask (onset narrative Gaps 1+5): the landing narrative quotes per-gain control
correlations, but they were measured with plain onset_detect, which OVER-FIRES ~3x on
textured drones (13-14/s on "sparse ambient" = flux garbage). Re-measure A_cc_v2,
E_fusion_v2, and the lr2e5 sweep with the SAME p95-gated peak-pick meter (delta=0.3,
validated 2026-07-10: dense 9.2/s vs sparse 4.2/s) so the head-to-head is apples-to-apples.

Requested gain+density are parsed from the staged clip filenames
(`<run>_p<P>_s<S>_g<G>_d<D>.m4a`) — no onset_eval.json needed. Per (run, gain) we report
the requested-vs-measured correlation = the control-authority number.

Run (mir venv):
  mir/bin/python control/sa3_control/onset_rescore_p95.py --out /tmp/.../rescore.json
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layer_patch_map import meter_onset_rate  # the p95-gated meter, reused verbatim

STAGE = "/home/kim/evals_aac/control_runs"
# trailing _g<G>_d<D> — matches both `..._p0_s1234_g1_d12` (A_cc/E_fusion) and
# `onset_g0.5_d10` (lr2e5 sweep). p/s optional. D may be float like 7.5.
FN_RE = re.compile(r"_g(?P<g>[\d.]+)_d(?P<d>[\d.]+)$")
FN_PS = re.compile(r"_p(?P<p>\d+)_s")


def read_audio(path):
    # staged clips are AAC .m4a -> soundfile can't decode; librosa's audioread/ffmpeg
    # backend handles it (CLAUDE.md read_audio note). Resample to 22050 is fine for onsets.
    import librosa
    y, sr = librosa.load(path, sr=22050, mono=True)
    return y, sr


def rescore_dir(run_dir):
    rows = []
    for f in sorted(glob.glob(f"{run_dir}/*.m4a")):
        stem = os.path.splitext(os.path.basename(f))[0]
        m = FN_RE.search(stem)
        if not m:
            continue
        try:
            y, sr = read_audio(f)
            measured = meter_onset_rate(y, sr)
        except Exception as e:
            print(f"  ! {stem}: {e}", file=sys.stderr)
            continue
        mps = FN_PS.search(stem)
        rows.append({"gain": float(m["g"]), "requested": float(m["d"]),
                     "measured": round(measured, 3), "prompt": int(mps["p"]) if mps else 0})
    return rows


def per_gain_corr(rows):
    out = {}
    gains = sorted({r["gain"] for r in rows})
    for g in gains:
        rr = [r for r in rows if r["gain"] == g]
        req = np.array([r["requested"] for r in rr])
        mea = np.array([r["measured"] for r in rr])
        if len(rr) >= 3 and req.std() > 0 and mea.std() > 0:
            corr = float(np.corrcoef(req, mea)[0, 1])
        else:
            corr = None
        out[str(g)] = {"n": len(rr), "corr": (round(corr, 3) if corr is not None else None),
                       "measured_range": [round(float(mea.min()), 2), round(float(mea.max()), 2)] if len(rr) else None}
    # pooled across gains too
    req = np.array([r["requested"] for r in rows]); mea = np.array([r["measured"] for r in rows])
    pooled = float(np.corrcoef(req, mea)[0, 1]) if len(rows) >= 3 and req.std() > 0 and mea.std() > 0 else None
    return {"per_gain": out, "pooled_corr": (round(pooled, 3) if pooled is not None else None), "n": len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    result = {"meter": "p95-gated peak_pick delta=0.3 (layer_patch_map.meter_onset_rate)", "runs": {}}

    # the two head-to-head heads
    for run in ("A_cc_v2", "E_fusion_v2"):
        d = f"{STAGE}/{run}"
        if not os.path.isdir(d):
            print(f"skip {run} (no dir)"); continue
        print(f"[rescore] {run} ...", flush=True)
        rows = rescore_dir(d)
        result["runs"][run] = per_gain_corr(rows)
        print(f"  {run}: pooled corr {result['runs'][run]['pooled_corr']} (n={len(rows)})", flush=True)

    # the lr2e5 sweep -> the corrected authority-vs-training curve; report best ckpt
    lr2e5 = {}
    for d in sorted(glob.glob(f"{STAGE}/onset_eval_lr2e5_*")):
        step = os.path.basename(d).replace("onset_eval_lr2e5_", "")
        rows = rescore_dir(d)
        if not rows:
            continue
        lr2e5[step] = per_gain_corr(rows)
        print(f"[rescore] lr2e5 step {step}: pooled {lr2e5[step]['pooled_corr']} (n={len(rows)})", flush=True)
    result["runs"]["lr2e5_sweep"] = lr2e5
    # best by pooled corr
    valid = {k: v["pooled_corr"] for k, v in lr2e5.items() if v["pooled_corr"] is not None}
    if valid:
        best = max(valid, key=valid.get)
        result["lr2e5_best"] = {"step": best, "pooled_corr": valid[best]}
        print(f"\n[lr2e5 BEST] step {best}: pooled corr {valid[best]}", flush=True)

    json.dump(result, open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out}")
    # headline summary
    print("\n=== p95-gated control-authority (pooled corr) ===")
    for run in ("A_cc_v2", "E_fusion_v2"):
        if run in result["runs"]:
            print(f"  {run:16s} {result['runs'][run]['pooled_corr']}")
    if "lr2e5_best" in result:
        print(f"  {'lr2e5_best':16s} {result['lr2e5_best']['pooled_corr']}  (step {result['lr2e5_best']['step']})")


if __name__ == "__main__":
    main()
