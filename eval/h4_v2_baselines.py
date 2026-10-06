#!/usr/bin/env python3
"""H4 v2: the cheap baselines (mean direction, pooled ridge) across W's 10 knobs, by phrase rhythm (C, 2026-10-06).
Data: h4_gate_v2/ladders_v2.npz + ladders_v2.latents_same_s.npz (2000 ladders = 10 knobs x 200, 4 rhythms, 8/16 rungs).
Uses eval/h4_ridge_baseline.evaluate (5-fold over ladders; a ladder is never in train and test). Chance identify = 1/10.
USAGE  .venv/bin/python eval/h4_v2_baselines.py [--features temporal] [--dir ...]   CPU only
"""
import argparse
import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h4_ridge_baseline import evaluate, features  # noqa: E402

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate_v2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--features", choices=["mean", "meanstd", "temporal"], default="temporal")
    ap.add_argument("--alpha", type=float, default=1.0)
    a = ap.parse_args()
    d = np.load(f"{a.dir}/ladders_v2.npz", allow_pickle=True)
    Z = np.load(f"{a.dir}/ladders_v2.latents_same_s.npz")["z"]
    M = features(Z, a.features)
    knobs = [str(k) for k in d["knobs"]]; rhy = [str(r) for r in d["rhythms"]]
    ax, lid, rg, val, rid = d["knob_id"], d["ladder_id"], d["rung"], d["knob_value"], d["rhythm_id"]
    res = evaluate(M, ax, lid, rg, len(knobs), alpha=a.alpha, val=val)
    lad_rhy = {int(l): int(rid[lid == l][0]) for l in np.unique(lid)}
    out = {"features": a.features, "chance": 1 / len(knobs), "knobs": knobs, "rhythms": rhy}
    for name in ("mean", "ridge"):
        hits = res[name]["ladder_hits"]
        out[name] = {"identify_overall": res[name]["identify_overall"],
                     "per_knob": {knobs[k]: res[name]["per_axis"][k] for k in range(len(knobs))},
                     "identify_by_rhythm": {rhy[r]: float(np.mean([h for l, h in hits.items() if lad_rhy[l] == r])) for r in range(len(rhy))}}
    out["ridge_heldout_r2"] = {knobs[k]: v for k, v in res["ridge_heldout_r2"].items()}
    print(f"features={a.features}  identify mean {out['mean']['identify_overall']:.2f} ridge {out['ridge']['identify_overall']:.2f} (chance {out['chance']:.2f})")
    for k, n in enumerate(knobs):
        print(f"{n:11s} identify mean {out['mean']['per_knob'][n]['identify']:.2f} ridge {out['ridge']['per_knob'][n]['identify']:.2f}"
              f" | rho mean {out['mean']['per_knob'][n]['monotone_rho']:+.2f} ridge {out['ridge']['per_knob'][n]['monotone_rho']:+.2f} | ridge R2 {out['ridge_heldout_r2'][n]:+.2f}")
    print("identify by rhythm  mean:", {r: round(v, 2) for r, v in out["mean"]["identify_by_rhythm"].items()},
          " ridge:", {r: round(v, 2) for r, v in out["ridge"]["identify_by_rhythm"].items()})
    json.dump(out, open(f"{a.dir}/baselines_{a.features}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
