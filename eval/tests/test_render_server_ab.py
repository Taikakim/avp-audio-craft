import sys

import pytest

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def client():
    import explorer_render_server as srv
    return fastapi_testclient.TestClient(srv.app)


def test_ab_rejects_a_slot_that_is_not_resident(client):
    r = client.post("/ab", json={"prompt": "x", "duration": 5, "ab": {"slots": [0, 9]}})
    assert r.status_code >= 400
    assert "resident" in str(r.json()).lower()


def test_ab_requires_at_least_two_arms(client):
    r = client.post("/ab", json={"prompt": "x", "duration": 5, "ab": {"slots": [0]}})
    assert r.status_code >= 400
    assert "two arms" in str(r.json()).lower()


def test_ab_with_no_slots_block_is_refused_rather_than_rendering_once(client):
    r = client.post("/ab", json={"prompt": "x", "duration": 5})
    assert r.status_code >= 400


def test_null_is_accepted_as_the_control_arm(client, monkeypatch):
    """`null` = the bare base. An adapter that "sounds better" against nothing is
    not a finding, so the control arm must always be expressible."""
    import explorer_render_server as srv
    calls = []

    def fake_impl(req):
        calls.append(req)
        return {"status": "ok", "job_id": f"j{len(calls)}", "files": ["/tmp/a.wav"],
                "urls": ["/audio/j/a.wav"], "latents": [], "meta": {"model_rebuilt": False}}

    monkeypatch.setattr(srv, "_generate_impl", fake_impl)
    r = client.post("/ab", json={"prompt": "x", "duration": 5, "seed": 42,
                                 "ab": {"slots": [None, None]}})
    assert r.status_code == 200
    body = r.json()
    assert [a["slot"] for a in body["arms"]] == [None, None]
    assert body["arms"][0]["label"] == "base (no adapter)"
    # ONE seed, reused, so the arms differ only by the model
    assert body["seed"] == 42
    assert [c["seed"] for c in calls] == [42, 42]


def test_a_resolved_seed_is_shared_by_every_arm(client, monkeypatch):
    import explorer_render_server as srv
    calls = []

    def fake_impl(req):
        calls.append(req)
        return {"status": "ok", "job_id": "j", "files": [], "urls": [], "latents": [],
                "meta": {}}

    monkeypatch.setattr(srv, "_generate_impl", fake_impl)
    body = client.post("/ab", json={"prompt": "x", "duration": 5, "seed": -1,
                                    "ab": {"slots": [None, None, None]}}).json()
    seeds = {c["seed"] for c in calls}
    assert len(seeds) == 1 and body["seed"] in seeds
    assert body["seed"] != -1, "the seed must be resolved once, not left for each arm"


def test_a_failing_arm_does_not_lose_the_others(client, monkeypatch):
    import explorer_render_server as srv
    n = {"i": 0}

    def flaky(req):
        n["i"] += 1
        if n["i"] == 1:
            raise RuntimeError("CUDA OOM")
        return {"status": "ok", "job_id": "j", "files": ["/tmp/b.wav"], "urls": [],
                "latents": [], "meta": {}}

    monkeypatch.setattr(srv, "_generate_impl", flaky)
    body = client.post("/ab", json={"prompt": "x", "duration": 5,
                                    "ab": {"slots": [None, None]}}).json()
    assert body["ok"] is True
    assert "CUDA OOM" in body["arms"][0]["error"]
    assert body["arms"][1]["files"] == ["/tmp/b.wav"]
    assert any("arm 0" in w for w in body["warnings"])


def test_the_ckpt_path_is_dropped_because_the_slot_is_the_model(client, monkeypatch):
    import explorer_render_server as srv
    calls = []

    def fake_impl(req):
        calls.append(req)
        return {"status": "ok", "job_id": "j", "files": [], "urls": [], "latents": [],
                "meta": {}}

    monkeypatch.setattr(srv, "_generate_impl", fake_impl)
    client.post("/ab", json={"prompt": "x", "duration": 5, "ckpt_path": "/some/other.ckpt",
                             "ab": {"slots": [None, None]}})
    assert all("ckpt_path" not in c for c in calls)
