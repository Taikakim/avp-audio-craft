"""Tests for sa3_control.contour_loss — differentiable soft-rank contour (morphological) loss.

Design note: papers/deep-research/MORPHOLOGICAL_SPACE_DESIGN_NOTE.md (§5.3).
Core property being tested: the loss measures the SHAPE (contour) of a per-frame profile and is
invariant to any strictly-monotone transform of the values (gain/EQ/compression) — exactly as tau->0.
Dependency-free (torch only); n is small (12 pitch classes) so the O(n^2) soft-rank is fine.
"""
import torch
import pytest

from sa3_control.contour_loss import soft_rank, contour_cosine_loss


def test_soft_rank_recovers_ordering():
    # value [1,3,2,0] -> 0-indexed ranks [1,3,2,0]; small tau -> ~hard ranks
    x = torch.tensor([1.0, 3.0, 2.0, 0.0])
    r = soft_rank(x, tau=0.01)
    assert torch.allclose(r, torch.tensor([1.0, 3.0, 2.0, 0.0]), atol=0.05), r


def test_soft_rank_monotone_invariance():
    # ranks are invariant to any strictly-increasing affine map; soft-rank matches as tau->0
    x = torch.tensor([0.2, 0.9, 0.5, -0.3])
    y = 3.7 * x + 5.0            # strictly-increasing affine
    assert torch.allclose(soft_rank(x, tau=0.01), soft_rank(y, tau=0.01), atol=0.05)


def test_loss_zero_on_identical():
    x = torch.rand(4, 12)
    assert contour_cosine_loss(x, x, tau=0.05).item() < 1e-3


def test_loss_small_on_monotone_transform():
    # same CONTOUR under gain+offset -> loss ~ 0 (this is the whole point vs. raw L1/cosine)
    x = torch.rand(8, 12)
    y = 2.5 * x + 0.7
    assert contour_cosine_loss(x, y, tau=0.02).item() < 0.02


def test_loss_larger_on_nonmonotone_than_monotone():
    torch.manual_seed(0)
    x = torch.rand(8, 12)
    mono = 2.5 * x + 0.7                          # same contour
    perm = x[:, torch.randperm(12)]               # a genuinely different contour
    l_mono = contour_cosine_loss(x, mono, tau=0.05).item()
    l_perm = contour_cosine_loss(x, perm, tau=0.05).item()
    assert l_perm > l_mono + 0.05, (l_mono, l_perm)


def test_gradient_flows_and_finite():
    pred = torch.rand(4, 12, requires_grad=True)
    target = torch.rand(4, 12)
    loss = contour_cosine_loss(pred, target, tau=0.05)
    loss.backward()
    assert pred.grad is not None
    assert torch.isfinite(pred.grad).all()
    assert pred.grad.abs().sum() > 0


def test_batched_dim_and_shapes():
    # (B, C, T) profile ranked along the C (pitch) axis; loss is a scalar
    pred = torch.rand(2, 12, 16)
    target = torch.rand(2, 12, 16)
    loss = contour_cosine_loss(pred, target, tau=0.05, dim=1)
    assert loss.ndim == 0
    assert torch.isfinite(loss)


def test_tau_sharpens_toward_hard_rank():
    x = torch.tensor([0.1, 0.4, 0.2, 0.9, 0.3])
    hard = torch.tensor([0.0, 3.0, 1.0, 4.0, 2.0])
    assert (soft_rank(x, tau=0.005) - hard).abs().max() < (soft_rank(x, tau=0.3) - hard).abs().max()
