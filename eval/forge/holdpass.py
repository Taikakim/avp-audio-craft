"""Graded-release hold for per-frame A2A noise (spec §8.1 S4-S5).

Generalises the /a2a_mix sinesweep hold (explorer_render_server.py 1793-1799): at step
time t, frames whose depth is below t are overwritten with (1-t)*z_ref + t*eps — they
have not been released yet. ODE samplers take it as the step callback; pingpong takes it
as a renoise_hook because its callback fires after the denoise, where edits to x are lost.
"""
import math

import numpy as np
import torch

from .envelope import sample_envelope


def clip_frame_span(start_sec, dur_sec, fps):
    f0 = int(math.floor(float(start_sec) * fps))
    f1 = int(math.ceil((float(start_sec) + float(dur_sec)) * fps))
    return f0, max(1, f1 - f0)


def depth_for_spans(spans, T):
    depth = np.zeros(int(T), dtype=np.float32)
    for f0, env, n in spans:
        vals = sample_envelope(env, n)
        lo, hi = max(0, f0), min(int(T), f0 + n)
        if hi > lo:
            depth[lo:hi] = np.maximum(depth[lo:hi], vals[lo - f0:hi - f0])
    return depth


def _scalar(t):
    return float(t.reshape(-1)[0]) if torch.is_tensor(t) else float(t)


class _Held:
    def __init__(self, z_ref, eps, depth):
        self.ref, self.eps = z_ref.float(), eps.float()
        self.depth = torch.as_tensor(np.asarray(depth, dtype=np.float32)).view(1, 1, -1)
        self._dev = None

    def on(self, device, dtype):
        if self._dev != (device, dtype):
            self.ref_d = self.ref.to(device, dtype)
            self.eps_d = self.eps.to(device, dtype)
            self.depth_d = self.depth.to(device)
            self._dev = (device, dtype)
        return self

    def apply(self, x, t):
        self.on(x.device, x.dtype)
        n = min(x.shape[-1], self.ref_d.shape[-1], self.depth_d.shape[-1])
        hold = self.depth_d[..., :n] < t
        target = (1.0 - t) * self.ref_d[..., :n] + t * self.eps_d[..., :n]
        x[..., :n] = torch.where(hold, target, x[..., :n])
        return x


def make_hold_callback(z_ref, eps, depth):
    held = _Held(z_ref, eps, depth)

    def callback(state):
        held.apply(state["x"], _scalar(state["t"]))
    return callback


def make_hold_renoise_hook(z_ref, eps, depth):
    held = _Held(z_ref, eps, depth)

    def hook(denoised, t_next, x, i):
        tn = _scalar(t_next)
        x_next = (1.0 - tn) * denoised + tn * torch.randn_like(x)
        return held.apply(x_next, tn)
    return hook
