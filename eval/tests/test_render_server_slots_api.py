import sys

import pytest

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def client():
    import explorer_render_server as srv
    return fastapi_testclient.TestClient(srv.app)


def test_slots_starts_empty_and_reports_the_budget(client):
    body = client.get("/slots").json()
    assert body["ok"] is True
    assert body["slots"] == []
    assert body["max_slots"] >= 1
    assert body["vram_floor_gb"] > 0
    assert body["active"] is None


def test_resolve_dora_req_passes_a_slot_through():
    import explorer_render_server as srv
    out = srv.resolve_dora_req({"dora": {"slot": 2, "strength": 1.4}})
    assert out["slot"] == 2 and out["strength"] == 1.4


def test_resolve_dora_req_without_a_slot_is_unchanged():
    import explorer_render_server as srv
    assert srv.resolve_dora_req({"dora": {"name": "hof", "strength": 0.8}})["slot"] is None
    assert srv.resolve_dora_req({"ckpt_path": "/x.ckpt"})["ckpt_path"] == "/x.ckpt"
    # no dora block at all still resolves to None, exactly as before slots existed
    assert srv.resolve_dora_req({}) is None


def test_posting_an_unknown_path_is_rejected_not_silently_ignored(client):
    r = client.post("/slots", json={"slots": [{"ckpt_path": "/does/not/exist.ckpt"}]})
    assert r.status_code >= 400
    body = r.json()
    assert "reason" in body or "detail" in body or "error" in body


def test_posting_a_fullft_path_as_a_slot_is_rejected_with_a_useful_reason(client):
    import explorer_render_server as srv
    ms = [m for m in srv.model_db.load_or_build()["models"]
          if m["family"] == "fullft" and m.get("loadable")]
    if not ms:
        pytest.skip("no fullft checkpoint reachable")
    r = client.post("/slots", json={"slots": [{"ckpt_path": ms[0]["path"]}]})
    assert r.status_code >= 400
    txt = str(r.json()).lower()
    assert "fullft" in txt or "not loaded" in txt


def test_with_lora_interval_covers_every_resident_index_in_slot_mode(monkeypatch):
    """The 'A vs B silently becomes A+B' trap, guarded at the server boundary."""
    import explorer_render_server as srv
    import adapter_slots

    class Fake:
        def load_lora(self, paths):
            pass

        def set_lora_strength(self, s, lora_index=None):
            pass

    table = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0,
                                    free_gb_fn=lambda: 99.0)
    table.apply(Fake(), [{"path": p, "label": p, "family": "adapter", "cost_gb": 0.4}
                         for p in ("a", "b", "c")])
    monkeypatch.setattr(srv, "SLOTS", table)
    monkeypatch.setattr(srv, "ACTIVE_SLOT", 1)
    monkeypatch.setattr(srv, "CURRENT_LORA_INTERVAL", (0.0, 1.0))
    cfgs = srv.with_lora_interval({})["lora_configs"]
    assert sorted(c["lora_index"] for c in cfgs) == [0, 1, 2]
    assert [c for c in cfgs if c["lora_index"] == 1][0]["interval"] == (0.0, 1.0)
    for c in cfgs:
        if c["lora_index"] != 1:
            assert c["interval"][0] > 1.0


def test_no_slots_resident_leaves_the_legacy_single_adapter_path_alone(monkeypatch):
    import explorer_render_server as srv
    import adapter_slots
    monkeypatch.setattr(srv, "SLOTS", adapter_slots.SlotTable(free_gb_fn=lambda: 99.0))
    monkeypatch.setattr(srv, "LOADED_DORA", "hof")
    monkeypatch.setattr(srv, "CURRENT_LORA_INTERVAL", (0.25, 1.0))
    cfgs = srv.with_lora_interval({})["lora_configs"]
    assert cfgs == [{"lora_index": 0, "interval": (0.25, 1.0)}]


def test_leaving_slot_mode_silences_every_resident_slot(monkeypatch):
    """A `slot: null` render came back BYTE-IDENTICAL to the previous slot-0
    render, because ACTIVE_SLOT kept its old value — "base model" was quietly
    still the last adapter. Same failure class as the A-vs-B trap."""
    import explorer_render_server as srv
    import adapter_slots

    class Fake:
        def __init__(self):
            self.strengths = {}

        def load_lora(self, paths):
            pass

        def set_lora_strength(self, s, lora_index=None):
            self.strengths[lora_index] = s

    table = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0,
                                    free_gb_fn=lambda: 99.0)
    table.apply(Fake(), [{"path": p, "label": p, "family": "adapter", "cost_gb": 0.4}
                         for p in ("a", "b")])
    monkeypatch.setattr(srv, "SLOTS", table)
    monkeypatch.setattr(srv, "ACTIVE_SLOT", 0)
    monkeypatch.setattr(srv, "CURRENT_LORA_INTERVAL", (0.0, 1.0))
    # the render-time view with nothing active: every index present, all off
    cfgs = srv.SLOTS.lora_configs(None)
    assert sorted(c["lora_index"] for c in cfgs) == [0, 1]
    for c in cfgs:
        assert c["interval"][0] > 1.0
    assert dict(srv.SLOTS.strengths(None, 1.0)) == {0: 0.0, 1: 0.0}
