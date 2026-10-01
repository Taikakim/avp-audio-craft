"""Frame-level latent splice with a short linear crossfade inside region edges (spec §8.1 S5-S6)."""
import numpy as np
import torch

from .contract import SPLICE_XFADE_FRAMES


def _runs(mask):
    m = np.concatenate([[False], np.asarray(mask, bool), [False]])
    d = np.diff(m.astype(np.int8))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def splice_by_mask(z_old, z_new, mask, xfade=SPLICE_XFADE_FRAMES):
    mask = np.asarray(mask, bool)
    if not mask.any():
        return z_old
    T = z_old.shape[-1]
    w = np.zeros(T, dtype=np.float32)
    for a, b in _runs(mask[:T]):
        w[a:b] = 1.0
        n = b - a
        for k in range(min(int(xfade), n)):
            ramp = (k + 1) / (int(xfade) + 1)
            w[a + k] = min(w[a + k], ramp)
            w[b - 1 - k] = min(w[b - 1 - k], ramp)
    wt = torch.as_tensor(w, dtype=torch.float32).view(1, 1, -1)
    return (1.0 - wt) * z_old.float() + wt * z_new.float()
