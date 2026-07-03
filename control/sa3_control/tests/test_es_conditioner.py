# tests/test_es_conditioner.py — pure-numpy core of the echo-location ES (#2 in
# docs/superpowers/specs/2026-07-02-perceptual-signal-optimizer-directions.md).
import numpy as np

from sa3_control.es_conditioner import (
    pack_params, unpack_params, centered_ranks, es_step, control_tokens_np,
    DEFAULT_EVOLVED_KEYS,
)


def _fake_cond(nt=4, cd=8, hidden=16):
    rng = np.random.default_rng(0)
    return {
        "tokens": rng.standard_normal((nt, cd)).astype(np.float32),
        "film0_w": rng.standard_normal((hidden, 1)).astype(np.float32),
        "film0_b": rng.standard_normal(hidden).astype(np.float32),
        "film2_w": rng.standard_normal((nt * cd * 2, hidden)).astype(np.float32),
        "film2_b": rng.standard_normal(nt * cd * 2).astype(np.float32),
        "mean": np.float32(7.0), "std": np.float32(1.4),
        "n_tokens": np.int64(nt), "control_dim": np.int64(cd),
    }


def test_pack_unpack_roundtrip():
    cond = _fake_cond()
    vec = pack_params(cond, DEFAULT_EVOLVED_KEYS)
    cond2 = unpack_params(vec + 1.0, cond, DEFAULT_EVOLVED_KEYS)
    # evolved keys shifted by exactly 1, frozen keys untouched, originals unmutated
    for k in DEFAULT_EVOLVED_KEYS:
        assert np.allclose(cond2[k], cond[k] + 1.0), k
    assert np.allclose(cond2["film2_w"], cond["film2_w"])
    assert np.allclose(pack_params(cond, DEFAULT_EVOLVED_KEYS), vec)  # no mutation


def test_tokens_forward_matches_reference():
    """control_tokens_np must equal the shipped numpy conditioner (sa3_control_onnx)."""
    import sys
    sys.path.insert(0, "/home/kim/Projects/SAO/onnx")
    from sa3_control_onnx import control_tokens_from_npz
    cond = _fake_cond()
    for val in (3.0, 7.0, 12.0):
        ours = control_tokens_np(cond, val)
        ref = control_tokens_from_npz(cond, val)
        assert ours.shape == ref.shape == (1, 4, 8)
        assert np.allclose(ours, ref, atol=1e-5), float(np.abs(ours - ref).max())


def test_centered_ranks_properties():
    r = centered_ranks(np.array([10.0, -5.0, 3.0, 0.0]))
    assert abs(r.sum()) < 1e-6                      # zero-sum (fp32)
    assert r.max() == -r.min()                      # symmetric
    assert r[np.argmax([10.0, -5.0, 3.0, 0.0])] == r.max()  # best fitness -> top rank


def test_anchored_weight_decay_pulls_toward_anchor_not_zero():
    """AWD (arXiv:2605.30148): with flat fitness, decay must pull toward the trained
    init, not toward zero."""
    from sa3_control.es_conditioner import es_step
    rng = np.random.default_rng(0)
    anchor = np.full(32, 5.0, np.float32)
    v = anchor + 1.0
    flat = lambda x: 0.0                             # no fitness signal at all
    for _ in range(50):
        v = es_step(v, flat, n_pairs=2, sigma=0.01, lr=0.05, rng=rng,
                    weight_decay=1.0, anchor=anchor)
    assert np.abs(v - anchor).mean() < 0.9           # moved toward anchor...
    assert np.abs(v).mean() > 3.0                    # ...NOT toward zero


def test_es_step_improves_quadratic_fitness():
    """Antithetic ES on f(v) = -||v - v*||^2 must move toward v*."""
    rng = np.random.default_rng(1)
    target = rng.standard_normal(64).astype(np.float32)
    v = np.zeros(64, np.float32)
    fit = lambda x: -float(((x - target) ** 2).sum())
    d0 = float(((v - target) ** 2).sum())
    for _ in range(60):
        v = es_step(v, fit, n_pairs=8, sigma=0.1, lr=0.3, rng=rng)
    d1 = float(((v - target) ** 2).sum())
    assert d1 < 0.3 * d0, (d0, d1)
