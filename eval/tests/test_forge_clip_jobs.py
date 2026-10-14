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
        J.validate_inpaint(inpaint_payload(region={"start_sec": 0.0, "end_sec": 370.0}))
    assert "capped at 374.43 s" in e.value.message


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


def test_latent_similarity_is_one_for_the_same_latent_and_low_for_an_unrelated_one():
    z = torch.randn(1, 8, 50)
    assert J.latent_similarity(z, z) == pytest.approx(1.0, abs=1e-5)
    assert J.latent_similarity(z, -z) == pytest.approx(-1.0, abs=1e-5)
    assert abs(J.latent_similarity(z, torch.randn(1, 8, 50))) < 0.4
    assert J.latent_similarity(z, z[..., :20]) == pytest.approx(1.0, abs=1e-5)     # compares the common frames


def test_run_a2a_clip_reports_how_close_the_result_stayed_to_the_source(rig, monkeypatch):
    srv, calls = rig
    res = J.run_a2a_clip(srv, FakeSvc(), "forge-t", {"audio": REF_A, "render": {"prompt": "acid"}, "noise_level": 0.4})
    assert res["meta"]["source_similarity"] == pytest.approx(1.0, abs=1e-5)         # the hold stub returns z untouched
    # a pass that throws the source away: the number says so
    monkeypatch.setattr(passes, "run_hold_pass", lambda s, z, d, r, w, label: -torch.ones_like(z))
    res = J.run_a2a_clip(srv, FakeSvc(), "forge-t2", {"audio": REF_A, "render": {"prompt": "acid"}, "noise_level": 0.4})
    assert res["meta"]["source_similarity"] == pytest.approx(-1.0, abs=1e-5)


# ---------------------------------------------------------------- outpaint (WINTERMUTE 2026-10-14)
def test_outpaint_windows_respect_the_cap_and_grow_their_context():
    w = J.outpaint_windows(20.0, pre=10.0, post=400.0, context=30.0, cap=184.0)  # cap passed in, any value
    assert [s for s, _, _ in w] == ["post", "post", "post", "pre"]
    assert all(c + n <= 184.0 + 1e-9 for _, c, n in w)
    assert w[0] == ("post", 20.0, 164.0)                  # context limited to the clip that exists
    assert w[1][1] == 30.0 and sum(n for s, _, n in w if s == "post") == pytest.approx(400.0)
    assert w[-1] == ("pre", 30.0, 10.0)


def test_validate_outpaint_rejects():
    with pytest.raises(ForgeError):
        J.validate_outpaint({"audio": REF_A, "pre_sec": 0, "post_sec": 0}, HEADS)
    with pytest.raises(ForgeError):
        J.validate_outpaint({"audio": REF_A, "post_sec": 9999}, HEADS)
    with pytest.raises(ForgeError):
        J.validate_outpaint({"post_sec": 5}, HEADS)


def test_run_outpaint_extends_both_sides_keeping_the_clip_samples(rig, monkeypatch):
    srv, calls = rig
    monkeypatch.setattr(passes, "decode_latent", lambda s, z, n: torch.full((2, n), 0.5))
    saved = {}
    monkeypatch.setattr(srv, "save_audio", lambda p, a, sr, normalize=True: (saved.update(a=a.numpy()), Path(p).write_bytes(b"x")))
    res = J.run_outpaint(srv, FakeSvc(), "forge-t", {
        "audio": REF_A, "offset_sec": 5.0, "dur_sec": 20.0, "pre_sec": 4.0, "post_sec": 6.0,
        "context_sec": 10.0, "render": {"prompt": "goa", "steps": 8, "seed": 11}, "chain": None})
    a = saved["a"]
    assert a.shape[1] == 30 * 44100
    assert np.allclose(a[:, :4 * 44100], 0.5)                            # new audio before
    assert np.allclose(a[:, 5 * 44100:23 * 44100], 0.1)                  # the clip, untouched inside
    assert np.allclose(a[:, -6 * 44100:], 0.5)                           # new audio after
    regs = [r for r, _ in calls["inpaint"]]
    assert regs == [[(10.0, 16.0)], [(0.0, 4.0)]]                        # post first, then pre
    assert res["meta"]["windows"] == 2 and res["meta"]["duration_sec"] == pytest.approx(30.0)
