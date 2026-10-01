import time

import pytest

import forge_testutil  # noqa: F401

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    # Prefer the REAL server (GPU box). On a CPU-only box (no torch) fall back to the stub that
    # mirrors the three M2 T8 hooks, so the /forge routes are still exercised end to end.
    try:
        import explorer_render_server as srv
        return srv
    except ModuleNotFoundError:
        return forge_testutil.make_stub_server(tmp_path_factory.mktemp("stub_out"))


@pytest.fixture
def client(srv, monkeypatch, tmp_path):
    import forge_api
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    forge_api.reset_queue()
    return fastapi_testclient.TestClient(srv.app)


def poll(client, jid, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        body = client.get(f"/forge/jobs/{jid}").json()
        if body["state"] in ("done", "error", "cancelled"):
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_generate_job_roundtrip(srv, client, monkeypatch):
    seen = {}

    def fake_generate(req):
        seen.update(req)
        srv.make_log_cb(req["steps"])({"t": [0.5]})
        return {"status": "ok", "job_id": "j", "files": [], "latents": [], "urls": [], "seed": 1,
                "timings": {"total_sec": 0.0, "per_stage": {}}, "warnings": [], "meta": {}}

    monkeypatch.setattr(srv, "_generate_impl", fake_generate)
    r = client.post("/forge/jobs", json={"op": "generate", "payload": {"prompt": "x", "duration": 8, "steps": 4}})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["ok"] is True and body["job_id"].startswith("forge-") and body["position"] == 0
    done = poll(client, body["job_id"])
    assert done["state"] == "done" and done["result"]["seed"] == 1
    assert done["payload"] == {"prompt": "x", "duration": 8, "steps": 4}
    assert seen["prompt"] == "x"
    listed = client.get("/forge/jobs?limit=5").json()
    assert listed["ok"] and listed["jobs"][0]["job_id"] == body["job_id"]


@pytest.mark.parametrize("body,status,needle", [
    ({"op": "generate", "payload": {"prompt": "x", "duration": 200}}, 400, "capped at 184 s"),
    ({"op": "nope", "payload": {}}, 400, "unknown op"),
    ({"op": "generate", "payload": [1]}, 400, "payload"),
    ({"payload": {}}, 400, "op"),
])
def test_submit_validation(client, body, status, needle):
    r = client.post("/forge/jobs", json=body)
    assert r.status_code == status
    assert r.json()["ok"] is False and needle in r.json()["error"]


def test_unknown_job_404(client):
    assert client.get("/forge/jobs/forge-x").status_code == 404
    assert client.delete("/forge/jobs/forge-x").status_code == 404


def test_error_job(srv, client, monkeypatch):
    def boom(req):
        raise RuntimeError("kaput")
    monkeypatch.setattr(srv, "_decode_impl", boom)
    jid = client.post("/forge/jobs", json={"op": "decode", "payload": {"crop_id": "1"}}).json()["job_id"]
    done = poll(client, jid)
    assert done["state"] == "error" and done["error"] == "kaput"


def test_log_and_status_progress(srv, client):
    srv.log("forge-log-probe")
    body = client.get("/forge/log?since=0").json()
    assert body["ok"] and any(line["text"].endswith("forge-log-probe") for line in body["lines"])
    last = body["seq"]
    assert client.get(f"/forge/log?since={last}").json()["lines"] == []
    st = client.get("/status").json()
    assert "progress" in st
