# Owner: WINTERMUTE (created 2026-10-13) -- the MODEL NOTES routes write only forge_notes
# Last edited: WINTERMUTE 2026-10-14 -- /models/rating test
import json

import pytest

import forge_testutil  # noqa: F401

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture
def client(tmp_path, monkeypatch):
    try:
        import explorer_render_server as srv
    except Exception as e:  # pragma: no cover - depends on the venv
        pytest.skip(f"render server not importable here: {e}")
    import model_db
    ov = tmp_path / "ov.json"
    ov.write_text(json.dumps({"armA": {"purpose": "auto", "status": "done"}}, indent=2) + "\n")
    monkeypatch.setattr(model_db, "OVERRIDES_PATH", ov)
    return fastapi_testclient.TestClient(srv.app), ov


def test_get_shows_census_fields_and_post_saves_only_forge_notes(client):
    c, ov = client
    r = c.get("/models/notes", params={"label": "armA"}).json()
    assert r["ok"] and r["fields"] == {"purpose": "auto", "status": "done"} and r["forge_notes"] == ""
    r = c.post("/models/notes", json={"label": "armA", "text": "keeper at ep3"}).json()
    assert r["ok"] and r["forge_notes"] == "keeper at ep3"
    d = json.loads(ov.read_text())["armA"]
    assert d["purpose"] == "auto" and d["status"] == "done" and d["forge_notes"] == "keeper at ep3"
    assert c.post("/models/notes", json={"label": "_doc", "text": "x"}).status_code == 400


def test_rating_route_saves_only_forge_rating_and_rejects_out_of_range(client):
    c, ov = client
    r = c.post("/models/rating", json={"label": "armA", "rating": 5}).json()
    assert r["ok"] and r["forge_rating"] == 5
    assert c.get("/models/notes", params={"label": "armA"}).json()["forge_rating"] == 5
    d = json.loads(ov.read_text())["armA"]
    assert d["purpose"] == "auto" and d["forge_rating"] == 5
    assert c.post("/models/rating", json={"label": "armA", "rating": 7}).status_code == 400
    assert c.post("/models/rating", json={"label": "armA", "rating": None}).json()["forge_rating"] is None
    assert "forge_rating" not in json.loads(ov.read_text())["armA"]
