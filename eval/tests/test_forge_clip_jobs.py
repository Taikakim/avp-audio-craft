import math
from pathlib import Path

import numpy as np
import pytest
import torch

import forge_testutil  # noqa: F401
from forge import clip_jobs as J
from forge import passes, progress
from forge.contract import ForgeError
from test_forge_commit import HEADS, payload as commit_payload
from test_forge_commit_run import FakeSvc

ENV = {"points": [0.2, 0.6, 0.6, 0.2], "curves": [0, 0, 0]}
REF_A = {"kind": "upload", "sha256": "a" * 64}
REF_B = {"kind": "upload", "sha256": "b" * 64}


@pytest.fixture
def rig(monkeypatch, tmp_path, tmp_path_factory):
    srv = forge_testutil.get_server(tmp_path_factory)      # real server on the GPU box, stub elsewhere
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    for k, v in HEADS.items():
        monkeypatch.setitem(srv.HEADS, k, v)
    calls = {"hold": [], "inpaint": []}
    monkeypatch.setattr(passes, "run_hold_pass",
                        lambda s, z, d, r, w, label: (calls["hold"].append((d, r)), z)[1])
    monkeypatch.setattr(passes, "run_inpaint_pass",
                        lambda s, z, reg, r, w, chroma_target=None, label="": (calls["inpaint"].append((reg, chroma_target)), z)[1])
    monkeypatch.setattr(passes, "decode_latent", lambda s, z, n: torch.zeros(2, n))
    monkeypatch.setattr(J, "chroma_384", lambda audio, sr, T: np.zeros((384, T), np.float32))
    return srv, calls


@pytest.mark.parametrize("bad,needle", [
    ({}, "audio"), ({"audio": REF_A, "noise_level": 1.5}, "noise_level"),
    ({"audio": REF_A, "envelope": {"points": [0, 0], "curves": [0]}}, "envelope"),
])
def test_validate_a2a_clip_rejects(bad, needle):
    with pytest.raises(ForgeError) as e:
        J.validate_a2a_clip(bad, HEADS)
    assert needle in e.value.message


def test_run_a2a_clip_flat_noise_and_ckpt(rig):
    srv, calls = rig
    res = J.run_a2a_clip(srv, FakeSvc(), "forge-t", {"audio": REF_A, "render": {"prompt": "acid", "steps": 8},
                                                     "envelope": None, "noise_level": 0.35,
                                                     "chain": None, "ckpt_path": "/x/dora.ckpt"})
    depth, req = calls["hold"][0]
    T = math.ceil(40 * 44100 / 4096)
    assert depth.shape == (T,) and np.allclose(depth, 0.35)
    assert req["ckpt_path"] == "/x/dora.ckpt" and req["seed"] >= 0
    assert Path(res["files"][0]).is_file() and res["meta"]["depth_max"] == pytest.approx(0.35)
    assert progress.snapshot() is None


def test_run_a2a_clip_envelope(rig):
    srv, calls = rig
    J.run_a2a_clip(srv, FakeSvc(), "forge-t", {"audio": REF_A, "render": {"prompt": "acid"}, "envelope": ENV})
    depth = calls["hold"][0][0]
    assert depth[0] == pytest.approx(0.2) and depth.max() == pytest.approx(0.6)


def inpaint_payload(**kw):
    p = {"a": {"audio": REF_A, "start_sec": 0.0, "offset_sec": 0.0, "dur_sec": 20.0},
         "b": {"audio": REF_B, "start_sec": 16.0, "offset_sec": 0.0, "dur_sec": 20.0},
         "region": {"start_sec": 16.0, "end_sec": 20.0}, "curve": ENV, "chroma_xfade": True,
         "render": {"prompt": "blend", "steps": 12}, "pad_sec": 8.0}
    p.update(kw)
    return p


def test_validate_inpaint():
    v = J.validate_inpaint(inpaint_payload())
    assert (v["span_start"], v["span_end"]) == (8.0, 28.0)
    with pytest.raises(ForgeError):
        J.validate_inpaint(inpaint_payload(region={"start_sec": 20.0, "end_sec": 16.0}))
    with pytest.raises(ForgeError) as e:
        J.validate_inpaint(inpaint_payload(region={"start_sec": 0.0, "end_sec": 180.0}))
    assert "capped at 184 s" in e.value.message


def test_run_inpaint_preview_shifts_to_span(rig):
    srv, calls = rig
    res = J.run_inpaint_preview(srv, FakeSvc(), "forge-t", inpaint_payload())
    regions, target = calls["inpaint"][0]
    assert regions == [(8.0, 12.0)]
    T = math.ceil(20 * 44100 / 4096)
    assert target.shape == (384, T)
    assert res["meta"]["span_start_sec"] == 8.0 and res["meta"]["op"] == "inpaint"


def test_submit_validation_for_new_ops(monkeypatch, tmp_path, tmp_path_factory):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    srv = forge_testutil.get_server(tmp_path_factory)
    import forge_api
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    for k, v in HEADS.items():
        monkeypatch.setitem(srv.HEADS, k, v)
    forge_api.reset_queue()
    c = fastapi_testclient.TestClient(srv.app)
    bad_commit = commit_payload()
    bad_commit["duration_sec"] = 500
    for op, body in (("commit", bad_commit), ("a2a_clip", {"noise_level": 0.3}),
                     ("inpaint", inpaint_payload(pad_sec=100))):
        r = c.post("/forge/jobs", json={"op": op, "payload": body})
        assert r.status_code == 400, (op, r.text)
