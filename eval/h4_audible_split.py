#!/usr/bin/env python3
"""H4: is a 'weak' knob unreadable because it is INAUDIBLE in this context, or absent from SAME? (C, 2026-10-07, W's hypothesis)
W's effect_size_<set>.npz gives each ladder's audible effect (log-mel L1, first vs last rung). Per knob, split its ladders at the
median effect; 4-fold leave-ARCHETYPES-out ridge on temporal features, trained and scored within each half, plus the all-ladders fit
scored on each half. If readability rises in the audible half and stays ~0 in the inaudible half the knob is hidden, not absent.
USAGE  .venv/bin/python eval/h4_audible_split.py [--set ladders_v2t] [--dir .../h4_gate_v2]   CPU only
"""
import argparse
import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h4_ridge_baseline import features  # noqa: E402

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate_v2"


def ridge(X, y, alpha=1.0):
    mu = X.mean(0); Xc = X - mu
    w = np.linalg.solve(Xc.T @ Xc + alpha * np.eye(X.shape[1]) * np.trace(Xc.T @ Xc) / X.shape[1], Xc.T @ (y - y.mean()))
    return w, mu, y.mean()


def r2(p, y):
    return float(1 - ((p - y) ** 2).sum() / (((y - y.mean()) ** 2).sum() + 1e-12))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--set", default="ladders_v2t")
    ap.add_argument("--folds", type=int, default=4)
    a = ap.parse_args()
    d = np.load(f"{a.dir}/{a.set}.npz", allow_pickle=True)
    e = np.load(f"{a.dir}/effect_size_{a.set}.npz", allow_pickle=True)
    F = features(np.load(f"{a.dir}/{a.set}.latents_same_s.npz")["z"], "temporal")
    knobs = [str(k) for k in d["knobs"]]
    eff = dict(zip(e["ladder_id"].tolist(), e["audio_effect"].tolist()))
    arch = np.asarray(d["archetype_id"])
    res = {}
    for k, name in enumerate(knobs):
        m = d["knob_id"] == k
        if not m.any():
            continue
        Fk, kv, lid, ar = F[m], d["knob_value"][m].astype(np.float64), d["ladder_id"][m], arch[m]
        y = (kv - kv.mean()) / (kv.std() + 1e-9)
        ee = np.array([eff[int(l)] for l in lid]); hi = ee > np.median(ee)
        ids = np.random.default_rng(0).permutation(np.unique(ar)); fo = {x: i % a.folds for i, x in enumerate(ids)}
        f = np.array([fo[x] for x in ar])
        out = {n: np.zeros(len(y)) for n in ("all", "hi", "lo")}
        for fi in range(a.folds):
            te, tr = f == fi, f != fi
            for n, sel in (("all", np.ones(len(y), bool)), ("hi", hi), ("lo", ~hi)):
                w, mu, my = ridge(Fk[tr & sel], y[tr & sel])
                out[n][te] = (Fk[te] - mu) @ w + my
        res[name] = {"effect_median": float(np.median(ee)),
                     "r2_hi_trained_hi": r2(out["hi"][hi], y[hi]), "r2_lo_trained_lo": r2(out["lo"][~hi], y[~hi]),
                     "r2_all_on_hi": r2(out["all"][hi], y[hi]), "r2_all_on_lo": r2(out["all"][~hi], y[~hi])}
        r = res[name]
        print(f"{name:11s} audible-half R2 {r['r2_hi_trained_hi']:+.2f} (all-fit {r['r2_all_on_hi']:+.2f}) | inaudible-half R2 {r['r2_lo_trained_lo']:+.2f} (all-fit {r['r2_all_on_lo']:+.2f})")
    json.dump(res, open(f"{a.dir}/audible_split_{a.set}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
