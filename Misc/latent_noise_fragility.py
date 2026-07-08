#!/usr/bin/env python3
"""Noise-fragility of feature encodability in the SA3 latent (CPU, no GPU).

Sibling of latent_dim_feature_xcorr.py. Same held-out ridge probe (256 latent
channels -> feature[frame]), but run at several rectified-flow noise levels sigma
so the SAME probe/method measures how readable each feature stays as the forward
noising corrupts the latent. Noising matches C's extract_layer_activations.py:

    x_t = (1 - sigma) * z + sigma * eps ,  eps ~ N(0,1)

Composed with CONTINUITY's DiT layer x feature map (docs/layer-feature-map.md):
  - noise_fragility = R2(sigma=0) - R2(sigma=0.5)   [this script, one method]
  - dit_gain        = peak_block_R2 - block0_R2      [C's map, one method]
Together they partition features into: ENCODED (robust, DiT-flat),
EMERGENT (DiT computes it mid-stack), DEGRADED (in the clean latent, destroyed
by noise, NOT rebuilt -> the mid-band a2a attractor).

Usage: python latent_noise_fragility.py [--sigmas 0,0.2,0.5,0.8] [--n 800] [--holdout 200]
"""
import argparse, os, random
import numpy as np

LAT_DIR = "/home/kim/Projects/latents_sa3"
SKIP_FIELDS = {"__meta__", "hpcp_ts"}
FRAME_STRIDE = 8
EPS_SEED = 7  # match C's extract_layer_activations.py fixed-eps convention


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
    ap.add_argument("--sigmas", default="0,0.2,0.5,0.8")
    ap.add_argument("--n", type=int, default=800)
    ap.add_argument("--holdout", type=int, default=200)
    ap.add_argument("--ridge", type=float, default=10.0)
    ap.add_argument("--out", default="/home/kim/Projects/mir/stats/latent_noise_fragility.csv")
    args = ap.parse_args()
    sigmas = [float(s) for s in args.sigmas.split(",")]

    stems = crop_list()
    random.seed(1); random.shuffle(stems)
    train, hold = stems[:args.n], stems[args.n:args.n + args.holdout]
    print(f"{len(stems)} crops; {len(train)} train + {len(hold)} holdout; sigmas={sigmas}")

    # fixed eps realization (256, T) — drawn once, reused per crop (matches C)
    eps_full = np.random.RandomState(EPS_SEED).randn(256, 4096).astype(np.float32)

    def noise(lat, s):
        if s == 0.0:
            return lat
        return (1.0 - s) * lat + s * eps_full[:, :lat.shape[1]]

    feat_names = None
    # per-sigma ridge accumulators
    xtx = {}; xty = {}
    for i, stem in enumerate(train):
        try:
            lat, feats = load_crop(stem)
        except Exception:
            continue
        if feat_names is None:
            feat_names = sorted(feats)
            D = lat.shape[0]
            for s in sigmas:
                xtx[s] = np.zeros((D + 1, D + 1))
                xty[s] = {f: np.zeros(D + 1) for f in feat_names}
        if any(f not in feats for f in feat_names):
            continue
        F = zscore(np.stack([feats[f] for f in feat_names]))     # (K, T)
        Fs = F[:, ::FRAME_STRIDE]
        for s in sigmas:
            lz = zscore(noise(lat, s))                           # (D, T)
            Xs = np.concatenate([lz[:, ::FRAME_STRIDE],
                                 np.ones((1, Fs.shape[1]))]).T    # (n, D+1)
            xtx[s] += Xs.T @ Xs
            for k, f in enumerate(feat_names):
                xty[s][f] += Xs.T @ Fs[k]
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(train)}")

    D = xtx[sigmas[0]].shape[0] - 1
    # solve + held-out R2 per sigma
    r2 = {s: {} for s in sigmas}
    w = {s: {} for s in sigmas}
    for s in sigmas:
        A = xtx[s] + args.ridge * np.eye(D + 1)
        for f in feat_names:
            w[s][f] = np.linalg.solve(A, xty[s][f])
    ss_res = {s: {f: 0.0 for f in feat_names} for s in sigmas}
    ss_tot = {s: {f: 0.0 for f in feat_names} for s in sigmas}
    for stem in hold:
        try:
            lat, feats = load_crop(stem)
        except Exception:
            continue
        if any(f not in feats for f in feat_names):
            continue
        y = {f: zscore(feats[f][None])[0] for f in feat_names}
        for s in sigmas:
            lz = zscore(noise(lat, s))
            X = np.concatenate([lz, np.ones((1, lz.shape[1]))]).T
            for f in feat_names:
                pred = X @ w[s][f]
                ss_res[s][f] += float(((y[f] - pred) ** 2).sum())
                ss_tot[s][f] += float((y[f] ** 2).sum())
    for s in sigmas:
        for f in feat_names:
            r2[s][f] = 1 - ss_res[s][f] / max(ss_tot[s][f], 1e-9)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fo:
        fo.write("feature," + ",".join(f"R2_s{s}" for s in sigmas) +
                 ",fragility_0_to_0.5\n")
        order = sorted(feat_names, key=lambda f: -r2[sigmas[0]][f])
        for f in order:
            frag = r2[0.0][f] - r2[0.5][f] if 0.0 in r2 and 0.5 in r2 else float("nan")
            fo.write(f"{f}," + ",".join(f"{r2[s][f]:.4f}" for s in sigmas) +
                     f",{frag:.4f}\n")

    print(f"\n-> {args.out}\n")
    hdr = "feature".ljust(30) + "".join(f"  s{str(s):>4}" for s in sigmas) + "   frag(0->.5)"
    print(hdr)
    order = sorted(feat_names, key=lambda f: -r2[sigmas[0]][f])
    for f in order:
        frag = r2[0.0][f] - r2[0.5][f] if (0.0 in r2 and 0.5 in r2) else float("nan")
        print(f"{f:30s}" + "".join(f"  {r2[s][f]:5.2f}" for s in sigmas) + f"   {frag:+.3f}")


if __name__ == "__main__":
    main()
