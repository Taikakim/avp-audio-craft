#!/usr/bin/env python3
"""H4 v2: END-TO-END vs LOCAL (per-third-of-the-sweep) direction consistency for every knob (W's request 2026-10-06, to stop
curvature hiding: a knob can have a shared end-to-end chord while its local steps rotate).
Per ladder: displacement over the whole sweep and over each third of the rungs, on the time-mean latent (as eval/h4_same_directions.py).
Per knob: mean signed pairwise cosine across ladders for 'full', 'low', 'mid', 'high'; curvature = full - mean(thirds).
USAGE  .venv/bin/python eval/h4_v2_segments.py [--dir .../h4_gate_v2]   CPU only
"""
import argparse
import json
import numpy as np

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate_v2"


def pair_cos(D):
    D = D / (np.linalg.norm(D, axis=1, keepdims=True) + 1e-12)
    G = D @ D.T
    return float(G[~np.eye(len(D), dtype=bool)].mean())


def segments(M, knob, ladder, rung, n_rungs, n_knobs):
    out = {}
    for k in range(n_knobs):
        D = {"full": [], "low": [], "mid": [], "high": []}
        for l in np.unique(ladder[knob == k]):
            i = np.where(ladder == l)[0]; i = i[np.argsort(rung[i])]
            n = len(i); b = [0, n // 3, (2 * n) // 3, n - 1]
            D["full"].append(M[i[-1]] - M[i[0]])
            for name, (s, e) in zip(("low", "mid", "high"), ((b[0], b[1]), (b[1], b[2]), (b[2], b[3]))):
                D[name].append(M[i[e]] - M[i[s]])
        out[k] = {n: pair_cos(np.array(v)) for n, v in D.items()}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    a = ap.parse_args()
    d = np.load(f"{a.dir}/ladders_v2.npz", allow_pickle=True)
    M = np.load(f"{a.dir}/ladders_v2.latents_same_s.npz")["z"].astype(np.float32).mean(-1)
    knobs = [str(k) for k in d["knobs"]]
    seg = segments(M, d["knob_id"], d["ladder_id"], d["rung"], d["n_rungs"], len(knobs))
    res = {}
    print(f"{'knob':11s} full   low   mid  high  curvature(full - mean thirds)")
    for k, n in enumerate(knobs):
        s = seg[k]; curv = s["full"] - np.mean([s["low"], s["mid"], s["high"]])
        res[n] = {**s, "curvature": curv}
        print(f"{n:11s} {s['full']:+.2f} {s['low']:+.2f} {s['mid']:+.2f} {s['high']:+.2f}   {curv:+.2f}")
    json.dump(res, open(f"{a.dir}/segment_consistency.json", "w"), indent=1)


if __name__ == "__main__":
    main()
