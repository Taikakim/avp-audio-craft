import json

import pytest

import forge_testutil  # noqa: F401
from forge import backbone


def make_hub(tmp_path, model_id, objective):
    d = tmp_path / f"models--stabilityai--stable-audio-3-{model_id}" / "snapshots" / "abc"
    d.mkdir(parents=True)
    (d / "model_config.json").write_text(json.dumps({"model": {"diffusion": {"diffusion_objective": objective}}}))


def test_listing_from_hub(tmp_path):
    make_hub(tmp_path, "medium", "rf_denoiser")
    rows = backbone.listing(tmp_path)
    assert [r["id"] for r in rows] == ["medium", "medium-base", "small-music", "small-music-base"]
    assert rows[0] == {"id": "medium", "objective": "rf_denoiser", "cached": True}
    assert rows[1] == {"id": "medium-base", "objective": "rectified_flow", "cached": False}


def test_hub_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    assert backbone.hub_dir() == tmp_path


def test_routes(monkeypatch, tmp_path, tmp_path_factory):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    srv = forge_testutil.get_server(tmp_path_factory)
    import forge_api
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    make_hub(tmp_path, "medium-base", "rectified_flow")
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    forge_api.reset_queue()
    c = fastapi_testclient.TestClient(srv.app)
    body = c.get("/forge/backbone").json()
    assert body["ok"] and [r["id"] for r in body["available"]][0] == "medium"
    assert c.post("/forge/backbone", json={"id": "large"}).status_code == 400
    r = c.post("/forge/backbone", json={"id": "medium"})
    assert r.status_code == 400 and "local HF cache" in r.json()["error"]
    srv.GPU_LOCK.acquire()
    try:
        assert c.post("/forge/backbone", json={"id": "medium-base"}).status_code == 409
    finally:
        srv.GPU_LOCK.release()


def test_failed_switch_restores_previous(monkeypatch):
    """Review 2026-10-01: a prepare_model failure must not leave ARGS.model on the bad id with no
    model loaded. The previous backbone is rebuilt and the error names both."""
    import threading
    from types import SimpleNamespace
    import forge_api
    from forge.contract import ForgeError

    loaded = []

    def prepare_model(_dora, _film):
        if srv.ARGS.model == "medium-base":
            raise RuntimeError("partial snapshot")
        loaded.append(srv.ARGS.model)
        srv.MODEL = object()

    srv = SimpleNamespace(ARGS=SimpleNamespace(model="medium"), MODEL=object(), GPU_LOCK=threading.Lock(),
                          SLOTS=SimpleNamespace(slots=[]), prepare_model=prepare_model, log=lambda *_: None)
    monkeypatch.setattr(forge_api, "SRV", srv)
    with pytest.raises(ForgeError) as ei:
        forge_api._switch_backbone("medium-base")
    assert "restored medium" in str(ei.value)
    assert srv.ARGS.model == "medium" and srv.MODEL is not None and loaded == ["medium"]
    assert not srv.GPU_LOCK.locked()
