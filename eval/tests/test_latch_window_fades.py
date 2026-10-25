# Owner: WINTERMUTE (created 2026-10-25)
"""E18: tapered LatCH window edges. A fade must leave the plateau exactly as a hard window over the plateau weighs it,
add only a decaying tail, and change nothing when no fade is asked for."""
import sys

import pytest
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
from stable_audio_3.inference.latch_guided import _guide_fades, _window_scale, fade_curve

N = 24
ALPHA = 1.0 - torch.linspace(1.0, 0.0, N + 1)[:-1]


@pytest.mark.parametrize("schedule", ["alpha", "flat"])
def test_no_fade_is_unchanged(schedule):
    w = _window_scale(ALPHA, 0, N, schedule)
    assert w.sum().item() == pytest.approx(1.0, abs=1e-6)
    assert torch.allclose(w, _window_scale(ALPHA, 0, N, schedule, 0, 0, "exp"))


@pytest.mark.parametrize("shape", ["linear", "cosine", "exp"])
def test_fade_out_equals_hard_window_plus_tail(shape):
    hard = _window_scale(ALPHA, 0, 19, "alpha")            # end_pct ~0.8, hard
    soft = _window_scale(ALPHA, 0, N, "alpha", 0, 5, shape)  # full window, last 5 steps fade out
    assert torch.allclose(soft[:19], hard[:19], atol=1e-7)
    tail = soft[19:] / hard[18]
    assert (tail > 0).all() and (tail[1:] <= tail[:-1] * ALPHA[20:] / ALPHA[19:-1] + 1e-6).all()


def test_fade_in_ramps_up():
    w = _window_scale(ALPHA, 4, N, "flat", 6, 0, "cosine")
    assert w[:4].sum().item() == 0
    ramp = w[4:10]
    assert (ramp[1:] > ramp[:-1]).all() and ramp[-1] < w[10]
    assert w[10:].sum().item() == pytest.approx(1.0, abs=1e-6)   # plateau normalised to 1


def test_fades_covering_the_window_still_normalise():
    w = _window_scale(ALPHA, 0, 4, "flat", 2, 4, "linear")
    assert w.sum().item() == pytest.approx(1.0, abs=1e-6)


def test_fade_curves():
    for s in ("linear", "cosine", "exp"):
        e = fade_curve(10, s)
        assert (e > 0).all() and (e <= 1).all() and (e[1:] < e[:-1]).all()
        assert torch.allclose(fade_curve(10, s, rising=True), e.flip(0))
    assert fade_curve(10, "exp")[-1].item() < 0.02
    with pytest.raises(ValueError):
        fade_curve(3, "square")


def test_guide_fades_from_pct():
    assert _guide_fades({"fade_out_pct": 0.2, "fade_shape": "exp"}, 24) == (0, 5, "exp")
    assert _guide_fades({}, 24) == (0, 0, "linear")
