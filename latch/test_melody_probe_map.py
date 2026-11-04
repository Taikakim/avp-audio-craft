"""Tests for melody_probe_map.py: the melodic targets, the grouped ridge, and a full extract -> analyze
pass on a fake DiT and a fake latent corpus (CPU)."""
import json
import os
import sys
import types

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import melody_probe_map as mp

FPS = mp.FPS


def test_f0_targets_split_the_bands():
    t = np.arange(int(60 * FPS)) / FPS
    semi = 60 + 6 * (t / 60) + 2 * np.sin(2 * np.pi * t / 3.0) + 0.3 * np.sin(2 * np.pi * t / 0.3)
    hz = 440 * 2 ** ((semi - 69) / 12)
    tg, v = mp.f0_targets(hz)
    assert v.all()
    mid = slice(int(10 * FPS), int(50 * FPS))
    phrase = 2 * np.sin(2 * np.pi * t / 3.0)
    assert np.corrcoef(tg["f0_phrase"][mid], phrase[mid])[0, 1] > 0.9     # the 3 s wave lands in the phrase band
    assert np.corrcoef(tg["f0_slow"][mid], 60 + 6 * t[mid] / 60)[0, 1] > 0.99
    assert abs(tg["f0_note"][mid]).max() < 1.5 and abs(tg["f0_slow"][mid] - (60 + 6 * t[mid] / 60)).max() < 0.5
    assert np.corrcoef(tg["f0_delta"][mid], np.gradient(phrase)[mid])[0, 1] > 0.8


def test_unvoiced_frames_are_filled_and_masked():
    hz = np.full(100, 440.0)
    hz[40:60] = 0.0
    tg, v = mp.f0_targets(hz)
    assert not v[40:60].any() and v[:40].all()
    assert np.allclose(tg["f0_semi"], 69.0)


def test_best_window_and_context():
    v = np.zeros(1000)
    v[600:900] = 1
    assert 560 <= mp.best_window(v, 320) <= 600
    z = np.arange(2 * 5, dtype=np.float32).reshape(2, 5)
    X = mp.with_context(z, ctx=1)
    assert X.shape == (5, 6) and X[0, 2] == z[0, 0] and X[0, 4] == z[0, 1] and X[4, 4] == z[0, 4]


def test_ridge_primal_and_dual_agree_and_groups_stay_whole():
    rng = np.random.default_rng(0)
    X, Xte = rng.normal(size=(30, 50)), rng.normal(size=(7, 50))
    Y = rng.normal(size=(30, 2))
    a = mp.ridge_path(X, Y, Xte, (10.0,))[10.0]
    b = mp.ridge_path(np.vstack([X] * 2), np.vstack([Y] * 2), Xte, (20.0,))[20.0]   # n > d -> primal
    assert a.shape == (7, 2) and np.allclose(a, b, atol=1e-6)
    groups = np.repeat(np.arange(12), 5)
    f = mp.group_folds(groups, 5)
    assert all(len(set(f[groups == g])) == 1 for g in range(12))


def test_grouped_ridge_finds_a_linear_signal_and_not_noise():
    rng = np.random.default_rng(1)
    n, d = 600, 20
    X = rng.normal(size=(n, d))
    groups = np.repeat(np.arange(30), n // 30)
    y = X @ rng.normal(size=d) + 0.1 * rng.normal(size=n)
    assert mp.grouped_ridge_r2(X, y, groups) > 0.95
    assert mp.grouped_ridge_r2(X, rng.normal(size=n), groups) < 0.05
    two = mp.grouped_ridge_r2_multi(X, np.stack([y, rng.normal(size=n)], 1), groups)
    assert two[0] > 0.95 and two[1] < 0.05


# ------------------------------------------------------------- end to end on a fake model and corpus

T_ALL, W, D, M = 400, 160, 32, 4


def _corpus(root, n=12):
    root.mkdir()
    rng = np.random.default_rng(3)
    for i in range(n):
        stem = f"{i:06d}"
        t = np.arange(T_ALL) / FPS
        semi = 55 + 10 * rng.random() + 3 * np.sin(2 * np.pi * t / (2 + 3 * rng.random()) + rng.random() * 6)
        voiced = (rng.random(T_ALL) > 0.2).astype(np.float32)
        z = rng.normal(size=(256, T_ALL)).astype(np.float32) * 0.5
        z[0] = (semi - 60) / 5                                  # pitch is linearly in the latent
        np.save(root / f"{stem}.npy", z)
        (root / f"{stem}.json").write_text(json.dumps({"source_track": f"Artist{i // 2} - Song{i}", "prompt": "x"}))
        np.savez(root / f"{stem}.TIMESERIES.npz", f0_other_ts=(440 * 2 ** ((semi - 69) / 12)).astype(np.float32),
                 f0_other_voiced_ts=voiced, beat_activation_ts=np.abs(np.sin(t * 7)).astype(np.float32),
                 hpcp_ts=rng.random((T_ALL, 12)).astype(np.float32))


def _fake_model():
    import torch
    from torch import nn

    class Transformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = nn.ModuleList([nn.Linear(D, D) for _ in range(3)])
            self.memory = nn.Parameter(torch.randn(M, D))

    class DiT(nn.Module):
        def __init__(self):
            super().__init__()
            self.proj = nn.Linear(256, D)
            with torch.no_grad():                               # keep the pitch channel readable
                self.proj.weight.mul_(0.05)
                self.proj.weight[0, 0] = 1.0
            self.transformer = Transformer()

        def forward(self, x, t, **cond):
            h = self.proj(x.transpose(1, 2))
            h = torch.cat([self.transformer.memory[None], h], 1)
            for layer in self.transformer.layers:
                h = h + torch.tanh(layer(h))
            return h

    torch.manual_seed(0)
    cdm = types.SimpleNamespace(model=DiT(),
                                conditioner=lambda conds, device: {},
                                get_conditioning_inputs=lambda tensors: {})
    return types.SimpleNamespace(model=cdm)


class _Head:
    def __init__(self):
        import torch
        self.p = torch.nn.Parameter(torch.zeros(1))

    def parameters(self):
        return iter([self.p])

    def eval(self):
        return self

    def __call__(self, x, t):
        semi = x[:, :1] * 5 + 60
        return 440 * 2 ** ((semi - 69) / 12)


def _install_fakes(monkeypatch):
    sa3 = types.ModuleType("stable_audio_3")
    sa3.StableAudioModel = types.SimpleNamespace(from_pretrained=lambda name, device=None: _fake_model())
    latch = types.ModuleType("stable_audio_3.models.latch")
    latch.load_latch_from_checkpoint = lambda path, device="cpu": _Head()
    monkeypatch.setitem(sys.modules, "stable_audio_3", sa3)
    monkeypatch.setitem(sys.modules, "stable_audio_3.models", types.ModuleType("stable_audio_3.models"))
    monkeypatch.setitem(sys.modules, "stable_audio_3.models.latch", latch)


def test_extract_then_analyze_end_to_end(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    _install_fakes(monkeypatch)
    _corpus(tmp_path / "lat")
    base = dict(latent_dir=tmp_path / "lat", n_crops=12, window=W, per_artist=2, min_voiced=0.3,
                sigmas="0.909,0.137", f0_head=tmp_path / "head.pt", seed=0, device="cpu")
    mp.run_extract(types.SimpleNamespace(out_dir=tmp_path / "acts", random_init=False, **base))
    mp.run_extract(types.SimpleNamespace(out_dir=tmp_path / "rnd", random_init=True, **{**base, "sigmas": "0.137"}))
    man = json.loads((tmp_path / "acts" / "manifest.json").read_text())
    assert len(man["crops"]) == 12 and len({c["artist"] for c in man["crops"]}) == 6
    blocks = np.load(next((tmp_path / "acts").glob("*__s0137.blocks.npy")))
    assert blocks.shape == (3, W, D)                         # memory tokens stripped
    assert np.load(next((tmp_path / "acts").glob("*__s0137.memory.npy"))).shape == (3, D)

    res = mp.analyze(tmp_path / "acts", tmp_path / "lat", random_dir=tmp_path / "rnd", n_null=1, log=lambda m: None)
    lo = res["sigmas"]["0.137"]
    assert res["z0_ctx"]["f0_semi"] > 0.9                     # pitch is in the clean latent by construction
    assert lo["x_t_ctx"]["f0_semi"] > lo["null"]["f0_slow"] - 1 and lo["f0_head"]["f0_semi"] > 0.9
    assert max(b["f0_semi"] for b in lo["blocks"]) > 0.5
    assert res["sigmas"]["0.909"]["x_t_ctx"]["f0_semi"] < lo["x_t_ctx"]["f0_semi"]   # noise hides it
    assert isinstance(res["random_init"], dict) and len(res["random_init"]["0.137"]) == 3
    assert "0.909" not in res["random_init"]                  # the control covered one sigma only
    assert len(lo["register_per_crop"]["memory_tokens"]) == 3
    md = mp.summary_markdown(res)
    assert "| 0.137 | f0_phrase |" in md and "| 0.909 | beat |" in md
