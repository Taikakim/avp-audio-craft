# eval/test_trajectory_sketch_analyze.py — run: SAO/.venv/bin/python -m pytest eval/test_trajectory_sketch_analyze.py -q
"""Known-answer walks: the reader must recover them or it cannot be trusted on real sketches."""
import math

import numpy as np

from eval.trajectory_sketch_analyze import (autocorr_cos, multiscale_efficiency, window_snr,
                                            step_cos_series)


def _rw(T=4000, D=512, seed=0):
    return np.random.RandomState(seed).randn(T, D).astype(np.float64)


def test_random_walk_efficiency_follows_inverse_sqrt_and_zero_autocorr():
    U = _rw()
    ws, eff = multiscale_efficiency(U, windows=(1, 4, 16, 64, 256))
    for w, e in zip(ws, eff):
        assert abs(e - 1 / math.sqrt(w)) < 0.15 / math.sqrt(w) + 0.03, (w, e)
    lags, ac = autocorr_cos(U, lags=(1, 2, 8, 32))
    assert all(abs(x) < 0.05 for x in ac)


def test_straight_line_has_unit_efficiency_and_unit_autocorr():
    d = np.random.RandomState(1).randn(512)
    U = np.tile(d, (500, 1))
    _, eff = multiscale_efficiency(U, windows=(1, 8, 64))
    assert all(abs(e - 1.0) < 1e-9 for e in eff)
    _, ac = autocorr_cos(U, lags=(1, 5, 50))
    assert all(abs(x - 1.0) < 1e-9 for x in ac)


def test_momentum_walk_autocorr_decays_geometrically():
    """AR(1) with rho=0.9: cos(u_t, u_{t+τ}) -> rho^τ. This is what Adam's momentum does to
    pure-noise gradients — the reader must not mistake it for drift."""
    rho, T, D = 0.9, 6000, 512
    rs = np.random.RandomState(2)
    U = np.zeros((T, D)); u = np.zeros(D)
    for t in range(T):
        u = rho * u + math.sqrt(1 - rho * rho) * rs.randn(D); U[t] = u
    lags, ac = autocorr_cos(U, lags=(1, 5, 20))
    for l, x in zip(lags, ac):
        assert abs(x - rho ** l) < 0.05, (l, x, rho ** l)
    # and its long-window efficiency still falls like a random walk (no drift)
    ws, eff = multiscale_efficiency(U, windows=(256, 1024))
    assert eff[-1] < 0.15


def test_window_snr_is_one_over_w_for_noise_and_one_for_signal():
    G = _rw(3000)
    ws, snr = window_snr(G, windows=(1, 10, 100))
    assert abs(snr[0] - 1.0) < 1e-9
    assert abs(snr[1] - 0.1) < 0.05 and abs(snr[2] - 0.01) < 0.01
    S = np.tile(np.random.RandomState(3).randn(512), (300, 1))
    _, snr = window_snr(S, windows=(1, 10, 100))
    assert all(abs(x - 1.0) < 1e-9 for x in snr)


def test_step_cos_series_pairs_adjacent_rows():
    U = np.array([[1., 0.], [1., 0.], [0., 1.], [0., -1.]])
    c = step_cos_series(U)
    assert np.allclose(c, [1.0, 0.0, -1.0])
