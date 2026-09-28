"""ladder_outlier_probe: leave-one-out detrended residuals over one run's epoch ladder."""
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.ladder_outlier_probe import loo_residuals, tail_stats  # noqa: E402

T = torch.tensor([3., 7., 14., 21., 35.], dtype=torch.float64)


def test_pure_linear_drift_has_zero_residual():
    a = torch.randn(1000, dtype=torch.float64)
    b = torch.randn(1000, dtype=torch.float64)
    X = a[None] + b[None] * T[:, None]
    assert loo_residuals(X, T).abs().max() < 1e-9


def test_spike_lands_in_its_own_epoch_and_element():
    X = torch.randn(1000, dtype=torch.float64)[None] + 0.0 * T[:, None]
    X = X + 0.01 * torch.randn(5, 1000, dtype=torch.float64)
    X[3, 17] += 5.0
    R = loo_residuals(X, T)
    assert int(R[3].abs().argmax()) == 17
    assert R[3, 17].abs() > 50 * R[3].abs().median()


def test_tail_stats_counts_only_the_spikes():
    r = 0.01 * torch.randn(100000, dtype=torch.float64)
    r[:10] = 1.0
    s = tail_stats(r, k=8.0)
    assert s["n_out"] == 10
    assert s["frac_out"] == 10 / 100000
