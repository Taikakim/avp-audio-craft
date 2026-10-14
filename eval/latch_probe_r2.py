#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-14)
"""latch_probe_r2.py -- is this LatCH target even LINEARLY readable from the SA3 latent? (CPU only, run BEFORE spending GPU on a head)

WHY (Kim 2026-10-14: "if we were comparing cake recipes it would not help to have sugar, eggs, flour and nails as the training ingredients").
MASTER s5 records that probe R^2 predicts per-head control. latch/latch_probe_encodability.py did this for the retired SAO-Small latents
(points at Lehto/latents); this is the SA3 / bigset version, per FRAME, since the heads are per-frame regressors.

For each target field in the crops' .TIMESERIES.npz (default: onset_per_beat_ts onset_envelope_ts) it fits ridge  z_t (+ window mean) -> target_t
on a track-grouped split (no track in both halves) and reports held-out R^2 and Pearson r. Two controls print next to every number so it can be
audited rather than believed (AUDIT-THE-INSTRUMENT rule):
  * perm : the same fit with the TRAIN targets shuffled across frames -> must be ~0, else the pipeline leaks;
  * mean : R^2 of always guessing the train mean is 0 by construction (so R^2 is already 'gain over the trivial baseline').
Clip-level scalars (bpm_madmom, onset_density, onset_per_beat) are probed from time-pooled mean+std of the latent.

RUN (any venv with numpy; no torch/GPU):
    /home/kim/Projects/SAO/.venv/bin/python eval/latch_probe_r2.py --latent-dir /run/media/kim/Kosmos/latents_goa_bigset --n 1200
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

SCALARS = ("bpm_madmom", "onset_density", "onset_per_beat")


def ridge_fit(X, y, lam):
    A = X.T @ X
    A[np.diag_indices_from(A)] += lam * len(X)
    return np.linalg.solve(A, X.T @ y)


def r2_r(y, p):
    sst = float(((y - y.mean()) ** 2).sum())
    return (1.0 - float(((y - p) ** 2).sum()) / max(sst, 1e-12), float(np.corrcoef(y, p)[0, 1]) if p.std() > 0 and y.std() > 0 else 0.0)


def window_mean(z, w):
    c = np.cumsum(np.pad(z, ((0, 0), (1, 0))), axis=1)
    T = z.shape[1]
    lo = np.clip(np.arange(T) - w, 0, T)
    hi = np.clip(np.arange(T) + w + 1, 0, T)
    return (c[:, hi] - c[:, lo]) / (hi - lo)


def load(latent_dir, n, fields, stride, win, seed):
    npys = sorted(glob.glob(os.path.join(latent_dir, "*.npy")))
    rng = np.random.default_rng(seed)
    rng.shuffle(npys)
    rows = {"X": [], "Y": {f: [] for f in fields}, "g": [], "pool": [], "sc": {s: [] for s in SCALARS}, "pg": []}
    for p in npys:
        base = p[:-4]
        if not (os.path.exists(base + ".TIMESERIES.npz") and os.path.exists(base + ".json")):
            continue
        z = np.load(p).astype(np.float32)                       # (256, T)
        ts = np.load(base + ".TIMESERIES.npz")
        if any(f not in ts.files for f in fields):
            continue
        valid = ts["valid_ts"] > 0.5
        grp = json.load(open(base + ".json")).get("relpath", os.path.basename(base))
        feats = np.concatenate([z, window_mean(z, win)], 0)      # (512, T)
        idx = np.where(valid)[0][::stride]
        if len(idx) < 8:
            continue
        rows["X"].append(feats[:, idx].T)
        for f in fields:
            rows["Y"][f].append(ts[f][idx])
        rows["g"] += [grp] * len(idx)
        vz = z[:, valid]
        rows["pool"].append(np.concatenate([vz.mean(1), vz.std(1)]))
        for s in SCALARS:
            rows["sc"][s].append(float(ts[s]) if s in ts.files else np.nan)
        rows["pg"].append(grp)
        if len(rows["pool"]) >= n:
            break
    return rows


def split_groups(groups, frac, seed):
    u = sorted(set(groups))
    rng = np.random.default_rng(seed)
    rng.shuffle(u)
    val = set(u[: max(1, int(len(u) * frac))])
    return np.array([g in val for g in groups])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latent-dir", default="/run/media/kim/Kosmos/latents_goa_bigset")
    ap.add_argument("--fields", nargs="+", default=["onset_per_beat_ts", "onset_envelope_ts"])
    ap.add_argument("--n", type=int, default=1200, help="crops to read")
    ap.add_argument("--stride", type=int, default=16, help="frame stride (decorrelates neighbours)")
    ap.add_argument("--win", type=int, default=8, help="half-width (frames) of the context mean (8 ~ 0.75 s)")
    ap.add_argument("--lam", type=float, default=1e-2)
    ap.add_argument("--val-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None, help="write the table as JSON")
    a = ap.parse_args()
    R = load(a.latent_dir, a.n, a.fields, a.stride, a.win, a.seed)
    if not R["X"]:
        sys.exit("no usable crops (is the drive mounted? are .TIMESERIES.npz present?)")
    X = np.concatenate(R["X"])
    isv = split_groups(R["g"], a.val_frac, a.seed)
    mu, sd = X[~isv].mean(0), X[~isv].std(0) + 1e-6
    Xn = (X - mu) / sd
    rng = np.random.default_rng(a.seed + 1)
    out = {"n_crops": len(R["pool"]), "n_frames": int(len(X)), "n_val_frames": int(isv.sum()), "frame": {}, "clip": {}}
    print(f"{out['n_crops']} crops, {out['n_frames']} frames ({out['n_val_frames']} held-out, track-grouped)")
    print(f"{'target':24s} {'R2':>7s} {'r':>7s} {'R2 perm':>8s}")
    for f in a.fields:
        y = np.concatenate(R["Y"][f]).astype(np.float64)
        ok = np.isfinite(y)
        tr, va = ~isv & ok, isv & ok
        ym = y[tr].mean()
        w = ridge_fit(Xn[tr], y[tr] - ym, a.lam)
        r2, r = r2_r(y[va], Xn[va] @ w + ym)
        wp = ridge_fit(Xn[tr], rng.permutation(y[tr]) - ym, a.lam)
        r2p, _ = r2_r(y[va], Xn[va] @ wp + ym)
        out["frame"][f] = {"r2": r2, "r": r, "r2_perm": r2p}
        print(f"{f:24s} {r2:7.3f} {r:7.3f} {r2p:8.3f}")
    P = np.stack(R["pool"])
    pv = split_groups(R["pg"], a.val_frac, a.seed)
    Pm, Ps = P[~pv].mean(0), P[~pv].std(0) + 1e-6
    Pn = (P - Pm) / Ps
    for s in SCALARS:
        y = np.array(R["sc"][s], dtype=np.float64)
        ok = np.isfinite(y)
        tr, va = ~pv & ok, pv & ok
        if tr.sum() < 20 or va.sum() < 5:
            continue
        ym = y[tr].mean()
        w = ridge_fit(Pn[tr], y[tr] - ym, 1.0)
        r2, r = r2_r(y[va], Pn[va] @ w + ym)
        wp = ridge_fit(Pn[tr], rng.permutation(y[tr]) - ym, 1.0)
        r2p, _ = r2_r(y[va], Pn[va] @ wp + ym)
        out["clip"][s] = {"r2": r2, "r": r, "r2_perm": r2p, "n_val": int(va.sum())}
        print(f"clip:{s:19s} {r2:7.3f} {r:7.3f} {r2p:8.3f}")
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
