"""Overlap regions and the chroma-crossfade guidance target (spec §8.1 S6)."""
import math

import numpy as np

from .envelope import sample_envelope


def region_frames(start_sec, end_sec, fps, T):
    f0 = max(0, int(math.floor(float(start_sec) * fps)))
    f1 = min(int(T), int(math.ceil(float(end_sec) * fps)))
    return f0, max(f0, f1)


def chroma_target(cA, cB, f0, f1, curve):
    tgt = np.array(cA, dtype=np.float32, copy=True)
    tgt[:, f1:] = cB[:, f1:]
    n = f1 - f0
    if n > 0:
        v = sample_envelope(curve, n)[None, :]
        tgt[:, f0:f1] = (1.0 - v) * cA[:, f0:f1] + v * cB[:, f0:f1]
    return tgt


def pad_target(target, frames):
    t = np.asarray(target, dtype=np.float32)
    if t.shape[1] >= frames:
        return np.ascontiguousarray(t[:, :frames])
    return np.pad(t, ((0, 0), (0, frames - t.shape[1])), mode="edge")
