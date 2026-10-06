#!/usr/bin/env python3
"""H4 baselines for the knob-direction question (C, 2026-10-06; W's condition (a) for a learned g(z)).

Same data as eval/h4_same_directions.py (ladders.npz + latents_same_s.npz: per knob, 50 anchor patches x 8 rungs,
time-mean-pooled 256-d SAME-S vectors m). Two ways to get a knob's edit direction, scored on HELD-OUT anchors
(GroupKFold over anchors, the same patch never in train and test):
  mean   u_k = mean unit(m[last]-m[first]) over the training ladders      (what h4_same_directions.py does)
  ridge  w_k = ridge weights regressing the rung (the knob value, z-scored) on m, POOLED over all training patches
         = the precedent's move (WORKLOG 2026-07-22: pooled multi-timbre ridge decoders untangled pitch from timbre)
For each held-out ladder: identify = which knob's direction its displacement is most cosine-aligned with
(chance 1/4); monotone = Spearman(rung, m . w_k) for the ladder's own knob; and the ridge's held-out R2 on the rung.
USAGE  .venv/bin/python eval/h4_ridge_baseline.py [--dir /run/media/kim/Mantu/surge_200k_models/h4_gate] [--alpha 1]
"""
import argparse
import json
import numpy as np
from scipy.stats import spearmanr

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate"


def unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def features(Z, kind):
    """Per-render feature vector from per-frame latents Z [N,256,T]. mean = the original time-mean; meanstd adds the
    per-channel std over time; temporal adds the last-quarter minus first-quarter mean (a filter/amp sweep shows there)."""
    Z = Z.astype(np.float32)
    m = Z.mean(-1)
    if kind == "mean":
        return m
    q = max(1, Z.shape[-1] // 4)
    parts = [m, Z.std(-1)]
    if kind == "temporal":
        parts.append(Z[..., -q:].mean(-1) - Z[..., :q].mean(-1))
    F = np.concatenate(parts, axis=1)
    return (F - F.mean(0)) / (F.std(0) + 1e-6)             # blocks have different scales; the cosine would follow the loudest one


def ridge_dir(M, y, alpha):
    """Ridge weight vector for y ~ M (both centred); returns (w, mean_M, mean_y)."""
    mu, my = M.mean(0), y.mean()
    X = M - mu
    w = np.linalg.solve(X.T @ X + alpha * np.eye(X.shape[1]) * np.trace(X.T @ X) / X.shape[1], X.T @ (y - my))
    return w, mu, my


def evaluate(M, ax, an, rg, n_axes, alpha=1.0, folds=5, seed=0, val=None):
    """M [N,256] pooled latents; ax/an/rg knob axis, anchor id, rung per row. Returns per-method dict.
    val: optional exact knob value per row (v2 ladders have 8 or 16 rungs, so the rung is not a common scale); it is
    z-scored per axis on the training rows and replaces the rung as the ridge target."""
    anchors = np.unique(an)
    fold_of = dict(zip(np.random.default_rng(seed).permutation(anchors), np.arange(len(anchors)) % folds))
    f = np.array([fold_of[a] for a in an])
    S = int(rg.max()) + 1
    out = {m: {"hit": [], "rho": [], "axis": [], "anchor": []} for m in ("mean", "ridge")}
    r2 = {k: [[], []] for k in range(n_axes)}                      # [sum sq err, sum sq tot] per axis
    for fo in range(folds):
        tr, te = f != fo, f == fo
        W, U, mus, mys = [], [], [], []
        for k in range(n_axes):
            m = tr & (ax == k)
            y = (rg[m] - (S - 1) / 2) / ((S - 1) / 2) if val is None else (val[m] - val[m].mean()) / (val[m].std() + 1e-9)
            w, mu, my = ridge_dir(M[m], y, alpha)
            W.append(unit(w)); mus.append(mu); mys.append(my)
            Dk = []
            for a in np.unique(an[m]):
                i = np.where(m & (an == a))[0]; i = i[np.argsort(rg[i])]
                Dk.append(unit(M[i[-1]] - M[i[0]]))
            U.append(unit(np.mean(Dk, 0)))
            mt = te & (ax == k)
            yt = (rg[mt] - (S - 1) / 2) / ((S - 1) / 2) if val is None else (val[mt] - val[m].mean()) / (val[m].std() + 1e-9)
            pred = (M[mt] - mu) @ w + my
            r2[k][0].append(((pred - yt) ** 2).sum()); r2[k][1].append(((yt - yt.mean()) ** 2).sum())
        W, U = np.array(W), np.array(U)
        for k in range(n_axes):
            for a in np.unique(an[te & (ax == k)]):
                i = np.where(te & (ax == k) & (an == a))[0]; i = i[np.argsort(rg[i])]
                d = unit(M[i[-1]] - M[i[0]])
                for name, V in (("mean", U), ("ridge", W)):
                    out[name]["hit"].append(int(np.argmax(V @ d) == k))
                    out[name]["rho"].append(spearmanr(rg[i], M[i] @ V[k])[0])
                    out[name]["axis"].append(k); out[name]["anchor"].append(int(a))
    res = {}
    for name, o in out.items():
        ax_ = np.array(o["axis"]); hit = np.array(o["hit"]); rho = np.array(o["rho"])
        res[name] = {"ladder_hits": dict(zip(o["anchor"], map(int, hit))) if len(set(o["anchor"])) == len(o["anchor"]) else None,
                     "identify_overall": float(hit.mean()),
                     "per_axis": {int(k): {"identify": float(hit[ax_ == k].mean()),
                                           "monotone_rho": float(np.nanmean(rho[ax_ == k]))} for k in range(n_axes)}}
    res["ridge_heldout_r2"] = {int(k): float(1 - sum(r2[k][0]) / sum(r2[k][1])) for k in range(n_axes)}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--features", choices=["mean", "meanstd", "temporal"], default="mean")
    a = ap.parse_args()
    d = np.load(f"{a.dir}/ladders.npz", allow_pickle=True)
    Z = np.load(f"{a.dir}/latents_same_s.npz")["z"].astype(np.float32)
    M = features(Z, a.features)
    axes = [str(x) for x in d["axes"]]
    res = evaluate(M, d["axis_ids"], d["anchor_ids"], d["rung"], len(axes), alpha=a.alpha)
    res["axes"] = axes
    for k, n in enumerate(axes):
        print(f"{n:12s} identify mean {res['mean']['per_axis'][k]['identify']:.2f} ridge {res['ridge']['per_axis'][k]['identify']:.2f}"
              f" | monotone mean {res['mean']['per_axis'][k]['monotone_rho']:+.2f} ridge {res['ridge']['per_axis'][k]['monotone_rho']:+.2f}"
              f" | ridge held-out R2 {res['ridge_heldout_r2'][k]:+.2f}")
    print(f"features={a.features} dir={a.dir.split('/')[-1]}")
    print(f"overall identify: mean {res['mean']['identify_overall']:.2f}  ridge {res['ridge']['identify_overall']:.2f}  (chance {1/len(axes):.2f})")
    json.dump(res, open(f"{a.dir}/ridge_baseline_{a.features}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
