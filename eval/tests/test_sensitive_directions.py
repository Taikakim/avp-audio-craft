# Owner: KUANG (created 2026-10-17)
"""eval/sensitive_directions.py core on the CPU (no SA3): the Jacobian subspace iteration recovers known singular
directions of a nonlinear map, perturbation sizes are as documented, and naming picks the right descriptor."""
import math
import os
import sys

import numpy as np
import pytest
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sensitive_directions import name_direction, perturb, slopes, top_right_singular  # noqa: E402


def test_recovers_top_singular_directions_of_a_nonlinear_map():
    torch.manual_seed(0)
    n_in, n_out = 40, 30
    U, _ = torch.linalg.qr(torch.randn(n_out, n_out))
    V, _ = torch.linalg.qr(torch.randn(n_in, n_in))
    s = torch.tensor([10.0, 6.0, 3.0] + [0.3] * (n_out - 3))
    A = U @ torch.diag(s) @ V[:, :n_out].T                   # known spectrum

    def f(X):                                                # (B, 4, 10) -> (B, 30), mildly nonlinear
        return torch.tanh(0.01 * (X.reshape(X.shape[0], -1) @ A.T)) * 100.0

    x = torch.zeros(1, 4, 10)
    Vk, sig = top_right_singular(f, x + 1e-3, k=3, iters=20, fd_eps=1e-3, chunk=2, seed=1)
    for i in range(3):
        c = abs(float(Vk[i].flatten() @ V[:, i]))
        assert c > 0.99, (i, c)
    assert sig.tolist() == pytest.approx([10.0, 6.0, 3.0], rel=0.02)


def test_perturbation_rms_is_alpha_times_x_rms():
    torch.manual_seed(1)
    x = torch.randn(1, 8, 50) * 3.0
    v = torch.randn(8, 50)
    v /= v.norm()
    d = perturb(x, v, 0.2) - x
    assert float(d.pow(2).mean().sqrt()) == pytest.approx(0.2 * float(x.pow(2).mean().sqrt()), rel=1e-5)


def test_slopes_and_naming():
    alphas = [-0.3, -0.15, 0.0, 0.15, 0.3]
    vals = [{"centroid": 2000 + 1000 * a, "rms_db": -14 + 0.1 * a, "onset_rate": 6.0} for a in alphas]
    sl = slopes(alphas, vals)
    assert sl["centroid"] == pytest.approx(1000.0) and sl["onset_rate"] == pytest.approx(0.0, abs=1e-9)
    spread = {"centroid": 200.0, "rms_db": 1.0, "onset_rate": 0.5}
    n = name_direction(sl, spread, name_z=1.0)
    assert n["name"] == "brighter" and n["top"] == "centroid"
    n2 = name_direction({k: -v for k, v in sl.items()}, spread)
    assert n2["name"] == "darker"
    assert name_direction({"centroid": 10.0}, spread)["name"] == "unnamed"


def test_compound_name():
    n = name_direction({"centroid": 400.0, "onset_rate": 0.8}, {"centroid": 200.0, "onset_rate": 0.5})
    assert n["name"] == "brighter + denser onsets"


def test_main_end_to_end_with_a_fake_sa3(tmp_path, monkeypatch):
    """Wiring check of main() (conditioning, Euler continuation, early exit, ladders, descriptors, page) against a tiny
    fake that mimics the SA3 calls the script makes. It cannot catch differences from the real SA3 API."""
    pytest.importorskip("soundfile")
    pytest.importorskip("scipy")
    import types
    import sensitive_directions as sd

    C, T, RATIO, SR = 4, 24, 256, 8000

    class FakeDiT(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.w = torch.nn.Parameter(torch.randn(16, C) * 0.3)
            self.model = types.SimpleNamespace(transformer=types.SimpleNamespace(layers=[0, 1, 2, 3]))

        def forward(self, x, t, cross_attn_cond=None, cfg_scale=1.0, exit_layer_ix=None, **kw):
            h = torch.tanh(torch.einsum("dc,bct->btd", self.w, x) + cross_attn_cond.mean() * 0.1)
            if exit_layer_ix is not None:
                return torch.cat([torch.zeros(x.shape[0], 1, 16), h], dim=1)   # one prepended token
            return -0.5 * x + 0.1 * torch.einsum("dc,btd->bct", self.w, h)

    class FakePre(torch.nn.Module):
        downsampling_ratio = RATIO

        def __init__(self):
            super().__init__()
            self.p = torch.nn.Parameter(torch.zeros(1))

        def decode(self, lat):
            env = lat[:, :1].repeat_interleave(RATIO, dim=-1)
            tt = torch.arange(env.shape[-1]) / SR
            return (0.3 * torch.tanh(env) * torch.sin(2 * math.pi * 440 * tt)).repeat(1, 2, 1)

    inner = types.SimpleNamespace(model=FakeDiT(), pretransform=FakePre(), io_channels=C, sample_rate=SR,
                                  sampling_dist_shift=None,
                                  conditioner=lambda cond, dev: {"x": 1},
                                  get_conditioning_inputs=lambda ct: {"cross_attn_cond": torch.ones(1, 3, 5)})
    fake = types.SimpleNamespace(model=inner, _adapt_sample_size=lambda cond, s, p: T * RATIO)

    class FakeSAM:
        @staticmethod
        def from_pretrained(name, device=None, model_half=False):
            return fake

        @staticmethod
        def _build_conditioning_dicts(prompt, neg, dur, b):
            return [{"prompt": prompt}], None

    mod = types.ModuleType("stable_audio_3")
    mod.StableAudioModel = FakeSAM
    inf = types.ModuleType("stable_audio_3.inference")
    smp = types.ModuleType("stable_audio_3.inference.sampling")
    smp.build_schedule = lambda steps, sigma_max, dist_shift, fallback_seq_len, include_endpoint, device: \
        torch.linspace(sigma_max, 0, steps + 1)
    monkeypatch.setitem(sys.modules, "stable_audio_3", mod)
    monkeypatch.setitem(sys.modules, "stable_audio_3.inference", inf)
    monkeypatch.setitem(sys.modules, "stable_audio_3.inference.sampling", smp)
    out = tmp_path / "run"
    monkeypatch.setattr(sys, "argv", ["sd", "--prompt", "a", "--seeds", "1", "2", "--duration", str(T * RATIO / SR),
                                      "--steps", "6", "--k", "2", "--iters", "3", "--alphas", "-0.2", "0", "0.2",
                                      "--device", "cpu", "--out", str(out)])
    assert sd.main() == 0
    import json
    res = json.loads((out / "results.json").read_text())
    assert len(res["runs"]) == 2 and len(res["runs"][0]["directions"]) == 2
    d = res["runs"][0]["directions"][0]
    assert [s["alpha"] for s in d["ladder"]] == [-0.2, 0.0, 0.2] and "name" in d and "slopes" in d
    assert (out / "index.html").exists() and (out / "p0_s1_base.wav").exists()
