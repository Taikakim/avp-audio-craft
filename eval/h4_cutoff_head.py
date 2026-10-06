#!/usr/bin/env python3
"""H4: a LatCH-style CUTOFF head on W's v2c ladders, the baseline a learned g(z) must beat (W's message 2026-10-06 23:17).

A small conv head f(z) regresses the cutoff knob value from per-frame SAME-S latents; its gradient df/dz IS a per-z
direction (the same mechanism as steering with a LatCH head). Scored on HELD-OUT patches (one patch per ladder; split by ladder):
  r2        R2 of knob_value on held-out rows
  rho       mean within-ladder Spearman(rung order, f)  (does it order the sweep?)
  dir_cos   mean cosine between the head gradient at the ladder's first rung (time-mean) and the true displacement
            m[last]-m[first]; null = |cos| against other held-out ladders' displacements; pair_consistency_signed = mean signed pair cos, the ceiling for ONE shared vector
  ridge_*   the same numbers for a pooled ridge on time-mean latents (the precedent's baseline), same split
CPU only. USAGE  .venv/bin/python eval/h4_cutoff_head.py [--dir .../h4_gate_v2] [--epochs 15]
"""
import argparse
import json
import numpy as np
import torch
import torch.nn as nn
from scipy.stats import spearmanr

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate_v2"


class Head(nn.Module):
    def __init__(self, c=256, h=128):
        super().__init__()
        self.net = nn.Sequential(nn.Conv1d(c, h, 3, padding=1), nn.GELU(), nn.Conv1d(h, h, 3, padding=1), nn.GELU())
        self.out = nn.Linear(h, 1)

    def forward(self, z):                                    # z [B,256,T] standardised
        return self.out(self.net(z).mean(-1)).squeeze(-1)


def unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def split_ladders(ladder_id, frac=0.2, seed=0):
    ids = np.unique(ladder_id)
    te = set(np.random.default_rng(seed).permutation(ids)[: int(len(ids) * frac)])
    return np.array([l not in te for l in ladder_id]), np.array([l in te for l in ladder_id])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--threads", type=int, default=12)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    torch.manual_seed(0)
    d = np.load(f"{a.dir}/ladders_v2c.npz", allow_pickle=True)
    Z = np.load(f"{a.dir}/ladders_v2c.latents_same_s.npz")["z"].astype(np.float32)        # [N,256,T]
    kv, lid, rung = d["knob_value"].astype(np.float32), d["ladder_id"], d["rung"]
    tr, te = split_ladders(lid)
    mu, sd = Z[tr].mean((0, 2), keepdims=True), Z[tr].std((0, 2), keepdims=True) + 1e-6
    Zs = (Z - mu) / sd
    y = (kv - 0.5) / 0.25
    head = Head()
    opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-2)
    Xtr, ytr = torch.from_numpy(Zs[tr]), torch.from_numpy(y[tr])
    for ep in range(a.epochs):
        perm = torch.randperm(len(Xtr))
        for s in range(0, len(perm), 64):
            i = perm[s:s + 64]
            loss = ((head(Xtr[i]) - ytr[i]) ** 2).mean()
            opt.zero_grad(); loss.backward(); opt.step()
    head.eval()
    with torch.no_grad():
        pred = head(torch.from_numpy(Zs[te])).numpy()
    r2 = 1 - ((pred - y[te]) ** 2).sum() / ((y[te] - y[te].mean()) ** 2).sum()

    M = Z.mean(-1)                                           # raw time-mean, for displacements and the ridge
    Mc = M[tr] - M[tr].mean(0)
    w = np.linalg.solve(Mc.T @ Mc + 1.0 * np.eye(256) * np.trace(Mc.T @ Mc) / 256, Mc.T @ (y[tr] - y[tr].mean()))
    rpred = (M[te] - M[tr].mean(0)) @ w
    rr2 = 1 - ((rpred - (y[te] - y[tr].mean())) ** 2).sum() / ((y[te] - y[te].mean()) ** 2).sum()

    rhos, rrhos, cos_h, cos_r, D = [], [], [], [], []
    te_ids = np.unique(lid[te])
    for l in te_ids:
        i = np.where(lid == l)[0]; i = i[np.argsort(rung[i])]
        D.append(M[i[-1]] - M[i[0]])
    D = unit(np.array(D))
    for n, l in enumerate(te_ids):
        i = np.where(lid == l)[0]; i = i[np.argsort(rung[i])]
        with torch.no_grad():
            f = head(torch.from_numpy(Zs[i])).numpy()
        rhos.append(spearmanr(rung[i], f)[0]); rrhos.append(spearmanr(rung[i], M[i] @ w)[0])
        x = torch.from_numpy(Zs[i[0]][None]).requires_grad_(True)
        head(x).sum().backward()
        g = (x.grad[0] / torch.from_numpy(sd[0])).mean(-1).numpy()                 # d f / d z_raw, time-mean
        cos_h.append(float(unit(g) @ D[n])); cos_r.append(float(unit(w) @ D[n]))
    other = [float(np.mean([abs(D[(n + k) % len(D)] @ D[n]) for k in range(1, 6)])) for n in range(len(D))]
    res = {"n_train_ladders": int(len(np.unique(lid[tr]))), "n_test_ladders": int(len(te_ids)),
           "head": {"r2": float(r2), "rho": float(np.nanmean(rhos)), "dir_cos": float(np.mean(cos_h))},
           "ridge": {"r2": float(rr2), "rho": float(np.nanmean(rrhos)), "dir_cos": float(np.mean(cos_r))},
           "null_abs_cos_other_ladder_displacement": float(np.mean(other)),
           "pair_consistency_signed": float((D @ D.T)[~np.eye(len(D), dtype=bool)].mean())}
    print(json.dumps(res, indent=1))
    json.dump(res, open(f"{a.dir}/cutoff_head_baseline.json", "w"), indent=1)


if __name__ == "__main__":
    main()
