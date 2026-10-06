"""model_defaults(): distilled (rf_denoiser) checkpoints default to their own demo steps / cfg,
base models keep the project's 24 / 6.0 (W, 2026-10-06; KUANG's 10-05 over-drive report)."""
import types

import pytest


def _srv():
    try:
        import explorer_render_server as srv
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"real server not importable here: {e}")
    return srv


def _model(objective, demo=None):
    cfg = {"model": {"diffusion": {"diffusion_objective": objective}}}
    if demo is not None:
        cfg["training"] = {"demo": demo}
    return types.SimpleNamespace(model_config=cfg)


def test_distilled_uses_its_demo_settings(monkeypatch):
    srv = _srv()
    monkeypatch.setattr(srv, "MODEL", _model("rf_denoiser", {"demo_steps": 8, "demo_cfg_scales": [1]}))
    assert srv.model_defaults() == (8, 1.0)


def test_base_keeps_project_defaults(monkeypatch):
    srv = _srv()
    monkeypatch.setattr(srv, "MODEL", _model("rectified_flow", {"demo_steps": 50, "demo_cfg_scales": [2, 4, 7]}))
    assert srv.model_defaults() == (24, 6.0)


def test_no_model_or_config(monkeypatch):
    srv = _srv()
    monkeypatch.setattr(srv, "MODEL", None)
    assert srv.model_defaults() == (24, 6.0)
    monkeypatch.setattr(srv, "MODEL", _model("rf_denoiser"))   # no training.demo block
    assert srv.model_defaults() == (8, 1.0)


def test_explicit_request_values_win(monkeypatch):
    srv = _srv()
    monkeypatch.setattr(srv, "MODEL", _model("rf_denoiser", {"demo_steps": 8, "demo_cfg_scales": [1]}))
    req = {"steps": 30, "cfg_scale": 5.0}
    assert srv._i(req, "steps", srv.model_defaults()[0]) == 30
    assert srv._f(req, "cfg_scale", srv.model_defaults()[1]) == 5.0
