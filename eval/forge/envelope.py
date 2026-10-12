"""Envelope geometry shared with the client (spec §5.2).

SVG viewBox 400x100: node x = 0, 133.33, 266.67, 400; y(v) = 90 - 80 v. Segment i is a
quadratic Bezier with control point at the chord midpoint lifted by 60*c_i, so x(s) is
linear in s and y can be evaluated directly at s = 3x - i.
"""
import math

import numpy as np

from .contract import ForgeError


def _num(v, lo, hi, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ForgeError(400, f"{what}={v!r} must be a number in {lo}..{hi}")
    return float(v)


def validate_envelope(env) -> dict:
    if not isinstance(env, dict):
        raise ForgeError(400, "envelope must be an object with points[4] and curves[3]")
    pts, cs = env.get("points"), env.get("curves")
    if not isinstance(pts, list) or len(pts) != 4 or not isinstance(cs, list) or len(cs) != 3:
        raise ForgeError(400, "envelope must have exactly 4 points and 3 curves")
    return {"points": [_num(p, 0.0, 1.0, "envelope.points") for p in pts],
            "curves": [_num(c, -1.0, 1.0, "envelope.curves") for c in cs]}


def sample_envelope(env, n: int) -> np.ndarray:
    env = validate_envelope(env)
    n = int(n)
    if n <= 0:
        return np.zeros(0, dtype=np.float32)
    x = np.zeros(1) if n == 1 else np.arange(n, dtype=np.float64) / (n - 1)
    i = np.minimum(2, np.floor(3.0 * x).astype(np.int64))
    s = 3.0 * x - i
    ys = 90.0 - 80.0 * np.asarray(env["points"], dtype=np.float64)
    ya, yb = ys[i], ys[i + 1]
    yc = (ya + yb) / 2.0 - 60.0 * np.asarray(env["curves"], dtype=np.float64)[i]
    y = (1 - s) ** 2 * ya + 2 * s * (1 - s) * yc + s ** 2 * yb
    return np.clip((90.0 - y) / 80.0, 0.0, 1.0).astype(np.float32)
