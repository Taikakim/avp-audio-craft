#!/usr/bin/env python
"""concept_directions.py — diff-in-means concept directions from the DiT layer dumps.

Phase 2 of the concept-direction steering experiment (papers/arxiv-2505.18186.md,
Kim ask 2026-07-11). For every score column in crop_mood_scores.csv and every
(sigma, layer): crop representation = frame-mean of the block output [1536];
direction = mean(top quartile by score) - mean(bottom quartile).

Honesty guards (AxBench spirit — don't ship an overfit direction):
- split-half validation: direction from half A, held-out separation measured on half B
  (AUC of projection top-vs-bottom + Spearman r of projection vs continuous score);
- cross-sigma stability: cosine similarity of the direction across sigma 0.2/0.5/0.8.

Outputs (into the dump dir):
  concept_directions.npz   dirs[feature][sigma] -> [24, 1536] fp32 (FULL-data directions)
  concept_directions.json  per (feature, sigma, layer) held-out AUC/rho + stability +
                           recommended injection layers per feature

CPU-only. Run: SAO/.venv/bin/python eval/concept_directions.py
"""
import csv
import json
from pathlib import Path

import numpy as np

DUMP = Path("/run/media/kim/Mantu/sa3_lora_runs/layer_activations_base")
SIGMAS = ["s20", "s50", "s80"]
Q = 0.25  # quartiles


def load_reps(stems):
    """{sigma: [n_crops, 24, 1536] fp32} — frame-mean of each block output."""
    reps = {}
    for s in SIGMAS:
        acc = [np.load(DUMP / f"{stem}__{s}.npy").astype(np.float32).mean(axis=1)
               for stem in stems]
        reps[s] = np.stack(acc)
    return reps


def auc(pos, neg):
    """Rank AUC of pos vs neg projections."""
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg])))
    return (ranks[:len(pos)].sum() - len(pos) * (len(pos) - 1) / 2) / (len(pos) * len(neg))


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    return float((ra * rb).sum() / (np.sqrt((ra**2).sum() * (rb**2).sum()) + 1e-12))


def dim_direction(X, y):
    """X [n, L, d], y [n] -> dirs [L, d]: top-Q minus bottom-Q class means."""
    lo, hi = np.quantile(y, [Q, 1 - Q])
    top, bot = X[y >= hi], X[y <= lo]
    return top.mean(axis=0) - bot.mean(axis=0)


def main():
    rows = list(csv.DictReader(open(DUMP / "crop_mood_scores.csv")))
    stems = [r["stem"] for r in rows]
    feat_cols = [c for c in rows[0] if c not in ("stem", "source")]
    feats = {c: np.array([float(r[c]) if r[c] != "" else np.nan for r in rows])
             for c in feat_cols}
    print(f"[dirs] {len(stems)} crops, {len(feat_cols)} features", flush=True)
    reps = load_reps(stems)
    n, L, d = reps["s50"].shape

    rng = np.random.default_rng(11)
    report, dirs_out = {}, {}
    for c, y in feats.items():
        ok = ~np.isnan(y)
        if ok.sum() < 40 or np.std(y[ok]) < 1e-9:
            continue
        report[c] = {}
        dirs_out[c] = {}
        for s in SIGMAS:
            X, yy = reps[s][ok], y[ok]
            # split-half held-out validation
            idx = rng.permutation(len(yy))
            A, B = idx[: len(yy) // 2], idx[len(yy) // 2:]
            dA = dim_direction(X[A], yy[A])                     # [L, d]
            u = dA / (np.linalg.norm(dA, axis=1, keepdims=True) + 1e-12)
            proj = np.einsum("nld,ld->nl", X[B], u)             # [nB, L]
            loB, hiB = np.quantile(yy[B], [Q, 1 - Q])
            per_layer = []
            for l in range(L):
                a = auc(proj[yy[B] >= hiB, l], proj[yy[B] <= loB, l])
                rho = spearman(proj[:, l], yy[B])
                per_layer.append({"layer": l, "auc": round(float(a), 3),
                                  "rho": round(rho, 3)})
            report[c][s] = per_layer
            dirs_out[c][s] = dim_direction(X, yy)               # full-data direction
        # cross-sigma stability at each layer (full-data dirs)
        u20 = dirs_out[c]["s20"] / (np.linalg.norm(dirs_out[c]["s20"], axis=1, keepdims=True) + 1e-12)
        u50 = dirs_out[c]["s50"] / (np.linalg.norm(dirs_out[c]["s50"], axis=1, keepdims=True) + 1e-12)
        u80 = dirs_out[c]["s80"] / (np.linalg.norm(dirs_out[c]["s80"], axis=1, keepdims=True) + 1e-12)
        stab = ((u20 * u50).sum(axis=1) + (u50 * u80).sum(axis=1)) / 2
        # recommend: layers ranked by min held-out AUC across sigmas, tie-broken by stability
        min_auc = np.min([[pl["auc"] for pl in report[c][s]] for s in SIGMAS], axis=0)
        rank = np.argsort(-(min_auc + 0.05 * stab))
        report[c]["stability_by_layer"] = [round(float(x), 3) for x in stab]
        report[c]["recommended_layers"] = [int(l) for l in rank[:4]]
        report[c]["best"] = {"layer": int(rank[0]),
                             "min_auc_across_sigma": round(float(min_auc[rank[0]]), 3),
                             "stability": round(float(stab[rank[0]]), 3)}
        print(f"[{c}] best L{rank[0]} min-AUC {min_auc[rank[0]]:.3f} "
              f"stab {stab[rank[0]]:.3f} | top4 {rank[:4].tolist()}", flush=True)

    np.savez(DUMP / "concept_directions.npz",
             **{f"{c}__{s}": dirs_out[c][s] for c in dirs_out for s in SIGMAS})
    (DUMP / "concept_directions.json").write_text(json.dumps(
        {"purpose": "diff-in-means concept directions + held-out validation "
                    "(arxiv-2505.18186 triage; Kim ask 2026-07-11)",
         "n_crops": n, "quartile": Q, "layers": L, "d": d,
         "report": report}, indent=2))
    print(f"[done] -> {DUMP}/concept_directions.npz", flush=True)


if __name__ == "__main__":
    main()
