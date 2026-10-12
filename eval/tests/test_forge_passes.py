import math
import types

import numpy as np
import pytest
import torch

import forge_testutil  # noqa: F401
from forge import passes
from forge.render_settings import parse_render, to_request

DS, SR = 4096, 44100


class FakePre(torch.nn.Module):
    downsampling_ratio = DS

    def __init__(self):
        super().__init__()
        self.w = torch.nn.Parameter(torch.zeros(1))

    def decode(self, z, chunked=True, chunk_size=128, overlap=32):
        return torch.full((1, 2, z.shape[-1] * DS), 0.25)


class FakeModel:
    def __init__(self, objective="rectified_flow", fill=5.0):
        self.calls, self.fill = [], fill
        self.model = types.SimpleNamespace(diffusion_objective=objective, sampling_dist_shift=None,
                                           pretransform=FakePre())

    def _build_conditioning_dicts(self, prompt, negative, duration, batch):
        return [{"prompt": prompt, "seconds_total": duration}], None

    def _adapt_sample_size(self, cond, sample_size, pad, allow_grow=False):
        return int(math.ceil((cond[0]["seconds_total"] + pad) * SR / DS)) * DS

    def generate(self, **kw):
        self.calls.append(kw)
        frames = kw["sample_size"] // DS
        kw["latents_sink"].append(torch.full((1, 8, frames), self.fill))
        return kw["latents_sink"][-1]


@pytest.fixture
def srv(monkeypatch):
    # Drives the REAL server's resolvers (resolve_latch, resolve_shift, ...) with a fake model, so it
    # needs the server importable (torch + SA3 fork + GPU-box paths). Skipped on a CPU-only box.
    try:
        import explorer_render_server as srv
    except ModuleNotFoundError as e:
        pytest.skip(f"render server not importable here: {e}")
    monkeypatch.setattr(srv, "prepare_model", lambda *a, **k: False)
    return srv


def req(**kw):
    return to_request(parse_render(kw), seed=11)


def test_zero_depth_skips(srv, monkeypatch):
    fm = FakeModel()
    monkeypatch.setattr(srv, "MODEL", fm)
    z = torch.randn(1, 8, 20)
    out = passes.run_hold_pass(srv, z, np.zeros(20, np.float32), req(prompt="p"), [], "lane0")
    assert torch.equal(out, z) and fm.calls == []


def test_hold_pass_callback_path(srv, monkeypatch):
    fm = FakeModel()
    monkeypatch.setattr(srv, "MODEL", fm)
    z = torch.zeros(1, 8, 20)
    depth = np.zeros(20, np.float32)
    depth[5:15] = 0.4
    w = []
    out = passes.run_hold_pass(srv, z, depth, req(prompt="p", steps=8), w, "lane0")
    kw = fm.calls[0]
    assert kw["init_noise_level"] == pytest.approx(0.4)
    assert kw["init_latents"].shape == (1, 8, 20)
    assert "renoise_hook" not in kw and callable(kw["callback"])
    assert kw["cfg_interval"] == pytest.approx((0.0, 0.4))
    assert kw["return_latents"] is True
    assert torch.equal(out[..., :5], z[..., :5]) and torch.equal(out[..., 15:], z[..., 15:])
    assert float(out[0, 0, 10]) == pytest.approx(5.0)


@pytest.mark.parametrize("objective,sampler", [("rectified_flow", "pingpong"), ("rf_denoiser", None)])
def test_hold_pass_pingpong_uses_renoise_hook(srv, monkeypatch, objective, sampler):
    fm = FakeModel(objective)
    monkeypatch.setattr(srv, "MODEL", fm)
    depth = np.full(12, 0.3, np.float32)
    passes.run_hold_pass(srv, torch.zeros(1, 8, 12), depth, req(prompt="p", sampler_type=sampler), [], "l")
    assert callable(fm.calls[0]["renoise_hook"])


def test_non_finite_aborts(srv, monkeypatch):
    monkeypatch.setattr(srv, "MODEL", FakeModel(fill=float("nan")))
    with pytest.raises(RuntimeError, match="non-finite latents in lane2"):
        passes.run_hold_pass(srv, torch.zeros(1, 8, 12), np.full(12, 0.5, np.float32), req(prompt="p"), [], "lane2")


def test_inpaint_pass_regions_and_chroma(srv, monkeypatch):
    fm = FakeModel()
    monkeypatch.setattr(srv, "MODEL", fm)
    monkeypatch.setitem(srv.HEADS, "chroma_other", {"path": "/x/chroma.pt", "default_gain": 2048.0})
    z = torch.zeros(1, 8, 40)
    tgt = np.ones((384, 40), np.float32)
    out = passes.run_inpaint_pass(srv, z, [(1.0, 2.0)], req(prompt="p", steps=8), [], chroma_target=tgt, label="ov")
    kw = fm.calls[0]
    assert kw["inpaint_mask_start_seconds"] == [1.0] and kw["inpaint_mask_end_seconds"] == [2.0]
    assert kw["cfg_interval"] == pytest.approx((0.0, 1.0))
    frames = passes.model_latent_frames(srv, req(prompt="p"), 40 * DS / SR)
    assert np.asarray(kw["latch_configs"][0]["target_raw"]).shape == (384, frames)
    f0, f1 = math.floor(1.0 * SR / DS), math.ceil(2.0 * SR / DS)
    assert float(out[0, 0, f0 + 3]) == pytest.approx(5.0) and float(out[0, 0, 0]) == 0.0 and float(out[0, 0, f1 + 1]) == 0.0


def test_inpaint_without_chroma_head_warns(srv, monkeypatch):
    monkeypatch.setattr(srv, "MODEL", FakeModel())
    monkeypatch.delitem(srv.HEADS, "chroma_other", raising=False)
    w = []
    passes.run_inpaint_pass(srv, torch.zeros(1, 8, 40), [(1.0, 2.0)], req(prompt="p"), w,
                            chroma_target=np.ones((384, 40), np.float32), label="ov")
    assert any("chroma crossfade skipped" in m for m in w)


def test_steer_and_decode(srv, monkeypatch):
    monkeypatch.setattr(srv, "MODEL", FakeModel())
    monkeypatch.setattr(srv, "_player_steer_head", lambda name: (lambda z, t: z))
    z = torch.zeros(1, 2, 3)
    out = passes.steer_master(srv, z, "rms_energy_bass", 6.0)
    assert torch.allclose(out, torch.ones(1, 2, 3))
    audio = passes.decode_latent(srv, torch.zeros(1, 8, 3), 5000)
    assert audio.shape == (2, 5000) and float(audio[0, 0]) == 0.25
