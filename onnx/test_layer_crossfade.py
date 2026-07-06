"""Tests for the pure schedule logic of the layer-staggered activation crossfade
(steered_layer_crossfade.py). The GPU generation is smoke-tested separately;
these pin the per-block blend-weight schedule that decides how A morphs into B."""
import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from steered_layer_crossfade import block_alphas, staggered_alpha


# ---------------------------------------------------------------- block_alphas

def test_block_alphas_length_matches_blocks():
    a = block_alphas(24, mode="linear")
    assert len(a) == 24


def test_block_alphas_top_heavy_late_blocks_toward_B():
    # "top-heavy": late blocks (high index) blend most toward B, early stay A
    a = block_alphas(24, mode="top", strength=1.0)
    assert a[23] > a[12] > a[0]
    assert a[0] == pytest.approx(0.0, abs=0.05)     # earliest stays A
    assert a[23] == pytest.approx(1.0, abs=0.05)     # latest fully B


def test_block_alphas_bottom_heavy_is_mirror():
    top = block_alphas(24, mode="top", strength=1.0)
    bot = block_alphas(24, mode="bottom", strength=1.0)
    # bottom-heavy: early blocks toward B, late stay A — reverse ordering
    assert bot[0] > bot[12] > bot[23]
    assert bot[0] == pytest.approx(top[23], abs=1e-6)


def test_block_alphas_linear_monotone_full_range():
    a = block_alphas(24, mode="linear")
    assert a[0] == pytest.approx(0.0) and a[-1] == pytest.approx(1.0)
    assert all(a[i] <= a[i + 1] for i in range(len(a) - 1))


def test_block_alphas_uniform_constant():
    a = block_alphas(24, mode="uniform", level=0.5)
    assert all(x == pytest.approx(0.5) for x in a)


# ---------------------------------------------------------------- staggered_alpha (time-varying, for longform)

def test_staggered_alpha_wipe_top_first():
    # at t=0 nothing crossed; at t=1 all crossed; mid-transition top blocks lead
    n = 24
    a0 = staggered_alpha(n, t=0.0)
    a1 = staggered_alpha(n, t=1.0)
    amid = staggered_alpha(n, t=0.5)
    assert all(x == pytest.approx(0.0, abs=1e-6) for x in a0)
    assert all(x == pytest.approx(1.0, abs=1e-6) for x in a1)
    # mid: late blocks further along than early blocks
    assert amid[23] > amid[0]


def test_staggered_alpha_monotone_in_time_per_block():
    n = 24
    prev = staggered_alpha(n, t=0.0)
    for t in (0.25, 0.5, 0.75, 1.0):
        cur = staggered_alpha(n, t=t)
        assert all(cur[i] >= prev[i] - 1e-9 for i in range(n))
        prev = cur


# ---------------------------------------------------------------- blend

from steered_layer_crossfade import blend_activations


def test_blend_activations_endpoints():
    import torch
    A = torch.zeros(2, 5, 4)
    B = torch.ones(2, 5, 4)
    assert torch.equal(blend_activations(A, B, 0.0), A)
    assert torch.equal(blend_activations(A, B, 1.0), B)
    mid = blend_activations(A, B, 0.5)
    assert torch.allclose(mid, torch.full_like(A, 0.5))
