"""Latent-player endpoints hosted on the render server (:8056).

These are the GET endpoints ported from mir/scripts/latent_server_sa3.py so the
second resident SAME-L copy (7.12 GB) can be retired. No GPU, no real model:
MODEL.model.pretransform is stubbed, and the LatCH head loader is stubbed too.
"""
from __future__ import annotations
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
import io
import json
import sys
import types
import wave
from pathlib import Path

import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
import explorer_render_server as ers  # noqa: E402

C, T, DS = 4, 8, 64


class _FakePretransform:
    """Stands in for MODEL.model.pretransform: same decode() call signature."""

    def __init__(self):
        self._p = torch.nn.Parameter(torch.zeros(1))
        self.calls = []

    def parameters(self):
        yield self._p

    def decode(self, z, chunked=False, chunk_size=128, overlap=32):
        self.calls.append({"chunked": chunked, "chunk_size": chunk_size,
                           "overlap": overlap, "shape": tuple(z.shape)})
        n = z.shape[-1] * DS
        base = z.float().mean().item()
        return torch.full((1, 2, n), max(min(base, 0.5), -0.5))


class _FakeHead(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.lin = torch.nn.Conv1d(C, C, 1)
        self.metadata = {"out_channels": C}

    def forward(self, z, t):
        return self.lin(z)


def _wav_dur(raw: bytes) -> int:
    with wave.open(io.BytesIO(raw), "rb") as wf:
        assert wf.getnchannels() == 2
        assert wf.getsampwidth() == 2
        return wf.getnframes()


@pytest.fixture
def env(tmp_path, monkeypatch):
    import soundfile as sf
    lat = tmp_path / "latents"
    lat.mkdir()
    src = tmp_path / "src.wav"
    sf.write(src, np.zeros((DS * T, 2), dtype="float32"), 44100)
    for cid, val in (("cropA", 0.1), ("cropB", 0.2)):
        np.save(lat / f"{cid}.npy", np.full((C, T), val, dtype=np.float32))
        (lat / f"{cid}.json").write_text(json.dumps({
            "source_path": str(src), "start_sample": 0,
            "end_sample": DS * T, "padding_mask": [1] * (T - 2) + [0, 0]}))

    pre = _FakePretransform()
    monkeypatch.setattr(ers, "MODEL", types.SimpleNamespace(
        model=types.SimpleNamespace(pretransform=pre)), raising=False)
    monkeypatch.setattr(ers, "DS", DS)
    monkeypatch.setattr(ers, "SR", 44100)
    monkeypatch.setattr(ers, "PLAYER_CFG", {"latent_dir": str(lat),
                                            "chunk_size": 32, "overlap": 8})
    monkeypatch.setattr(ers, "HEADS", {"onset": {"name": "onset", "family": "medium",
                                                 "path": "/nonexistent/onset.pt",
                                                 "default_gain": 512.0}})
    monkeypatch.setattr(ers, "STEER_HEADS", {}, raising=False)
    monkeypatch.setattr(ers, "load_latch_from_checkpoint",
                        lambda p, device=None: _FakeHead())
    monkeypatch.setattr(ers, "OUT_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir()
    return types.SimpleNamespace(client=TestClient(ers.app), pre=pre, lat=lat)


def test_crops_lists_latent_ids(env):
    r = env.client.get("/crops")
    assert r.status_code == 200
    assert r.json() == ["cropA", "cropB"]


def test_meta_returns_sidecar(env):
    r = env.client.get("/meta", params={"crop": "cropA"})
    assert r.status_code == 200
    assert r.json()["start_sample"] == 0


def test_get_decode_returns_wav_trimmed_by_padding_mask(env):
    r = env.client.get("/decode", params={"crop": "cropA"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    # padding_mask has T-2 content frames -> trimmed to (T-2)*DS samples
    assert _wav_dur(r.content) == (T - 2) * DS


def test_get_decode_uses_resident_pretransform_with_config_chunking(env):
    env.client.get("/decode", params={"crop": "cropA"})
    assert env.pre.calls, "decode must go through the already-loaded pretransform"
    assert env.pre.calls[-1]["chunked"] is True
    assert env.pre.calls[-1]["chunk_size"] == 32
    assert env.pre.calls[-1]["overlap"] == 8


def test_get_decode_accepts_crop_id_alias(env):
    assert env.client.get("/decode", params={"crop_id": "cropA"}).status_code == 200


def test_source_returns_wav_slice(env):
    r = env.client.get("/source", params={"crop": "cropA"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert _wav_dur(r.content) == DS * T


@pytest.mark.parametrize("interp", ["lerp", "slerp"])
def test_mix_returns_wav(env, interp):
    r = env.client.get("/mix", params={"crop_a": "cropA", "crop_b": "cropB",
                                       "t": 0.5, "interp": interp})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert _wav_dur(r.content) == T * DS      # /mix does not trim


def test_steer_uses_the_shared_head_registry(env):
    r = env.client.get("/steer", params={"crop": "cropA", "head": "onset",
                                         "gain": 4.0})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert "onset" in ers.STEER_HEADS      # cached from the HEADS registry entry


def test_steer_unknown_head_is_404_and_lists_heads(env):
    r = env.client.get("/steer", params={"crop": "cropA", "head": "nope"})
    assert r.status_code == 404
    assert r.json()["heads"] == ["onset"]


def test_unknown_crop_is_404(env):
    assert env.client.get("/decode", params={"crop": "ghost"}).status_code == 404


def test_post_decode_still_works_and_uses_config_latent_dir(env):
    r = env.client.post("/decode", json={"crop_id": "cropA"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"


def test_player_cfg_is_config_driven_not_hardcoded():
    cfg = ers.load_player_cfg()
    assert "latent_dir" in cfg and "chunk_size" in cfg and "overlap" in cfg
    src = Path(ers.__file__).read_text()
    assert "/home/kim/Projects/latents_sa3" not in src, \
        "latent_dir must come from the ini, not a hardcoded path"
