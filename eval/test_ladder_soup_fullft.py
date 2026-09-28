"""ladder_soup_fullft.filtered_mean: per-value mean over epochs, dropping an epoch where it is a
detrended outlier."""
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.ladder_soup_fullft import filtered_mean  # noqa: E402

T = torch.tensor([3., 7., 14., 21., 35.], dtype=torch.float64)


def test_no_outliers_equals_plain_mean():
    X = torch.randn(5, 10000, dtype=torch.float64)
    m, frac = filtered_mean(X, T, k=50.0)
    assert torch.allclose(m, X.mean(0))
    assert frac == 0.0


def test_spike_is_excluded_from_that_value_only():
    X = 0.01 * torch.randn(5, 10000, dtype=torch.float64) + 1.0
    X[4, 5] = 100.0
    m, frac = filtered_mean(X, T, k=8.0)
    assert abs(float(m[5]) - float(X[:4, 5].mean())) < 1e-12
    assert torch.allclose(m[6:], X[:, 6:].mean(0))
    assert 0 < frac < 1e-3
