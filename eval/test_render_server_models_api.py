"""API-shape tests for the model/roots endpoints.

The server module imports torch and loads a model at __main__ time only, so the
FastAPI app object can be imported and exercised with TestClient on CPU.
"""
import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def client():
    import explorer_render_server as srv
    return fastapi_testclient.TestClient(srv.app)


def test_roots_lists_every_configured_root_with_availability(client):
    r = client.get("/roots")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    ids = {x["id"] for x in body["roots"]}
    assert {"local_dora", "lumi_uuid", "lumi_mantu", "control"} <= ids
    for x in body["roots"]:
        assert set(x) >= {"id", "label", "path", "available", "enabled", "priority"}


def test_models_returns_records_and_supports_family_filter(client):
    r = client.get("/models", params={"family": "adapter"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert all(m["family"] == "adapter" for m in body["models"])
    if body["models"]:
        m = body["models"][0]
        assert set(m) >= {"id", "path", "root_id", "family", "label",
                          "loadable", "load_cost_gb", "provenance"}


def test_models_by_id_round_trips(client):
    body = client.get("/models").json()
    if not body["models"]:
        pytest.skip("no checkpoints reachable - is a drive unmounted?")
    mid = body["models"][0]["id"]
    r = client.get(f"/models/{mid}")
    assert r.status_code == 200 and r.json()["model"]["id"] == mid
    assert client.get("/models/MDB-deadbeef").status_code == 404


def test_ckpts_with_no_params_keeps_its_legacy_response_shape(client):
    r = client.get("/ckpts")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        body = r.json()
        assert set(body) >= {"ok", "root", "cached", "scanned_at", "count", "ckpts"}
        if body["ckpts"]:
            assert set(body["ckpts"][0]) >= {"path", "name", "mtime", "size", "kind"}


def test_ckpts_with_root_ids_merges_roots_and_tags_each_entry(client):
    r = client.get("/ckpts", params={"root_ids": "local_dora,lumi_uuid"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "roots" in body
    if body["ckpts"]:
        assert all("root_id" in c for c in body["ckpts"])
