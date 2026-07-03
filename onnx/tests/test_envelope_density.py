"""Tests for the corpus envelope<->density mapping (composed sweep, step 1).

The sweep's guidance target for "requested density d" is the corpus-expected mean
onset_envelope value at that density: E[env_mean | density=d]. Fit = binned means +
piecewise-linear interp, edge-slope extrapolation beyond corpus support (density 12
is outside support by design — the ceiling probe).

Run: python3 -m pytest onnx/tests/test_envelope_density.py -q  (from SAO root, PYTHONPATH=onnx)
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from envelope_density_map import fit_envelope_density, density_to_env  # noqa: E402


def _synthetic(n=2000, a=0.1, b=0.5, noise=0.05, seed=0):
    rng = np.random.default_rng(seed)
    xs = rng.uniform(1.0, 10.0, n)
    ys = a * xs + b + rng.normal(0, noise, n)
    return xs, ys


def test_fit_recovers_linear_relationship():
    xs, ys = _synthetic()
    fit = fit_envelope_density(xs, ys, n_bins=10)
    for d in (2.0, 5.0, 8.0):
        assert abs(density_to_env(d, fit) - (0.1 * d + 0.5)) < 0.02, d


def test_fit_reports_support_and_flags_extrapolation():
    xs, ys = _synthetic()
    fit = fit_envelope_density(xs, ys, n_bins=10)
    lo, hi = fit["support"]
    assert 0.9 < lo < 1.5 and 9.5 < hi < 10.1
    # density 12 is beyond support: still returns a value (edge-slope extrapolation,
    # continuing the linear trend), and in_support says so
    v, ok = density_to_env(12.0, fit, return_in_support=True)
    assert not ok
    assert abs(v - (0.1 * 12.0 + 0.5)) < 0.1
    v5, ok5 = density_to_env(5.0, fit, return_in_support=True)
    assert ok5 and abs(v5 - 1.0) < 0.02


def test_interp_is_monotone_when_bin_means_are():
    xs, ys = _synthetic()
    fit = fit_envelope_density(xs, ys, n_bins=10)
    grid = [density_to_env(d, fit) for d in np.linspace(1.0, 12.0, 40)]
    assert all(b >= a for a, b in zip(grid, grid[1:]))


def test_fit_serializes_to_plain_json_types():
    import json
    xs, ys = _synthetic(n=500)
    fit = fit_envelope_density(xs, ys, n_bins=6)
    rt = json.loads(json.dumps(fit))
    assert abs(density_to_env(5.0, rt) - density_to_env(5.0, fit)) < 1e-12
