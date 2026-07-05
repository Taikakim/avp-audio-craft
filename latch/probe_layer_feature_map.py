"""Layer x feature encodability map for the SA3 DiT.

Answers "which layer's per-frame activations encode which audio feature" — the
representational map behind Kim's cross-correlation idea, and the target-conditioned
LOCALIZER the relevance-routed-DoRA paradigm needs (W's rigor note). Extends the
time-POOLED probe in latch_probe_encodability.py to keep the frame axis.

The feature side is free: every crop's TIMESERIES.npz already holds 21 per-frame
features at 4096 frames — the SAME grid as the latent tokens — so activation[layer,
frame] and feature[frame] align 1:1 with no resampling.

CPU analysis (load_features / frame_probe_r2 / lagged_xcorr / build_feature_map)
is tested in test_probe_layer_feature_map.py. GPU activation extraction
(extract_activations) is the only piece that needs the card — deferred behind the
training/eval queue; the rest runs now against synthetic or pre-extracted acts.
"""
from __future__ import annotations

import numpy as np

# The per-frame features worth probing (keys in the TIMESERIES.npz). hpcp is the
# harmonic/melodic one (12-d chroma) — the one that answers "where does melody live".
FEATURE_NAMES = [
    "onset_envelope_ts", "onset_envelope_drums_ts", "onset_envelope_bass_ts",
    "rms_energy_bass_ts", "rms_energy_body_ts", "rms_energy_mid_ts", "rms_energy_air_ts",
    "spectral_flatness_ts", "spectral_flux_ts", "spectral_skewness_ts",
    "hpcp_ts", "beat_activation_ts", "downbeat_activation_ts",
]


# ------------------------------------------------------------------ features

def load_features(npz_path, names=FEATURE_NAMES, n_frames=None):
    """name -> [T] (scalar) or [T, k] (vector, e.g. hpcp). Only requested names
    present in the file; optionally truncated to the first n_frames."""
    out = {}
    with np.load(npz_path) as d:
        for nm in names:
            if nm in d.files:
                a = np.asarray(d[nm], dtype=float)
                out[nm] = a[:n_frames] if n_frames is not None else a
    return out


# ------------------------------------------------------------------ probing

def frame_probe_r2(X, y, n_splits=3, lam=10.0):
    """Held-out R^2 of a ridge probe from per-frame activations X [N, d] to a
    per-frame feature y [N] or [N, k]. Standardizes X (fit on train only).
    Vector y -> mean R^2 across outputs. Constant y -> 0.0 (never NaN)."""
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.model_selection import KFold
    from sklearn.metrics import r2_score

    X = np.asarray(X, dtype=float)
    Y = np.asarray(y, dtype=float)
    if Y.ndim == 1:
        Y = Y[:, None]
    if np.all(Y.std(axis=0) < 1e-9):          # zero-variance target
        return 0.0

    kf = KFold(n_splits=n_splits, shuffle=True, random_state=0)
    scores = []
    for tr, te in kf.split(X):
        model = make_pipeline(StandardScaler(), Ridge(alpha=lam))
        model.fit(X[tr], Y[tr])
        pred = model.predict(X[te])
        scores.append(r2_score(Y[te], pred, multioutput="uniform_average"))
    return float(np.mean(scores))


def lagged_xcorr(a, b, max_lag):
    """Signed Pearson cross-correlation of two per-frame series over integer
    lags in [-max_lag, max_lag] (non-circular overlap). Returns (best_lag,
    corr_at_best) where best is by |corr|. Convention: b = roll(a, k) -> lag k
    (b lags a by k). Cheap first-pass complement to the ridge map."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = len(a)
    best_lag, best_r = 0, 0.0
    for L in range(-max_lag, max_lag + 1):
        if L >= 0:
            x, y = a[: n - L] if L > 0 else a, b[L:]
        else:
            x, y = a[-L:], b[: n + L]
        if len(x) < 3:
            continue
        xc, yc = x - x.mean(), y - y.mean()
        denom = np.sqrt((xc ** 2).sum() * (yc ** 2).sum())
        if denom == 0:
            continue
        r = float((xc * yc).sum() / denom)
        if abs(r) > abs(best_r):
            best_lag, best_r = L, r
    return best_lag, best_r


def pool_frames(clips):
    """clips: list of [L, T, d] activation arrays -> list of L arrays each
    [sum_T, d] (all clips' frames concatenated per layer)."""
    n_layers = clips[0].shape[0]
    return [np.concatenate([c[l] for c in clips], axis=0) for l in range(n_layers)]


def build_feature_map(acts_by_layer, feats, n_splits=3, lam=10.0):
    """acts_by_layer: list of [N, d] (frames pooled across clips); feats: name ->
    [N] or [N, k]. Returns {r2: [L, F], features: [names], best_layer: {feat:layer},
    n_layers}. r2[l, f] = how linearly feature f is decodable from layer l."""
    names = list(feats)
    n_layers = len(acts_by_layer)
    R2 = np.zeros((n_layers, len(names)))
    for li, A in enumerate(acts_by_layer):
        for fi, nm in enumerate(names):
            R2[li, fi] = frame_probe_r2(A, feats[nm], n_splits=n_splits, lam=lam)
    best = {nm: int(np.argmax(R2[:, fi])) for fi, nm in enumerate(names)}
    return {"r2": R2, "features": names, "n_layers": n_layers, "best_layer": best}


# ------------------------------------------------------------------ GPU extraction (deferred)

def extract_activations(sam, latent, timestep_sigmas, conditioning, block_reduce=None):
    """GPU-SIDE, DEFERRED — needs the card + verification against model.py's DiT
    forward before first run. Registers forward hooks on the DiT transformer
    blocks (ContinuousTransformer.layers, the `layers.N` sites), runs the denoiser
    at each requested sigma, and returns activations [n_layers, n_frames, d_model]
    (optionally per requested timestep). block_reduce, if given, maps a block's
    [T, d] output to a lower-dim [T, d'] on the fly to keep memory bounded (raw is
    ~11GB for 150 clips; reduce to norm or a PCA basis at extraction time).

    Contract only — the CPU analysis above consumes the returned array (or a
    pre-extracted .npz). Left unimplemented so the tested scaffold ships without
    a GPU dependency; wire the hooks when the eval/train queue frees the card.
    """
    raise NotImplementedError(
        "GPU activation extraction is deferred; hook ContinuousTransformer.layers "
        "and capture per-block outputs during the denoise loop. See docstring.")


# ------------------------------------------------------------------ driver

def run_map(activations_npz, timeseries_paths, feature_names=FEATURE_NAMES,
            n_frames=None, out_json=None):
    """Build the map from pre-extracted activations + the clips' TIMESERIES.
    activations_npz: file with 'acts' [n_clips, n_layers, T, d] (or reduced d).
    timeseries_paths: parallel list of TIMESERIES.npz paths (same clip order)."""
    import json
    A = np.load(activations_npz)["acts"]                       # [C, L, T, d]
    n_clips = A.shape[0]
    pooled = pool_frames([A[i] for i in range(n_clips)])       # list[L] of [C*T, d]

    # stack each feature across clips, frame-aligned to the pooled activation frames
    feats = {}
    for nm in feature_names:
        cols = []
        for p in timeseries_paths:
            f = load_features(p, names=[nm], n_frames=n_frames)
            if nm in f:
                cols.append(f[nm])
        if cols:
            feats[nm] = np.concatenate(cols, axis=0)
    out = build_feature_map(pooled, feats)
    if out_json:
        json.dump({"r2": out["r2"].tolist(), "features": out["features"],
                   "best_layer": out["best_layer"], "n_layers": out["n_layers"]},
                  open(out_json, "w"), indent=1)
    return out


def print_map(out):
    """Readable dump: R^2 grid + which layer maxes each feature."""
    R2, names = out["r2"], out["features"]
    print(f"layer x feature encodability (R^2), {out['n_layers']} layers\n")
    hdr = "layer " + " ".join(f"{n[:10]:>10}" for n in names)
    print(hdr)
    for l in range(out["n_layers"]):
        print(f"{l:5d} " + " ".join(f"{R2[l, f]:10.3f}" for f in range(len(names))))
    print("\nbest layer per feature:")
    for nm in names:
        print(f"  {nm:26s} -> layer {out['best_layer'][nm]}  (R^2 {R2[out['best_layer'][nm], names.index(nm)]:.3f})")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--activations", required=True, help=".npz with 'acts' [C,L,T,d]")
    ap.add_argument("--timeseries", nargs="+", required=True, help="TIMESERIES.npz per clip (same order)")
    ap.add_argument("--n-frames", type=int, default=None)
    ap.add_argument("--out", default=None, help="write the map to this JSON")
    args = ap.parse_args()
    out = run_map(args.activations, args.timeseries, n_frames=args.n_frames, out_json=args.out)
    print_map(out)
