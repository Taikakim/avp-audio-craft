"""Schedule shapes for rectified-flow SA3 (spec §5.3).

The σ array reaches the samplers as a distribution-shift object: build_schedule() calls
dist_shift.shift(t, seq_len) with t = linspace(sigma_max, 0, steps+1) and then forces
t[0] = sigma_max. ArraySchedule ignores t (beyond its length) and returns our array, so
both sample_diffusion and the LatCH-guided sampler consume it with no fork change.
"""
import math

import numpy as np

from .contract import ForgeError

SHAPES = ("model", "logsnr", "geometric", "linear", "log", "exponential", "cosine")
DEFAULTS = {"shape": "model", "rho": 1.0, "sigma_min": 0.01, "lam_min": -6.2, "lam_max": 2.0,
            "stepped": False, "plateaus": 6, "tilt": 0.15}
_RANGES = {"rho": (0.1, 15.0), "sigma_min": (0.001, 0.5), "lam_min": (-12.0, 0.0),
           "lam_max": (0.0, 6.0), "plateaus": (2, 24), "tilt": (0.0, 1.0)}
RF_SAMPLERS = {"rectified_flow": ("euler", "rk4", "dpmpp", "pingpong"), "rf_denoiser": ("pingpong", "euler")}
FLAT_WARNING = "flat plateaus are no-op steps on ODE samplers"


def parse_spec(obj) -> dict:
    if obj is None:
        return dict(DEFAULTS)
    if not isinstance(obj, dict):
        raise ForgeError(400, "schedule must be an object")
    unknown = sorted(set(obj) - set(DEFAULTS))
    if unknown:
        raise ForgeError(400, f"unknown schedule field(s): {', '.join(unknown)}")
    spec = {**DEFAULTS, **obj}
    if spec["shape"] not in SHAPES:
        raise ForgeError(400, f"unknown schedule.shape {spec['shape']!r} (have {', '.join(SHAPES)})")
    if not isinstance(spec["stepped"], bool):
        raise ForgeError(400, "schedule.stepped must be true or false")
    p = spec["plateaus"]
    if isinstance(p, float) and p.is_integer():
        spec["plateaus"] = int(p)
    if isinstance(spec["plateaus"], bool) or not isinstance(spec["plateaus"], int):
        raise ForgeError(400, "schedule.plateaus must be an integer")
    for key, (lo, hi) in _RANGES.items():
        v = spec[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
            raise ForgeError(400, f"schedule.{key}={v!r} outside {lo}..{hi}")
        if key != "plateaus":
            spec[key] = float(v)
    if spec["lam_max"] <= spec["lam_min"]:
        raise ForgeError(400, "schedule.lam_max must be > lam_min")
    return spec


def sigmas(spec, steps, sigma_max) -> np.ndarray:
    shape = spec["shape"]
    if shape == "model":
        raise ValueError("the model shape has no explicit array — use build_schedule")
    n = int(steps)
    s_max = float(sigma_max)
    if n < 1:
        raise ForgeError(400, "steps must be >= 1")
    if not 0.0 < s_max <= 1.0:
        raise ForgeError(400, f"sigma_max {sigma_max!r} must be in (0, 1]")
    s_min = spec["sigma_min"]
    if shape != "logsnr" and s_min >= s_max:
        raise ForgeError(400, "schedule.sigma_min must be < sigma_max (the noise level)")
    u = np.arange(n, dtype=np.float64) / n
    w = u ** spec["rho"]
    if spec["stepped"]:
        P = spec["plateaus"]
        x = w * P
        fl = np.floor(x)
        tau = np.minimum(1.0, (fl + spec["tilt"] * (x - fl)) / (P - 1))
    else:
        tau = w
    if shape == "logsnr":
        lam_min = spec["lam_min"]
        if s_max < 1.0:
            lam_min = max(lam_min, math.log((1.0 - s_max) / s_max))
        if lam_min >= spec["lam_max"]:
            raise ForgeError(400, "noise level too low for this logSNR interval (raise lam_max)")
        sig = 1.0 / (1.0 + np.exp(lam_min + (spec["lam_max"] - lam_min) * tau))
    elif shape == "geometric":
        sig = np.exp(math.log(s_max) + (math.log(max(s_min, 1e-6)) - math.log(s_max)) * tau)
    elif shape == "linear":
        sig = s_max + (s_min - s_max) * tau
    elif shape == "log":
        sig = s_max + (s_min - s_max) * np.log1p(9.0 * tau) / math.log(10.0)
    elif shape == "exponential":
        sig = s_max + (s_min - s_max) * (np.exp(3.0 * tau) - 1.0) / (math.exp(3.0) - 1.0)
    else:  # cosine
        sig = s_min + (s_max - s_min) * (1.0 + np.cos(math.pi * tau)) / 2.0
    out = np.empty(n + 1, dtype=np.float64)
    out[:n] = sig
    out[0] = s_max
    out[n] = 0.0
    if np.any(np.diff(out) > 1e-12):
        raise ForgeError(400, "schedule is not non-increasing")
    return out


def _has_flat(arr) -> bool:
    return bool(np.any(np.diff(arr[:-1]) == 0.0))


def sampler_warnings(arr, spec, sampler_type):
    if not spec.get("stepped") or not _has_flat(arr):
        return []
    if sampler_type == "dpmpp":
        raise ForgeError(400, "flat plateaus (tilt 0) divide by zero in dpmpp — raise tilt or pick another sampler")
    if sampler_type in (None, "", "euler", "rk4"):
        return [FLAT_WARNING]
    return []


class ArraySchedule:
    def __init__(self, sigma_array):
        self.sigmas = np.asarray(sigma_array, dtype=np.float64)

    def shift(self, t, seq_len):
        import torch
        if t.dim() != 1 or t.shape[0] != len(self.sigmas):
            raise ValueError(f"ArraySchedule has {len(self.sigmas)} points; sampler asked for {tuple(t.shape)}")
        return torch.as_tensor(self.sigmas, dtype=t.dtype, device=t.device)


def resolve_schedule(req, steps, sigma_max, sampler_type=None):
    spec = parse_spec(req.get("schedule"))
    if spec["shape"] == "model":
        return None, []
    if req.get("dist_shift") not in (None, "", "default"):
        raise ForgeError(400, "schedule.shape replaces dist_shift — send one or the other")
    arr = sigmas(spec, steps, sigma_max)
    return ArraySchedule(arr), sampler_warnings(arr, spec, sampler_type)


def progress_to_cfg_interval(p_lo, p_hi, sigma_max):
    try:
        lo, hi, s = float(p_lo), float(p_hi), float(sigma_max)
    except (TypeError, ValueError):
        raise ForgeError(400, "cfg_interval_progress must be two numbers")
    if not (0.0 <= lo <= hi <= 1.0):
        raise ForgeError(400, f"cfg_interval_progress ({p_lo}, {p_hi}) must satisfy 0 <= lo <= hi <= 1")
    return (s * (1.0 - hi), s * (1.0 - lo))
