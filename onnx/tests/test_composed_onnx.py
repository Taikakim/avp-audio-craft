"""Structural tests for the composed control+LatCH generator (no ORT needed —
a stub session records the feeds). Spec:
docs/superpowers/specs/2026-07-03-composed-control-latch-sweep.md

Run: stable-audio-3/.venv/bin/python -m pytest onnx/tests/test_composed_onnx.py -q
(from SAO root, PYTHONPATH=onnx)
"""
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sa3_composed_onnx import build_latch_guides, generate_z0_control_latch_guided  # noqa: E402


class StubSession:
    """Records every feed dict; returns a small constant velocity."""
    def __init__(self, T):
        self.T = T
        self.feeds = []

    def run(self, _outs, feed):
        self.feeds.append({k: (v.copy() if hasattr(v, "copy") else v) for k, v in feed.items()})
        return [np.full((1, 256, self.T), 0.01, np.float32)]


class TinyHead(torch.nn.Module):
    """Stands in for a LatCH head: (x, t) -> (1, 1, T) differentiable output."""
    def forward(self, x, t):
        return x.mean(dim=1, keepdim=True)


def _run(T=32, steps=4, cfg=6.0, gain=2.0):
    sess = StubSession(T)
    cond = (np.zeros((8, 16), np.float32), np.ones((8,), np.float32), np.zeros((16,), np.float32))
    ct = np.random.default_rng(0).standard_normal((1, 4, 8)).astype(np.float32)
    out = generate_z0_control_latch_guided(
        sess, cond=cond, uncond=cond,
        cond_tok=ct, zero_tok=np.zeros_like(ct), gain=gain,
        guides=[{"head": TinyHead(), "target": torch.zeros(1, 1, T), "weight": 1.0}],
        frames=T, steps=steps, cfg_scale=cfg, seed=7, rho=1.0, mu=1.0, n_iter=1)
    return sess, out, ct


def test_control_tokens_reach_the_graph():
    sess, out, ct = _run()
    assert out["z0"].shape == (1, 256, 32)
    assert all("control_tokens" in f and "gain" in f for f in sess.feeds), \
        "every DiT call must carry control inputs"


def test_cond_uncond_token_routing():
    """cond passes carry cond_tok; uncond passes carry zero_tok (control-server parity)."""
    sess, _, ct = _run(cfg=6.0)
    conds = [f for f in sess.feeds if np.allclose(f["control_tokens"], ct)]
    uncs = [f for f in sess.feeds if np.allclose(f["control_tokens"], 0.0)]
    assert len(conds) == len(uncs) > 0, (len(conds), len(uncs))


def test_cfg1_skips_uncond():
    sess, _, ct = _run(cfg=1.0)
    assert all(np.allclose(f["control_tokens"], ct) for f in sess.feeds)


def test_guidance_actually_modifies_x():
    """With rho/mu on vs off (weight 0), z0 must differ — the guidance path is live."""
    sess1 = StubSession(32)
    cond = (np.zeros((8, 16), np.float32), np.ones((8,), np.float32), np.zeros((16,), np.float32))
    ct = np.zeros((1, 4, 8), np.float32)
    common = dict(cond=cond, uncond=cond, cond_tok=ct, zero_tok=ct, gain=1.0,
                  frames=32, steps=4, cfg_scale=1.0, seed=7, n_iter=1)
    g_on = [{"head": TinyHead(), "target": torch.full((1, 1, 32), 5.0), "weight": 1.0}]
    g_off = [{"head": TinyHead(), "target": torch.full((1, 1, 32), 5.0), "weight": 0.0}]
    a = generate_z0_control_latch_guided(sess1, guides=g_on, rho=8.0, mu=8.0, **common)
    b = generate_z0_control_latch_guided(StubSession(32), guides=g_off, rho=8.0, mu=8.0, **common)
    assert not np.allclose(a["z0"], b["z0"])


# ---------------------------------------------------------------------------
# build_latch_guides — the server-side job->guides adapter
# ---------------------------------------------------------------------------
_META = {"std_mean": 2.0, "std_std": 0.5, "standardized": True,
         "out_channels": 1, "loss_type": "mse"}


def _fake_loader_calls():
    calls = []

    def load(ckpt):
        calls.append(ckpt)
        return TinyHead(), dict(_META)
    return load, calls


def test_build_latch_guides_standardizes_target():
    load, _ = _fake_loader_calls()
    guides, rho, mu, prov = build_latch_guides(
        {"head_ckpt": "h.pt", "target_raw": 3.0}, frames=16, load_head=load)
    g = guides[0]
    assert g["target"].shape == (1, 1, 16)
    assert torch.allclose(g["target"], torch.full((1, 1, 16), (3.0 - 2.0) / 0.5))
    assert g["weight"] == 1.0 and g["loss_type"] == "mse"
    assert prov["target_raw"] == 3.0 and prov["target_std"] == 2.0


def test_build_latch_guides_caches_head_by_ckpt():
    load, calls = _fake_loader_calls()
    cache = {}
    for _ in range(3):
        build_latch_guides({"head_ckpt": "h.pt", "target_raw": 1.0}, frames=8,
                           load_head=load, head_cache=cache)
    assert calls == ["h.pt"]


def test_build_latch_guides_overrides_and_defaults():
    load, _ = _fake_loader_calls()
    _, rho, mu, _ = build_latch_guides(
        {"head_ckpt": "h.pt", "target_raw": 1.0}, frames=8, load_head=load)
    assert rho == 512.0 and mu == 512.0        # onset_envelope operating point TBD by probe
    _, rho2, mu2, _ = build_latch_guides(
        {"head_ckpt": "h.pt", "target_raw": 1.0, "rho": 128.0, "mu": 64.0,
         "weight": 0.5, "start_pct": 0.2, "end_pct": 0.9}, frames=8, load_head=load)
    assert rho2 == 128.0 and mu2 == 64.0
