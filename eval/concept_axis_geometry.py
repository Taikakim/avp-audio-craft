#!/usr/bin/env python3
"""concept_axis_geometry.py — per-feature axis + shape via Kim's iso-probability method
(2026-08-01), replacing the crude diff-in-means concept map.

Kim's critique of diff-in-means: mean(high)-mean(low) is confounded (loud clips score high
on many tags at once => spuriously parallel axes), AND my first map compared axes taken at
DIFFERENT recommended layers (incomparable). Fix both:
  - ONE common activation layer (consistent coordinate space for the topology).
  - RIDGE REGRESSION of score on activation = the covariance-corrected gradient axis
    (~ Sigma^-1 (mean_hi - mean_lo)), de-confounding what diff-in-means cannot.
  - CURVATURE (Kim's "shape"): fit the axis separately in low-p vs high-p halves;
    cos(axis_low, axis_high) < 1 => the feature's direction ROTATES across its range =
    a curved manifold, not a straight axis (a single steering vector would drift off it).
  - CV-R2 per feature => which features are even decodable at this layer (honest filter).

150 crops, DiT activations [24,96,1536] + crop_mood_scores.csv. PCA-reduce then ridge.
CPU, seconds. No generation (Kim's point: this is real-clip geometry, not audio pairs).

Run: /home/kim/Projects/SAO/.venv/bin/python eval/concept_axis_geometry.py [--layer 15]
"""
import argparse
import csv
import glob
import json
import os
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_predict

D = Path("/run/media/kim/Mantu/sa3_lora_runs/layer_activations_base")


def load():
    rows = list(csv.DictReader(open(D / "crop_mood_scores.csv")))
    idcol = next(k for k in rows[0] if k.lower() in ("id", "crop", "stem", "crop_id"))
    feats = [k for k in rows[0] if k != idcol and _isnum(rows[0][k])]
    ids, Y = [], []
    for r in rows:
        act = D / f"{r[idcol]}__s50.npy"
        if act.exists():
            ids.append(r[idcol]); Y.append([float(r[f]) for f in feats])
    return ids, np.array(Y), feats


def _isnum(s):
    try:
        float(s); return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", type=int, default=15)   # mid-stack, mood-rich (L8-15 finding)
    ap.add_argument("--pca", type=int, default=48)
    args = ap.parse_args()

    ids, Y, feats = load()
    X = np.stack([np.load(D / f"{i}__s50.npy")[args.layer].mean(0) for i in ids])  # [N,1536]
    N = len(ids)
    print(f"[data] {N} crops, {len(feats)} features, layer {args.layer}, act-dim {X.shape[1]}")

    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xs = (X - mu) / sd
    pca = PCA(n_components=min(args.pca, N - 2)).fit(Xs)
    Xp = pca.transform(Xs)                              # [N, k]

    axes, geom = {}, {}
    for fi, f in enumerate(feats):
        y = Y[:, fi]
        if y.std() < 1e-6:
            continue
        # CV-R2: is this feature decodable at this layer at all?
        pred = cross_val_predict(Ridge(alpha=10.0), Xp, y, cv=5)
        r2 = 1 - ((y - pred) ** 2).sum() / (((y - y.mean()) ** 2).sum() + 1e-9)
        # global axis
        w = Ridge(alpha=10.0).fit(Xp, y).coef_
        ax = pca.components_.T @ w                      # back to 1536
        ax = ax / (np.linalg.norm(ax) + 1e-12)
        # curvature: axis in low-p half vs high-p half
        order = np.argsort(y)
        lo, hi = order[:N // 2], order[N // 2:]
        wl = Ridge(alpha=10.0).fit(Xp[lo], y[lo]).coef_
        wh = Ridge(alpha=10.0).fit(Xp[hi], y[hi]).coef_
        al = pca.components_.T @ wl; ah = pca.components_.T @ wh
        curv = float(np.dot(al, ah) / (np.linalg.norm(al) * np.linalg.norm(ah) + 1e-12))
        axes[f] = ax
        geom[f] = {"cv_r2": round(float(r2), 3), "axis_linearity": round(curv, 3)}

    # keep decodable features for the topology
    good = [f for f in axes if geom[f]["cv_r2"] > 0.15]
    A = np.array([axes[f] for f in good])
    Cm = A @ A.T
    ev = np.clip(np.linalg.eigvalsh(Cm)[::-1], 0, None)
    part = float(ev.sum() ** 2 / (ev ** 2).sum())

    print(f"\n[decodable] {len(good)}/{len(feats)} features CV-R2>0.15 at layer {args.layer}")
    print(f"[effective dim] regression axes: {part:.1f} of {len(good)}  "
          f"(diff-in-means map claimed 3.7/69 — inflated by confounds + cross-layer mixing)")
    lin = sorted(good, key=lambda f: geom[f]["axis_linearity"])
    print("\nMOST CURVED features (axis rotates across its range — NOT a straight steering line):")
    for f in lin[:8]:
        print(f"  linearity {geom[f]['axis_linearity']:+.2f}  R2 {geom[f]['cv_r2']:.2f}  {f}")
    print("MOST LINEAR features (clean straight axis — safe single steering vector):")
    for f in lin[::-1][:8]:
        print(f"  linearity {geom[f]['axis_linearity']:+.2f}  R2 {geom[f]['cv_r2']:.2f}  {f}")

    (D / "concept_axis_geometry.json").write_text(json.dumps(
        {"layer": args.layer, "n_crops": N, "n_decodable": len(good),
         "effective_dim_regression": round(part, 2), "per_feature": geom,
         "method": "Kim iso-probability: ridge-regression gradient axis + low/high-p curvature",
         "note": "supersedes diff-in-means concept_topology (confounded + cross-layer)."},
        indent=1))
    # map
    from sklearn.manifold import MDS
    dist = 1 - Cm; np.fill_diagonal(dist, 0); dist = np.clip((dist + dist.T) / 2, 0, 2)
    xy = MDS(n_components=2, dissimilarity="precomputed", random_state=1,
             normalized_stress="auto").fit_transform(dist)
    fig, ax = plt.subplots(figsize=(11, 9))
    curvs = np.array([geom[f]["axis_linearity"] for f in good])
    sc = ax.scatter(xy[:, 0], xy[:, 1], c=curvs, cmap="RdYlGn", s=60, vmin=0, vmax=1)
    for f, (x, y2) in zip(good, xy):
        ax.annotate(f.replace("mt_", ""), (x, y2), fontsize=7, alpha=0.85)
    plt.colorbar(sc, label="axis linearity (green=straight, red=curved)")
    ax.set_title(f"Concept geometry — Kim's iso-probability method, layer {args.layer}\n"
                 f"{len(good)} decodable axes, effective dim {part:.1f} "
                 f"(regression de-confounds the diff-in-means 3.7)", fontsize=11)
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout(); fig.savefig(D / "concept_axis_geometry_map.png", dpi=130)
    print(f"\nmap -> {D}/concept_axis_geometry_map.png")


if __name__ == "__main__":
    main()
