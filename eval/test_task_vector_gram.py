# eval/test_task_vector_gram.py — run: SAO/.venv/bin/python -m pytest eval/test_task_vector_gram.py -q
"""The Gram-matrix algebra is the part that can be silently wrong while printing plausible
numbers, so it gets tests against cases with known answers. The checkpoint I/O is exercised
by the tool's own built-in validation (raw-trainable path efficiency must reproduce
checkpoint_trajectory_stats' number for the same ladder)."""
import math

import torch

from eval.task_vector_gram import (dora_delta_eff, gram_from_vectors, ladder_stats_from_gram,
                                   group_cosines)


def _G(vs):
    return gram_from_vectors(torch.stack(vs).double())


def test_gram_is_inner_products():
    a, b = torch.tensor([1., 0.]), torch.tensor([1., 1.])
    G = _G([a, b])
    assert torch.allclose(G, torch.tensor([[1., 1.], [1., 2.]]).double())


def test_ladder_collinear_points_have_unit_efficiency_and_cosine():
    """3 checkpoints on a straight line: every step points the same way."""
    X = [torch.tensor([float(i), 0.]) for i in range(4)]
    s = ladder_stats_from_gram(_G(X), list(range(4)))
    assert abs(s["path_efficiency"] - 1.0) < 1e-9
    assert all(abs(c - 1.0) < 1e-9 for c in s["step_cosines"])


def test_ladder_zigzag_has_low_efficiency_and_negative_cosines():
    """Back-and-forth: net displacement small, successive steps anti-aligned."""
    X = [torch.tensor([0., 0.]), torch.tensor([1., 0.]), torch.tensor([0.1, 0.]),
         torch.tensor([1.1, 0.])]
    s = ladder_stats_from_gram(_G(X), list(range(4)))
    # net = 1.1, path = 1 + 0.9 + 1 = 2.9
    assert abs(s["path_efficiency"] - 1.1 / 2.9) < 1e-6   # inputs are float32 (0.1 inexact)
    assert all(c < 0 for c in s["step_cosines"])


def test_ladder_orthogonal_steps_hit_random_walk_floor():
    """Orthogonal steps of equal length: eff = 1/sqrt(n_steps), cosines 0. This is the
    number the AdamW-sweep arms sit on (0.31-0.38 for 9 steps -> 1/3), so the tool must
    get it exactly right on a synthetic case before it is read off real weights."""
    n = 9
    X = [torch.zeros(n)]
    for i in range(n):
        v = X[-1].clone(); v[i] += 1.0; X.append(v)
    s = ladder_stats_from_gram(_G(X), list(range(n + 1)))
    assert abs(s["path_efficiency"] - 1.0 / math.sqrt(n)) < 1e-9
    assert all(abs(c) < 1e-9 for c in s["step_cosines"])


def test_group_cosines_within_and_across():
    good = [torch.tensor([1., 0., 0.]), torch.tensor([1., 0.1, 0.])]
    bad = [torch.tensor([0., 0., 1.])]
    G = _G(good + bad)
    r = group_cosines(G, good_idx=[0, 1], bad_idx=[2])
    assert r["good_good"] > 0.99
    assert abs(r["bad_good"]) < 1e-9
    assert math.isnan(r["bad_bad"])          # a single member has no within-group pair


def test_dora_delta_is_zero_when_adapter_is_identity():
    """B=0 and magnitude = base row norms must give exactly ΔW_eff = 0 — the DoRA identity.
    If this fails the 'delta' would be measuring our own arithmetic, not training."""
    W = torch.randn(6, 5)
    A = torch.randn(2, 5); B = torch.zeros(6, 2)
    m = W.norm(dim=1)
    d = dora_delta_eff(W, A, B, m, scaling=1.0)
    assert d.abs().max() < 1e-6


def test_dora_delta_matches_reference_formula():
    W = torch.randn(6, 5); A = torch.randn(2, 5); B = torch.randn(6, 2); m = torch.rand(6) + 0.5
    V = W + B @ A
    ref = (V / V.norm(dim=1, keepdim=True)) * m[:, None] - W
    assert torch.allclose(dora_delta_eff(W, A, B, m, scaling=1.0), ref, atol=1e-6)
