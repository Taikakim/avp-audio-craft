import time

import pytest

import forge_testutil  # noqa: F401

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    # Real server on a GPU box, a faithful stub elsewhere (see forge_testutil.get_server).
    return forge_testutil.get_server(tmp_path_factory)


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


def test_generate_folds_lane_chain(srv, client, monkeypatch):
    """A plain generate is steered by its lane chain (no A2A needed); a lane LoRA that is ON goes
    in as `dora` and so wins over the top-bar ckpt_path."""
    seen = {}

    def fake_generate(req):
        seen.update(req)
        return {"status": "ok", "job_id": "j", "files": [], "latents": [], "urls": [], "seed": 1,
                "timings": {"total_sec": 0.0, "per_stage": {}}, "warnings": [], "meta": {}}

    monkeypatch.setattr(srv, "_generate_impl", fake_generate)
    monkeypatch.setitem(srv.HEADS, "rms_energy_bass", {"default_gain": 512.0})
    chain = {"latch_on": True, "lora_on": True, "film_on": False, "bungee_on": False,
             "slots": [{"head": "rms_energy_bass", "kind": "constant", "value": 1.0, "weight": 1.0,
                        "start_pct": 0.0, "end_pct": 1.0}, {"head": None, "weight": 0}],
             "lora": {"ckpt_path": "/lane.ckpt", "slot": None, "strength": 0.5}}
    payload = {"prompt": "x", "duration": 8, "steps": 4, "ckpt_path": "/top.ckpt", "chain": chain}
    jid = client.post("/forge/jobs", json={"op": "generate", "payload": payload}).json()["job_id"]
    assert poll(client, jid)["state"] == "done"
    assert "chain" not in seen
    assert seen["latch"][0]["head"] == "rms_energy_bass" and seen["latch"][0]["gain"] == 512.0
    assert seen["dora"] == {"ckpt_path": "/lane.ckpt", "strength": 0.5}
    assert srv.resolve_dora_req(seen)["ckpt_path"] == "/lane.ckpt"

    seen.clear()
    jid = client.post("/forge/jobs", json={"op": "generate", "payload": {
        "prompt": "x", "duration": 8, "steps": 4, "ckpt_path": "/top.ckpt", "chain": None}}).json()["job_id"]
    poll(client, jid)
    assert seen.get("latch") is None and srv.resolve_dora_req(seen)["ckpt_path"] == "/top.ckpt"


def test_step_t_accepts_scalar_and_batched_t():
    import torch
    import explorer_render_server as s
    assert s.step_t(torch.tensor(0.25)) == 0.25        # pingpong (medium): 0-dim
    assert s.step_t(torch.tensor([0.5, 0.5])) == 0.5   # euler/rf: [B]
    assert s.step_t([0.75]) == 0.75 and s.step_t(0.1) == 0.1


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
