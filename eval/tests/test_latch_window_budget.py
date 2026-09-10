"""The guidance budget must be spent INSIDE the window, whatever the window is.

Before 2026-08-27, s_t divided by the sum of alpha over ALL steps, so a windowed
guide spent only that window's share of a whole-schedule budget. Because alpha =
1-sigma is small at high noise, the loss was severe and silent: on a real 24-step
schedule the first 20% of steps carried 0.2% of the budget and the GUI's default
0.0-0.6 window carried 9.3%. Windows were advertised as "which steps", but acted
as a huge, non-linear volume control.
"""
import sys

import pytest
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
from stable_audio_3.inference.latch_guided import _st_weights


def _sigmas(n=24):
    return torch.linspace(1.0, 0.0, n + 1)


def test_an_unwindowed_budget_still_sums_to_one():
    assert _st_weights(_sigmas()).sum().item() == pytest.approx(1.0, abs=1e-5)


def test_a_windowed_budget_ALSO_sums_to_one():
    """The whole point: narrowing the window must not quietly reduce the dose."""
    sig = _sigmas()
    m = torch.zeros(len(sig) - 1)
    m[:5] = 1.0                                    # an early, narrow window
    assert _st_weights(sig, active_mask=m).sum().item() == pytest.approx(1.0, abs=1e-5)


def test_weight_falls_entirely_inside_the_window():
    sig = _sigmas()
    m = torch.zeros(len(sig) - 1)
    m[10:15] = 1.0
    w = _st_weights(sig, active_mask=m)
    assert w[:10].sum().item() == pytest.approx(0.0, abs=1e-9)
    assert w[15:].sum().item() == pytest.approx(0.0, abs=1e-9)
    assert w[10:15].sum().item() == pytest.approx(1.0, abs=1e-5)


def test_an_early_window_is_no_longer_starved():
    """The regression that made the paper's 'guide the first 20%' inexpressible:
    that window used to receive 0.2% of the budget."""
    sig = _sigmas()
    n = len(sig) - 1
    m = torch.zeros(n)
    m[: int(n * 0.2)] = 1.0
    old = (_st_weights(sig) * m).sum().item()      # pre-fix delivered fraction
    new = _st_weights(sig, active_mask=m).sum().item()
    assert old < 0.05, f"sanity: the old scheme really was starved ({old:.4f})"
    assert new == pytest.approx(1.0, abs=1e-5)


def test_shape_within_the_window_is_still_alpha_weighted():
    """Normalisation changes the DOSE, not the SHAPE: cleaner steps still get more."""
    sig = _sigmas()
    m = torch.zeros(len(sig) - 1)
    m[10:20] = 1.0
    w = _st_weights(sig, active_mask=m)
    inside = w[10:20]
    assert torch.all(inside[1:] >= inside[:-1]), "should still rise toward clean"


def test_an_empty_window_does_not_divide_by_zero():
    sig = _sigmas()
    w = _st_weights(sig, active_mask=torch.zeros(len(sig) - 1))
    assert torch.isfinite(w).all() and w.sum().item() == pytest.approx(0.0)
