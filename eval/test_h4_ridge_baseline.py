"""h4_ridge_baseline: on synthetic ladders with a planted per-knob direction both methods must find it (and a shuffled-axis control must not)."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h4_ridge_baseline import evaluate


def make(n_axes=3, n_anchor=30, S=8, dim=32, noise=0.05, seed=0):
    rng = np.random.default_rng(seed)
    dirs = np.linalg.qr(rng.standard_normal((dim, n_axes)))[0].T           # orthonormal planted directions
    M, ax, an, rg = [], [], [], []
    for a in range(n_anchor):
        base = rng.standard_normal(dim)
        for k in range(n_axes):
            for r in range(S):
                M.append(base + dirs[k] * (r - 3.5) + noise * rng.standard_normal(dim)); ax.append(k); an.append(a); rg.append(r)
    return np.array(M), np.array(ax), np.array(an), np.array(rg)


def test_planted_directions_are_found_on_held_out_anchors():
    M, ax, an, rg = make()
    res = evaluate(M, ax, an, rg, 3)
    assert res["mean"]["identify_overall"] > 0.95 and res["ridge"]["identify_overall"] > 0.95
    # ceiling ~0.84: the per-patch offset projects onto w and a pooled readout cannot know it
    assert all(v > 0.7 for v in res["ridge_heldout_r2"].values())


def test_shuffled_knob_labels_fall_to_chance():
    M, ax, an, rg = make()
    rng = np.random.default_rng(1)
    ax2 = ax.copy()
    for a in np.unique(an):                                                  # relabel the knobs per anchor
        m = an == a; perm = rng.permutation(3); ax2[m] = perm[ax[m]]
    res = evaluate(M, ax2, an, rg, 3)
    assert res["ridge"]["identify_overall"] < 0.6
