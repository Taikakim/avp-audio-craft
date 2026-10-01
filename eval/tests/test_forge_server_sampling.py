import pytest

import forge_testutil  # noqa: F401

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def srv():
    # These exercise the REAL server's resolvers and routes with the model stubbed; they cannot run
    # where torch / the SA3 fork / the GPU-box paths are missing (a CPU-only box). Run on the dev box.
    try:
        import explorer_render_server as srv
    except ModuleNotFoundError as e:
        pytest.skip(f"render server not importable here: {e}")
    return srv


def test_cfg_interval_progress(srv):
    assert srv.resolve_cfg_interval({"cfg_interval_progress": [0.1, 0.85]}) == pytest.approx((0.15, 0.9))
    assert srv.resolve_cfg_interval({"cfg_interval_progress": [0.0, 0.5]}, sigma_max=0.4) == pytest.approx((0.2, 0.4))
    assert srv.resolve_cfg_interval({"cfg_interval": [0.2, 0.8]}) == (0.2, 0.8)
    assert srv.resolve_cfg_interval({}) == (0.0, 1.0)
    from forge.contract import ForgeError
    with pytest.raises(ForgeError):
        srv.resolve_cfg_interval({"cfg_interval_progress": [0, 1], "cfg_interval": [0, 1]})


def test_resolve_shift_model_path_unchanged(srv):
    w = []
    assert srv.resolve_shift({}, 24, 1.0, w) is None and w == []
    flux = srv.resolve_shift({"dist_shift": 3.0}, 24, 1.0, w)
    assert type(flux).__name__ == "FluxDistributionShift"
    arr = srv.resolve_shift({"schedule": {"shape": "logsnr"}}, 8, 1.0, w)
    assert type(arr).__name__ == "ArraySchedule"


def test_log_norms_passthrough(srv):
    cfgs, hp = srv.resolve_latch([{"builtin": "recurrence", "gain": 10.0}], {"log_norms": True})
    assert hp["log_norms"] is True
    _, hp2 = srv.resolve_latch([{"builtin": "recurrence", "gain": 10.0}], {})
    assert hp2["log_norms"] is False


def test_schedule_route_shapes(srv):
    c = fastapi_testclient.TestClient(srv.app)
    r = c.post("/schedule", json={"steps": 8, "duration": 10.0, "schedule": {"shape": "logsnr"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["shape"] == "logsnr" and len(body["sigmas"]) == 9 and body["sigmas"][0] == 1.0
    assert body["warnings"] == []
    r = c.post("/schedule", json={"steps": 4, "duration": 10.0, "sampler_type": "dpmpp",
                                  "schedule": {"shape": "linear", "stepped": True, "plateaus": 2, "tilt": 0.0}})
    assert r.status_code == 400 and "dpmpp" in r.json()["error"]
    r = c.post("/schedule", json={"steps": 8, "duration": 10.0, "dist_shift": 3.0, "schedule": {"shape": "cosine"}})
    assert r.status_code == 400


def test_generate_passes_schedule_scale_phi_and_warnings(srv, monkeypatch, tmp_path):
    seen = {}

    class FakeModel:
        class model:
            diffusion_objective = "rectified_flow"
            sampling_dist_shift = None

        def generate(self, **kw):
            import torch
            seen.update(kw)
            kw["latents_sink"].append(torch.zeros(1, 256, 4))
            return torch.zeros(1, 2, int(44100 * 2.0))

    monkeypatch.setattr(srv, "MODEL", FakeModel())
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    monkeypatch.setattr(srv, "prepare_model", lambda *a, **k: False)
    body = srv._generate_impl({"prompt": "x", "duration": 2.0, "steps": 8, "scale_phi": 0.7,
                               "sampler_type": "dpmpp", "cfg_interval_progress": [0.1, 0.9],
                               "schedule": {"shape": "logsnr"}})
    assert type(seen["dist_shift"]).__name__ == "ArraySchedule"
    assert seen["scale_phi"] == 0.7
    assert seen["cfg_interval"] == pytest.approx((0.1, 0.9))
    assert body["warnings"] == []
    seen.clear()
    srv._generate_impl({"prompt": "x", "duration": 2.0, "steps": 8})
    assert "scale_phi" not in seen and seen["dist_shift"] is None
