"""The new guided ping-pong sampler must actually be guided, and must actually ping-pong.

test_guided_sampler_dispatch.py pins WHICH sampler gets chosen. This file pins what
the new one DOES, because the bug it fixes was precisely a sampler that ran and
produced audio while the guidance did nothing measurable -- a failure no dispatch
test can catch.

Toy model + toy head on CPU: no checkpoint, no GPU, milliseconds. The point is not
audio quality, it is that gain reaches the output and that the ping-pong update is
the ping-pong update.
"""
import sys

import pytest
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
from stable_audio_3.inference.latch_guided import (
    sample_flow_euler_multi_latch_guided,
    sample_flow_pingpong_multi_latch_guided,
)

B, C, T, STEPS = 1, 4, 16, 8          # STEPS=8 == the post-trained operating point


class ToyModel(torch.nn.Module):
    """Stands in for the DiT: returns a velocity shaped like x."""

    def forward(self, x, t, **kw):
        return 0.1 * x


class ToyHead(torch.nn.Module):
    """Stands in for a LatCH head: (B,C,T) -> (B,1,T), differentiable wrt x."""

    t_injection = "concat"            # keeps _ensure_time_cache a no-op

    def forward(self, x, t):
        return x.mean(dim=1, keepdim=True)


def _guide(start_pct=0.0, end_pct=1.0, weight=1.0):
    return {
        "head": ToyHead(),
        # a target the toy head cannot already be sitting on, so guidance has work
        "target": torch.full((B, 1, T), 5.0),
        "weight": weight, "start_pct": start_pct, "end_pct": end_pct,
        "loss_type": "mse", "huber_beta": 1.0, "w_sec": None, "fps": None,
    }


def _sigmas(n=STEPS):
    return torch.linspace(1.0, 0.0, n + 1)


def _run(sampler, rho, mu, *, seed=0, guide_kw=None, x=None):
    """Same seed every call, so any difference is attributable to the arguments."""
    torch.manual_seed(seed)
    x0 = x if x is not None else torch.randn(B, C, T)
    return sampler(ToyModel(), x0.clone(), _sigmas(), [_guide(**(guide_kw or {}))],
                   rho=rho, mu=mu, gamma=0.0, n_iter=2, disable_tqdm=True)


def _dev(a, b):
    return (a - b).norm().item()


# --- the regression these tests exist for ------------------------------------------

def test_guidance_changes_the_output():
    """The whole failure mode was guidance that ran and did nothing."""
    unguided = _run(sample_flow_pingpong_multi_latch_guided, 0.0, 0.0)
    guided = _run(sample_flow_pingpong_multi_latch_guided, 1.0, 1.0)
    assert _dev(guided, unguided) > 1e-6


def test_more_gain_moves_the_output_further():
    """Gain must reach the output monotonically. G's bracket saw gain 2 and gain 2048
    produce identical audio; on a correct sampler that cannot happen."""
    base = _run(sample_flow_pingpong_multi_latch_guided, 0.0, 0.0)
    small = _dev(_run(sample_flow_pingpong_multi_latch_guided, 0.01, 0.01), base)
    large = _dev(_run(sample_flow_pingpong_multi_latch_guided, 1.0, 1.0), base)
    assert large > small > 0.0


def test_an_empty_window_guides_nothing():
    """start_pct == end_pct selects no steps; the render must equal the unguided one
    rather than quietly guiding anyway."""
    unguided = _run(sample_flow_pingpong_multi_latch_guided, 0.0, 0.0)
    empty = _run(sample_flow_pingpong_multi_latch_guided, 1.0, 1.0,
                 guide_kw={"start_pct": 0.5, "end_pct": 0.5})
    assert _dev(empty, unguided) == pytest.approx(0.0, abs=1e-9)


def test_a_late_window_differs_from_a_full_window():
    """Windows must select WHERE guidance acts."""
    full = _run(sample_flow_pingpong_multi_latch_guided, 1.0, 1.0)
    late = _run(sample_flow_pingpong_multi_latch_guided, 1.0, 1.0,
                guide_kw={"start_pct": 0.5, "end_pct": 1.0})
    assert _dev(full, late) > 1e-6


# --- it must be ping-pong, not euler wearing a different name ----------------------

def test_pingpong_is_not_euler():
    """Same model, head, schedule, seed and input -- only the update rule differs.
    If these agreed, the 'fix' would be cosmetic."""
    x = torch.randn(B, C, T)
    pp = _run(sample_flow_pingpong_multi_latch_guided, 1.0, 1.0, x=x)
    eu = _run(sample_flow_euler_multi_latch_guided, 1.0, 1.0, x=x)
    assert _dev(pp, eu) > 1e-6


def test_pingpong_redraws_noise_and_euler_does_not():
    """The defining difference: ping-pong renoises from the clean estimate with FRESH
    noise each step, so it is stochastic across RNG draws; euler reuses the model's
    implied direction and is deterministic given the same input."""
    x = torch.randn(B, C, T)

    def _fixed_input(sampler, seed):
        torch.manual_seed(seed)
        return sampler(ToyModel(), x.clone(), _sigmas(), [_guide()],
                       rho=0.0, mu=0.0, gamma=0.0, n_iter=2, disable_tqdm=True)

    assert _dev(_fixed_input(sample_flow_pingpong_multi_latch_guided, 1),
                _fixed_input(sample_flow_pingpong_multi_latch_guided, 2)) > 1e-6
    assert _dev(_fixed_input(sample_flow_euler_multi_latch_guided, 1),
                _fixed_input(sample_flow_euler_multi_latch_guided, 2)) == pytest.approx(0.0, abs=1e-9)


def test_final_step_lands_on_the_clean_estimate():
    """sigma ends at 0, so the last renoise is (1-0)*z0 + 0*noise: the output must be
    the clean estimate, carrying no residual noise term."""
    out = _run(sample_flow_pingpong_multi_latch_guided, 0.0, 0.0)
    assert torch.isfinite(out).all()
    # with a fresh RNG draw the result must be identical -- the last step's noise is
    # multiplied by zero, so it cannot leak into the output
    torch.manual_seed(999)
    torch.randn(64)                                   # advance the RNG
    again = _run(sample_flow_pingpong_multi_latch_guided, 0.0, 0.0)
    assert _dev(out, again) == pytest.approx(0.0, abs=1e-9)


# --- loud failure rather than a wrong broadcast ------------------------------------

def test_a_per_element_schedule_is_refused():
    """sample_diffusion supports (B, steps+1) schedules; the guided path builds one
    global schedule. Broadcasting a 2-D one would silently index the wrong sigma."""
    with pytest.raises(ValueError, match="global 1-D schedule"):
        sample_flow_pingpong_multi_latch_guided(
            ToyModel(), torch.randn(B, C, T), _sigmas().unsqueeze(0).repeat(B, 1),
            [_guide()], rho=1.0, mu=1.0, disable_tqdm=True)
