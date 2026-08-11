"""Differentiable soft-rank *contour* (morphological) loss — prototype.

Design note: `papers/deep-research/MORPHOLOGICAL_SPACE_DESIGN_NOTE.md` (§5.3), from Kant & Polansky,
"The Structure of Morphological Space". The idea:

  A morph is a parameter-over-time; its *contour* is the shape (the ordering of its values), and
  contour is invariant to any strictly-monotone transform of the values (gain / EQ / compression /
  the genre-generic magnitude offset). Polansky's contour distance ≈ ANGLE between contours ≈ cosine
  similarity — and the authors flag cosine's *differentiability* as the ML door. This module walks
  through it: convert a profile to a (differentiable) rank vector, then take the cosine of the
  centred rank vectors. The result is a shape-matching loss that ignores monotone value changes.

Why not a library: Blondel et al. 2020 (`fast-soft-sort`/`torchsort`) gives O(n log n) soft ranks,
but it is not installed in the ROCm venv and n here is tiny (12 pitch classes, or up to 128 bins),
so the dependency-free O(n^2) pairwise-sigmoid soft-rank below is fine and avoids a new dep.

Invariance caveat (honest): the monotone invariance is *exact only as tau -> 0*; for finite tau the
softness scales with the value spread, so it is approximate. Small tau (~0.02-0.1 on unit-ish data)
is close enough — see the tests. This is the ANGULAR (shape) part of contour distance; the full
basis-space coordinates (an L-1 linear map of the ranks) are a future refinement — cosine-on-ranks
already captures the paper's OCD≈angle relation.

Usage (prototype; wiring into training is a separate, deliberate step — two options, readout-head
loss vs meter-in-gradient term, see the design note):
    from sa3_control.contour_loss import contour_cosine_loss
    loss = contour_cosine_loss(pred_chroma, target_chroma, tau=0.05, dim=<pitch axis>)
"""
from __future__ import annotations

import torch


def soft_rank(x: torch.Tensor, tau: float = 0.1, dim: int = -1) -> torch.Tensor:
    """Differentiable 0-indexed rank of ``x`` along ``dim`` (pairwise-sigmoid soft-rank).

    rank_i = (sum_j sigmoid((x_i - x_j) / tau)) - 0.5   (the -0.5 removes the self-comparison,
    so distinct values map to {0, 1, ..., n-1} and ties share the average rank). Smaller ``tau``
    -> sharper, closer to the hard rank; the op is fully differentiable in ``x``.
    """
    xw = x.movedim(dim, -1)                       # ranking axis -> last
    diff = xw.unsqueeze(-1) - xw.unsqueeze(-2)    # (..., n, n): [i, j] = x_i - x_j
    r = torch.sigmoid(diff / tau).sum(dim=-1) - 0.5
    return r.movedim(-1, dim)


def contour_cosine_loss(
    pred: torch.Tensor,
    target: torch.Tensor,
    tau: float = 0.1,
    dim: int = -1,
    eps: float = 1e-8,
) -> torch.Tensor:
    """Contour (shape) loss = 1 - cosine(soft_rank(pred), soft_rank(target)), centred along ``dim``.

    Both profiles are converted to soft ranks along ``dim`` and mean-centred (removing the constant
    rank-sum offset so cosine measures pure shape); the loss is ``(1 - cos)`` averaged over every
    other axis (batch, frames, ...). Zero when the two share a contour (up to a monotone transform),
    positive otherwise. Differentiable end-to-end.
    """
    rp = soft_rank(pred, tau=tau, dim=dim)
    rt = soft_rank(target, tau=tau, dim=dim)
    rp = rp - rp.mean(dim=dim, keepdim=True)
    rt = rt - rt.mean(dim=dim, keepdim=True)
    num = (rp * rt).sum(dim=dim)
    den = rp.norm(dim=dim) * rt.norm(dim=dim) + eps
    cos = num / den
    return (1.0 - cos).mean()
