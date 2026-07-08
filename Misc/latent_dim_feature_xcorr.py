#!/usr/bin/env python3
"""Latent-dim x feature-timeseries correlation over latents_sa3 (CPU, no GPU).

For each SA3 latent channel (256) x each per-frame feature (TIMESERIES.npz companions,
same 4096-frame grid, 1:1 aligned): per-crop Pearson r over frames, aggregated across
crops (mean r, mean |r|). Plus a streaming ridge probe per feature: predict feature[frame]
from ALL 256 channels, held-out-crop R^2 — the frame-resolved encodability number that
predicts whether a LatCH head for that feature has signal to work with.

Usage: python latent_dim_feature_xcorr.py [--n 1000] [--holdout 200] [--out CSV]
"""
import argparse, json, os, random
import numpy as np

LAT_DIR = "/home/kim/Projects/latents_sa3"
SKIP_FIELDS = {"__meta__", "hpcp_ts"}  # hpcp is (T,12); handle separately if ever needed
FRAME_STRIDE = 8  # subsample frames for the ridge accumulation (4096/8 = 512/crop)


def crop_list():
    stems = [f[:-len(".TIMESERIES.npz")] for f in os.listdir(LAT_DIR)
             if f.endswith(".TIMESERIES.npz")]
    return sorted(s for s in stems if os.path.exists(os.path.join(LAT_DIR, s + ".npy")))


def load_crop(stem):
    lat = np.load(os.path.join(LAT_DIR, stem + ".npy")).astype(np.float32)
    lat = lat.reshape(lat.shape[-2], lat.shape[-1])          # (256, T)
    z = np.load(os.path.join(LAT_DIR, stem + ".TIMESERIES.npz"))
    feats = {}
    for k in z.files:
        if k in SKIP_FIELDS:
            continue
        v = z[k].astype(np.float32)
        if v.ndim == 1 and len(v) == lat.shape[1]:
            feats[k] = v
    return lat, feats


def zscore(a, axis=-1):
    m = a.mean(axis=axis, keepdims=True)
    s = a.std(axis=axis, keepdims=True) + 1e-9
    return (a - m) / s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--holdout", type=int, default=200)
    ap.add_argument("--out", default="/home/kim/Projects/mir/stats/latent_dim_feature_xcorr.csv")
    ap.add_argument("--ridge", type=float, default=10.0)
    args = ap.parse_args()

    stems = crop_list()
    random.seed(1); random.shuffle(stems)
    train, hold = stems[:args.n], stems[args.n:args.n + args.holdout]
    print(f"{len(stems)} crops available; using {len(train)} train + {len(hold)} holdout")

    feat_names = None
    r_sum = r_abs_sum = None; n_used = 0
    xtx = None; xty = {}                    # ridge accumulators (frame-level)
    for i, stem in enumerate(train):
        try:
            lat, feats = load_crop(stem)
        except Exception:
            continue
        if feat_names is None:
            feat_names = sorted(feats)
            D = lat.shape[0]
            r_sum = np.zeros((D, len(feat_names))); r_abs_sum = np.zeros_like(r_sum)
            xtx = np.zeros((D + 1, D + 1))
            xty = {f: np.zeros(D + 1) for f in feat_names}
        if any(f not in feats for f in feat_names):
            continue
        lz = zscore(lat)                                     # (D, T)
        F = zscore(np.stack([feats[f] for f in feat_names])) # (K, T)
        r = (lz @ F.T) / lat.shape[1]                        # (D, K) Pearson at lag 0
        r_sum += r; r_abs_sum += np.abs(r); n_used += 1
        # ridge accumulation on subsampled frames (raw z-scored channels + bias)
        Xs = np.concatenate([lz[:, ::FRAME_STRIDE], np.ones((1, lz[:, ::FRAME_STRIDE].shape[1]))]).T
        xtx += Xs.T @ Xs
        for k, f in enumerate(feat_names):
            xty[f] += Xs.T @ F[k, ::FRAME_STRIDE]
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(train)}")

    r_mean = r_sum / n_used; r_abs = r_abs_sum / n_used
    D = r_mean.shape[0]

    # ridge solve + held-out R^2
    w = {}
    A = xtx + args.ridge * np.eye(D + 1)
    for f in feat_names:
        w[f] = np.linalg.solve(A, xty[f])
    ss_res = {f: 0.0 for f in feat_names}; ss_tot = {f: 0.0 for f in feat_names}
    for stem in hold:
        try:
            lat, feats = load_crop(stem)
        except Exception:
            continue
        if any(f not in feats for f in feat_names):
            continue
        lz = zscore(lat)
        X = np.concatenate([lz, np.ones((1, lz.shape[1]))]).T
        for k, f in enumerate(feat_names):
            y = zscore(feats[f][None])[0]
            pred = X @ w[f]
            ss_res[f] += float(((y - pred) ** 2).sum()); ss_tot[f] += float((y ** 2).sum())
    r2 = {f: 1 - ss_res[f] / max(ss_tot[f], 1e-9) for f in feat_names}

    # write full matrix
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fo:
        fo.write("feature,ridge_R2_holdout," + ",".join(f"dim{d}" for d in range(D)) + "\n")
        for k, f in enumerate(feat_names):
            fo.write(f"{f},{r2[f]:.4f}," + ",".join(f"{r_mean[d,k]:.4f}" for d in range(D)) + "\n")

    print(f"\n{n_used} crops in matrix; holdout {len(hold)}. -> {args.out}\n")
    print(f"{'feature':34s} {'ridge R2':>8s}  {'max|r| dim':>10s} {'max|r|':>7s}  top-5 dims by mean|r|")
    order = sorted(range(len(feat_names)), key=lambda k: -r2[feat_names[k]])
    for k in order:
        f = feat_names[k]
        top = np.argsort(-r_abs[:, k])[:5]
        print(f"{f:34s} {r2[f]:8.3f}  {top[0]:10d} {r_abs[top[0],k]:7.3f}  " +
              " ".join(f"{d}({r_abs[d,k]:.2f})" for d in top))


if __name__ == "__main__":
    main()
