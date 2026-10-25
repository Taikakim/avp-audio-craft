# Owner: WINTERMUTE (created 2026-10-15)
# Last edited: WINTERMUTE 2026-10-25 -- fade shape linear/cosine/exp (E18 crossfades); default linear unchanged
"""film_schedule.py -- per-step FiLM gain by noise level (EXPERIMENTS E8: timestep-gated FiLM).

WHY. The FiLM density adapter has range but carries the training set's style; LatCH is transparent but narrow. On SA3,
rhythm and arrangement are committed at high noise and timbre/character at low noise (2026-10-15 early-budget bracket),
so FiLM at full strength EARLY and faded to 0 for the low-noise tail should keep the density it sets while leaving the
character to the base model (and to late, alpha-weighted LatCH). It also locates WHERE in the schedule the leak enters.

HOW. The control adapter reads its gain live from `sa3_control.adapters._ACTIVE["gain"]` on every forward. A forward
pre-hook on the module the samplers call as `model(x, t, ...)` (StableAudioModel.model.model, both the guided and the
unguided samplers) sets that gain from the step's sigma before each call. Sigma semantics match the DoRA interval:
1 = pure noise (first step), 0 = clean (last). The FiLM tokens themselves are unchanged.

    gain(sigma) = gain                       for sigma_min <= sigma <= sigma_max
                  gain * ramp(shape) to 0    over `fade` sigma below sigma_min (and above sigma_max); shape linear/cosine/exp
                  0                          outside that

The defaults (0, 1, fade 0) give the constant gain, so a request without the keys behaves as before.
"""
from __future__ import annotations

import contextlib
import math

import torch


_EXP_K = math.log(100.0)   # exp ramp: 1 -> 1% across the fade (same as latch_guided.fade_curve)


def ramp(u: float, shape: str = "linear") -> float:
    """Envelope at fraction u in [0, 1] into a fade (0 = edge of the active band, 1 = end of the fade)."""
    if shape == "linear":
        return 1.0 - u
    if shape == "cosine":
        return 0.5 + 0.5 * math.cos(math.pi * u)
    if shape == "exp":
        return math.exp(-_EXP_K * u)
    raise ValueError(f"fade shape must be linear/cosine/exp, got {shape!r}")


def film_gain_at(sigma: float, gain: float, sigma_min: float = 0.0, sigma_max: float = 1.0, fade: float = 0.0,
                 shape: str = "linear") -> float:
    if sigma_min <= sigma <= sigma_max:
        return gain
    d = (sigma_min - sigma) if sigma < sigma_min else (sigma - sigma_max)
    if fade > 0 and d < fade:
        return gain * ramp(d / fade, shape)
    return 0.0


def is_scheduled(film_req: dict | None) -> bool:
    if not film_req:
        return False
    return (float(film_req.get("sigma_min", 0.0)) > 0.0 or float(film_req.get("sigma_max", 1.0)) < 1.0)


@contextlib.contextmanager
def film_gain_schedule(module: torch.nn.Module, active: dict, gain: float, sigma_min: float, sigma_max: float,
                       fade: float = 0.0, log: list | None = None, shape: str = "linear"):
    """Set active["gain"] from each forward's sigma (positional arg 1, or kwarg t) for the duration."""
    def pre(_mod, args, kwargs):
        t = args[1] if len(args) > 1 else kwargs.get("t")
        if t is None:
            return None
        s = float(t.flatten()[0]) if torch.is_tensor(t) else float(t)
        g = film_gain_at(s, gain, sigma_min, sigma_max, fade, shape)
        active["gain"] = g
        if log is not None:
            log.append((round(s, 4), round(g, 4)))
        return None

    h = module.register_forward_pre_hook(pre, with_kwargs=True)
    try:
        yield
    finally:
        h.remove()
