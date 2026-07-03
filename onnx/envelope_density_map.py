"""Corpus envelope<->density mapping for the composed control x LatCH sweep.

Spec: docs/superpowers/specs/2026-07-03-composed-control-latch-sweep.md (guidance
configuration). The onset_envelope LatCH head needs a CONSTANT raw target per
requested density; this module freezes that mapping from the corpus:
E[mean(onset_envelope_ts) | onset_density] via quantile-binned means +
piecewise-linear interpolation, edge-slope extrapolated beyond corpus support
(the grid's density-12 cells are outside support by design — the ceiling probe).
Standardization to the head's output space happens downstream in
``sa3_latch_onnx.make_latch_target`` — this module speaks RAW envelope units.

CLI (numpy-only, any venv):
    python3 onnx/envelope_density_map.py \
        --corpus /home/kim/Projects/latents_sa3 --out onnx/envelope_density_map.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os

import numpy as np


def fit_envelope_density(xs, ys, n_bins: int = 12) -> dict:
    """Quantile-bin xs (density), record mean ys (raw envelope mean) per bin.

    Returns a plain-JSON-serializable dict: bin centers/means, corpus support,
    and a global linear fit (reference only; interp uses the bins).
    """
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    edges = np.quantile(xs, np.linspace(0.0, 1.0, n_bins + 1))
    centers, means, counts = [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (xs >= lo) & (xs <= hi if hi == edges[-1] else xs < hi)
        if not sel.any():
            continue
        centers.append(float(xs[sel].mean()))
        means.append(float(ys[sel].mean()))
        counts.append(int(sel.sum()))
    a, b = np.polyfit(xs, ys, 1)
    pred = a * xs + b
    r2 = float(1.0 - ((ys - pred) ** 2).sum() / (((ys - ys.mean()) ** 2).sum() + 1e-12))
    return {
        "bin_centers": centers,
        "bin_means": means,
        "bin_counts": counts,
        "support": [float(xs.min()), float(xs.max())],
        "linear": {"a": float(a), "b": float(b), "r2": r2},
        "n": int(len(xs)),
    }


def density_to_env(d: float, fit: dict, return_in_support: bool = False):
    """Requested density -> raw envelope target. Piecewise-linear over bin means;
    beyond the outermost bin centers, continue the edge segment's slope."""
    c = np.asarray(fit["bin_centers"], dtype=np.float64)
    m = np.asarray(fit["bin_means"], dtype=np.float64)
    d = float(d)
    if d <= c[0]:
        slope = (m[1] - m[0]) / (c[1] - c[0])
        v = m[0] + slope * (d - c[0])
    elif d >= c[-1]:
        slope = (m[-1] - m[-2]) / (c[-1] - c[-2])
        v = m[-1] + slope * (d - c[-1])
    else:
        v = float(np.interp(d, c, m))
    lo, hi = fit["support"]
    in_support = bool(lo <= d <= hi)
    return (float(v), in_support) if return_in_support else float(v)


def scan_corpus(corpus_dir: str, ts_field: str = "onset_envelope_ts",
                json_field: str = "onset_density"):
    """Collect (density, mean envelope) pairs from <crop>.TIMESERIES.npz + <crop>.json."""
    xs, ys = [], []
    for p in sorted(glob.glob(os.path.join(corpus_dir, "*.TIMESERIES.npz"))):
        jp = p.replace(".TIMESERIES.npz", ".json")
        if not os.path.exists(jp):
            continue
        try:
            meta = json.load(open(jp))
            if json_field not in meta:
                continue
            env = np.load(p)[ts_field]
        except Exception:
            continue
        xs.append(float(meta[json_field]))
        ys.append(float(np.asarray(env, dtype=np.float64).mean()))
    return np.array(xs), np.array(ys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="/home/kim/Projects/latents_sa3")
    ap.add_argument("--out", default="onnx/envelope_density_map.json")
    ap.add_argument("--n-bins", type=int, default=12)
    args = ap.parse_args()
    xs, ys = scan_corpus(args.corpus)
    fit = fit_envelope_density(xs, ys, n_bins=args.n_bins)
    fit["provenance"] = {"corpus": args.corpus, "ts_field": "onset_envelope_ts",
                         "json_field": "onset_density"}
    with open(args.out, "w") as f:
        json.dump(fit, f, indent=1)
    print(f"[fit] n={fit['n']}  support={fit['support']}  "
          f"linear a={fit['linear']['a']:.5f} b={fit['linear']['b']:.5f} "
          f"R2={fit['linear']['r2']:.3f} -> {args.out}")
    for d in (1, 3, 5, 6, 7, 7.5, 8, 9, 12):
        v, ok = density_to_env(d, fit, return_in_support=True)
        print(f"  density {d:>4} -> env {v:.4f}{'' if ok else '  (EXTRAPOLATED)'}")


if __name__ == "__main__":
    main()
