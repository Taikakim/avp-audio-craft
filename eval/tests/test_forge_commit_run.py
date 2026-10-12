import math
from pathlib import Path

import numpy as np
import pytest
import torch

import forge_testutil  # noqa: F401
from forge import commit as C
from forge import passes, progress
from forge.contract import ForgeError
from test_forge_commit import HEADS, payload


class FakeSvc:
    def __init__(self):
        self.stretch_calls = []

    def resolve_audio(self, ref):
        return Path(f"/fake/{(ref.get('sha256') or ref.get('crop_id'))[:4]}.wav")

    def stretched_path(self, p, speed, semis):
        self.stretch_calls.append((p.name, round(speed, 4), round(semis, 4)))
        return p if abs(speed - 1) < 5e-4 and abs(semis) < 1e-4 else p.with_suffix(".st.wav")

    def load_audio(self, p):
        return np.full((2, 44100 * 40), 0.1, np.float32)

    def encode_cached(self, buf):
        return torch.ones(1, 8, math.ceil(buf.shape[1] / 4096))


@pytest.fixture
def rig(monkeypatch, tmp_path, tmp_path_factory):
    srv = forge_testutil.get_server(tmp_path_factory)      # real server on the GPU box, stub elsewhere
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    for k, v in HEADS.items():
        monkeypatch.setitem(srv.HEADS, k, v)
    calls = {"hold": [], "inpaint": [], "steer": [], "decode": []}
    monkeypatch.setattr(passes, "run_hold_pass",
                        lambda s, z, d, r, w, label: (calls["hold"].append((label, d, r)), z * 2)[1])
    monkeypatch.setattr(passes, "run_inpaint_pass",
                        lambda s, z, reg, r, w, chroma_target=None, label="": (calls["inpaint"].append((label, reg, chroma_target)), z)[1])
    monkeypatch.setattr(passes, "steer_master", lambda s, z, h, g: (calls["steer"].append((h, g)), z)[1])
    monkeypatch.setattr(passes, "decode_latent", lambda s, z, n: (calls["decode"].append(n), torch.zeros(2, n))[1])
    monkeypatch.setattr(C, "chroma_384", lambda audio, sr, T: np.zeros((384, T), np.float32))
    return srv, calls


def test_commit_runs_all_stages(rig):
    srv, calls = rig
    svc = FakeSvc()
    res = C.run_commit(srv, svc, "forge-test-1", payload())
    assert Path(res["files"][0]).name == "mix.wav" and Path(res["files"][0]).is_file()
    assert Path(res["latents"][0]).name == "mix.z0.npy"
    meta = res["meta"]
    assert [s["label"] for s in meta["stages"]] == C.STAGES
    on = [s["on"] for s in meta["stages"]]
    assert on == [True, True, True, False, True, True, True, True, True]
    assert meta["stages"][3]["note"] == "all bypassed"
    T = math.ceil(40 * 44100 / 4096)
    labels = [c[0] for c in calls["hold"]]
    assert labels == ["lane0:a2a:0", "lane2:a2a:0"]
    depth0 = calls["hold"][0][1]
    assert depth0.shape == (T,) and depth0[0] == 0 and depth0[200] == pytest.approx(0.3)
    assert calls["hold"][0][2]["latch"] is None and calls["hold"][0][2]["seed"] >= 0
    assert calls["inpaint"][0][0] == "lane0:ov:a-b" and calls["inpaint"][0][2].shape == (384, T)
    assert calls["steer"] == [("rms_energy_bass", 64.0)]
    assert calls["decode"] == [40 * 44100]
    assert ("bbbb.wav", round(140 / 138, 4), 0.12) in svc.stretch_calls
    assert set(meta["resolved_seeds"]) == {"lane0:a2a:0", "lane2:a2a:0", "lane0:ov:a-b"}
    assert [l["used"] for l in meta["lanes"]] == [True, False, True, False]
    assert progress.snapshot() is None


def test_commit_all_muted_is_400(rig):
    srv, _ = rig
    p = payload()
    for lane in p["lanes"]:
        lane["muted"] = True
    with pytest.raises(ForgeError) as e:
        C.run_commit(srv, FakeSvc(), "forge-test-2", p)
    assert e.value.status == 400 and "every lane is empty or muted" in e.value.message
    assert progress.snapshot() is None


def test_a_master_with_slots_runs_a_guided_pass_on_the_mix_and_not_the_old_steer(rig):
    from test_forge_commit import master_chain
    srv, calls = rig
    p = payload()
    p["master"] = master_chain(noise=0.3)
    res = C.run_commit(srv, FakeSvc(), "forge-test-m", p)
    assert [c[0] for c in calls["hold"]] == ["lane0:a2a:0", "lane2:a2a:0", "master"]
    label, depth, req = calls["hold"][-1]
    T = math.ceil(40 * 44100 / 4096)
    assert depth.shape == (T,) and np.allclose(depth, 0.3)
    assert req["latch"][0]["head"] == "rms_energy_bass" and req["latch"][0]["target_raw"][0][0] == -30.0
    assert req["latch"][0]["gain"] == 1024.0 and req["rho"] == 1024.0
    assert calls["steer"] == []                                                # the single-head step is not used
    meta = res["meta"]
    assert "master" in meta["resolved_seeds"]
    assert meta["passes"][-1]["kind"] == "master"
    assert meta["stages"][7]["on"] is True and meta["stages"][7]["note"] == "latch + norm"


def test_a_master_with_slots_but_no_active_head_runs_nothing(rig):
    from test_forge_commit import master_chain
    srv, calls = rig
    p = payload()
    p["master"] = master_chain()
    p["master"]["slots"][0]["head"] = "none"
    res = C.run_commit(srv, FakeSvc(), "forge-test-m2", p)
    assert [c[0] for c in calls["hold"]] == ["lane0:a2a:0", "lane2:a2a:0"] and calls["steer"] == []
    assert res["meta"]["stages"][7]["note"] == "norm"
