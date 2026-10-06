#!/usr/bin/env python3
"""H4 v2: is each knob READABLE from per-frame SAME-S latents by a small nonlinear head? (C, 2026-10-06)
One conv head per knob (eval/h4_cutoff_head.Head), regressing the exact knob value, 4-fold leave-ARCHETYPES-out CV (W: 16 base presets repeat), CPU.
Reports held-out R2 and mean within-ladder Spearman, next to a pooled ridge on temporal features (same split).
A knob at chance for BOTH is not in the latent; one the head reads and the ridge does not is the case for a learned map.
USAGE  .venv/bin/python eval/h4_v2_heads.py [--epochs 12] [--dir ...]
"""
import argparse
import json
import os
import sys
import numpy as np
import torch
from scipy.stats import spearmanr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h4_cutoff_head import Head  # noqa: E402
from h4_ridge_baseline import archetype_folds, features  # noqa: E402

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate_v2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--threads", type=int, default=12)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    d = np.load(f"{a.dir}/ladders_v2.npz", allow_pickle=True)
    Z = np.load(f"{a.dir}/ladders_v2.latents_same_s.npz")["z"].astype(np.float32)
    F = features(Z, "temporal")
    knobs = [str(k) for k in d["knobs"]]
    fold_all, _ = archetype_folds(a.dir, "ladders_v2", d["ladder_id"])
    out = {}
    for k, name in enumerate(knobs):
        m = d["knob_id"] == k
        z, f, kv, lid, rung, fo = Z[m], F[m], d["knob_value"][m].astype(np.float32), d["ladder_id"][m], d["rung"][m], fold_all[m]
        P, RP, Y, YR = np.zeros(len(kv)), np.zeros(len(kv)), np.zeros(len(kv)), np.zeros(len(kv))
        for fi in range(int(fold_all.max()) + 1):
            torch.manual_seed(fi)
            tr, te = fo != fi, fo == fi
            y = (kv - kv[tr].mean()) / (kv[tr].std() + 1e-9)
            mu, sd = z[tr].mean((0, 2), keepdims=True), z[tr].std((0, 2), keepdims=True) + 1e-6
            zs = torch.from_numpy((z - mu) / sd)
            head = Head(); opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-2)
            Xtr, ytr = zs[tr], torch.from_numpy(y[tr])
            for _ in range(a.epochs):
                perm = torch.randperm(len(Xtr))
                for s_ in range(0, len(perm), 64):
                    i = perm[s_:s_ + 64]
                    loss = ((head(Xtr[i]) - ytr[i]) ** 2).mean(); opt.zero_grad(); loss.backward(); opt.step()
            head.eval()
            with torch.no_grad():
                P[te] = head(zs[te]).numpy()
            Fc = f[tr] - f[tr].mean(0)
            w = np.linalg.solve(Fc.T @ Fc + np.eye(Fc.shape[1]) * np.trace(Fc.T @ Fc) / Fc.shape[1], Fc.T @ (y[tr] - y[tr].mean()))
            RP[te] = (f[te] - f[tr].mean(0)) @ w + y[tr].mean()
            Y[te] = y[te]
        r2 = lambda p_: 1 - ((p_ - Y) ** 2).sum() / ((Y - Y.mean()) ** 2).sum()
        rho = lambda pred: float(np.nanmean([spearmanr(rung[lid == l], pred[lid == l])[0] for l in np.unique(lid)]))
        r2, rr2, p, rp = r2(P), r2(RP), P, RP
        out[name] = {"head_r2": float(r2), "head_rho": rho(p), "ridge_r2": float(rr2), "ridge_rho": rho(rp)}
        print(f"{name:11s} head R2 {r2:+.2f} rho {out[name]['head_rho']:+.2f} | ridge R2 {rr2:+.2f} rho {out[name]['ridge_rho']:+.2f}", flush=True)
    json.dump(out, open(f"{a.dir}/knob_heads.json", "w"), indent=1)


if __name__ == "__main__":
    main()
