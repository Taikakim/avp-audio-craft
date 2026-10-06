#!/usr/bin/env python3
"""H4 family-transfer test: fit the pooled-ridge knob readout on one ladder set, score it on another (C, 2026-10-06).
v2 (val-split prior, 16 families) <-> v2t (train-split prior, 105 presets) are disjoint preset pools, so this is a clean
'new families' test (W). Smoke: v2 -> v2c (same prior, cutoff only). Per knob: held-out R2 and mean within-ladder Spearman of the
standardised knob value, ridge on temporal features (eval/h4_ridge_baseline.features), plus identify across the knobs
both sets share (mean displacement direction fitted on the source set; chance 1/n).
USAGE  .venv/bin/python eval/h4_transfer.py --src ladders_v2 --dst ladders_v2t [--dir .../h4_gate_v2]   CPU only
"""
import argparse
import json
import os
import sys
import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h4_ridge_baseline import features, unit  # noqa: E402

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate_v2"


def load(dir_, name):
    d = np.load(f"{dir_}/{name}.npz", allow_pickle=True)
    Z = np.load(f"{dir_}/{name}.latents_same_s.npz")["z"]
    return d, features(Z, "temporal")


def ladder_disp(F, ladder, rung, rows):
    out = {}
    for l in np.unique(ladder[rows]):
        i = np.where(rows & (ladder == l))[0]; i = i[np.argsort(rung[i])]
        out[int(l)] = F[i[-1]] - F[i[0]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--src", default="ladders_v2")
    ap.add_argument("--dst", default="ladders_v2t")
    ap.add_argument("--alpha", type=float, default=1.0)
    a = ap.parse_args()
    ds, Fs = load(a.dir, a.src)
    dd, Fd = load(a.dir, a.dst)
    ks = [str(k) for k in ds["knobs"]]; kd = [str(k) for k in dd["knobs"]]
    shared = [k for k in ks if k in kd]                                    # directions are fitted for every shared knob (distractors)
    scored = [k for k in shared if (dd["knob_id"] == kd.index(k)).any()]   # but only knobs that have rows in dst are scored
    res, U = {}, {}
    for name in shared:
        ms, md = ds["knob_id"] == ks.index(name), dd["knob_id"] == kd.index(name)
        U[name] = unit(np.mean([unit(v) for v in ladder_disp(Fs, ds["ladder_id"], ds["rung"], ms).values()], 0))
        if name not in scored:
            continue
        y = ds["knob_value"][ms].astype(np.float64); mu_y, sd_y = y.mean(), y.std() + 1e-9
        X = Fs[ms]; mu = X.mean(0); Xc = X - mu
        w = np.linalg.solve(Xc.T @ Xc + a.alpha * np.eye(X.shape[1]) * np.trace(Xc.T @ Xc) / X.shape[1], Xc.T @ ((y - mu_y) / sd_y))
        yt = (dd["knob_value"][md] - mu_y) / sd_y
        pred = (Fd[md] - mu) @ w
        lid, rg = dd["ladder_id"][md], dd["rung"][md]
        rho = np.nanmean([spearmanr(rg[lid == l], pred[lid == l])[0] for l in np.unique(lid)])
        res[name] = {"r2": float(1 - ((pred - yt) ** 2).sum() / ((yt - yt.mean()) ** 2).sum()), "rho": float(rho)}
    hit = {n: [] for n in scored}
    for name in scored:
        md = dd["knob_id"] == kd.index(name)
        for v in ladder_disp(Fd, dd["ladder_id"], dd["rung"], md).values():
            hit[name].append(int(shared[int(np.argmax([unit(v) @ U[n] for n in shared]))] == name))
    for n in scored:
        res[n]["identify"] = float(np.mean(hit[n]))
        print(f"{n:11s} transfer R2 {res[n]['r2']:+.2f} rho {res[n]['rho']:+.2f} identify {res[n]['identify']:.2f}")
    print(f"identify overall {np.mean([h for v in hit.values() for h in v]):.2f} (chance {1/len(shared):.2f}); {a.src} -> {a.dst}")
    json.dump(res, open(f"{a.dir}/transfer_{a.src}_to_{a.dst}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
