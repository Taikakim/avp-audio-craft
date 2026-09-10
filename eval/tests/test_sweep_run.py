import json
import sys

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import sweep_run

import pytest


SPEC = {"name": "t", "payload": {"prompt": "goa", "duration": 10.0, "steps": 8,
                                 "cfg_scale": 7.0, "dora": {"name": "hof", "strength": 1.0}},
        "axes": {"strength": [0.5, 1.0]}, "seeds": [7]}


def _ok_post(calls):
    def post(url, payload, timeout=None):
        calls.append(payload)
        n = len(calls)
        return {"status": "ok", "job_id": f"gen-{n}", "seed": payload.get("seed", 1),
                "files": [f"/tmp/j{n}/out_00.wav"], "latents": [f"/tmp/j{n}/out_00.z0.npy"],
                "meta": {"dora_loaded": "hof"}, "timings": {"total_sec": 1.0}}
    return post


def test_a_dry_run_posts_nothing_and_reports_the_cell_count(tmp_path):
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls), dry_run=True)
    assert r["planned"] == 2 and r["rendered"] == 0 and calls == []


def test_every_cell_is_posted_once_and_written_once(tmp_path):
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls))
    assert r["rendered"] == 2 and len(calls) == 2
    lines = (tmp_path / "manifest.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2 and all(json.loads(x)["status"] == "ok" for x in lines)


def test_rerunning_skips_everything_already_done(tmp_path):
    sweep_run.run(SPEC, tmp_path, post=_ok_post([]))
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls))
    assert r["skipped"] == 2 and r["rendered"] == 0 and calls == []


def test_force_reruns_everything(tmp_path):
    sweep_run.run(SPEC, tmp_path, post=_ok_post([]))
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls), force=True)
    assert r["rendered"] == 2 and len(calls) == 2


def test_a_failed_cell_is_recorded_as_error_and_retried_next_run(tmp_path):
    def bad(url, payload, timeout=None):
        raise RuntimeError("server said no")
    r = sweep_run.run(SPEC, tmp_path, post=bad)
    assert r["errors"] == 2 and r["rendered"] == 0
    rec = json.loads((tmp_path / "manifest.jsonl").read_text().strip().split("\n")[0])
    assert rec["status"] == "error" and "server said no" in rec["error"]
    calls = []
    sweep_run.run(SPEC, tmp_path, post=_ok_post(calls))
    assert len(calls) == 2, "errors must be retried, not treated as done"


def test_one_bad_cell_does_not_abort_the_rest(tmp_path):
    n = {"i": 0}

    def flaky(url, payload, timeout=None):
        n["i"] += 1
        if n["i"] == 1:
            raise RuntimeError("boom")
        return {"status": "ok", "job_id": "g", "seed": 7, "files": ["/tmp/a.wav"],
                "latents": ["/tmp/a.z0.npy"], "meta": {}, "timings": {}}
    r = sweep_run.run(SPEC, tmp_path, post=flaky)
    assert r["rendered"] == 1 and r["errors"] == 1


def test_a_response_without_latents_is_flagged_not_dropped(tmp_path):
    def no_z0(url, payload, timeout=None):
        return {"status": "ok", "job_id": "g", "seed": 7, "files": ["/tmp/a.wav"],
                "meta": {}, "timings": {}}
    r = sweep_run.run(SPEC, tmp_path, post=no_z0)
    rec = json.loads((tmp_path / "manifest.jsonl").read_text().strip().split("\n")[0])
    assert rec["status"] == "ok" and rec["z0_missing"] is True
    assert r["z0_missing"] == 2


def test_the_manifest_stores_the_exact_payload_that_was_posted(tmp_path):
    calls = []
    sweep_run.run(SPEC, tmp_path, post=_ok_post(calls))
    recs = [json.loads(x) for x in
            (tmp_path / "manifest.jsonl").read_text().strip().split("\n")]
    assert [r["payload"]["dora"]["strength"] for r in recs] == \
           [c["dora"]["strength"] for c in calls]


def test_limit_caps_the_number_of_renders(tmp_path):
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls), limit=1)
    assert r["rendered"] == 1 and len(calls) == 1


def test_an_invalid_spec_raises_before_any_render(tmp_path):
    calls = []
    with pytest.raises(ValueError):
        sweep_run.run({"payload": {"prompt": "x"}, "axes": {"cfg": []}}, tmp_path,
                      post=_ok_post(calls))
    assert calls == []


def test_a_corrupt_manifest_line_does_not_break_resume(tmp_path):
    sweep_run.run(SPEC, tmp_path, post=_ok_post([]))
    with open(tmp_path / "manifest.jsonl", "a") as f:
        f.write("{ not json\n")
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls))
    assert r["skipped"] == 2 and calls == []


# --- preset x models -----------------------------------------------------------

MODELS = [
    {"id": "MDB-aaaa1111", "label": "dorlor_ab_r128", "path": "/m/a.ckpt",
     "family": "adapter", "loadable": True},
    {"id": "MDB-bbbb2222", "label": "fullft_avp_subloss", "path": "/m/b.ckpt",
     "family": "fullft", "loadable": True},
    {"id": "MDB-cccc3333", "label": "morphcond_riffer", "path": "/m/c.pt",
     "family": "control", "loadable": False},
]


def _fetch(_url=None):
    return {"models": MODELS}


def test_models_resolve_by_id_label_or_path():
    got = sweep_run.resolve_models(
        {"models": ["MDB-aaaa1111", "fullft_avp_subloss", "/m/a.ckpt"]}, fetch=_fetch)
    assert [m["label"] for m in got] == ["dorlor_ab_r128", "fullft_avp_subloss",
                                         "dorlor_ab_r128"]


def test_an_unknown_model_fails_before_any_render():
    with pytest.raises(ValueError) as e:
        sweep_run.resolve_models({"models": ["MDB-aaaa1111", "typo"]}, fetch=_fetch)
    assert "typo" in str(e.value)


def test_a_non_loadable_family_is_refused_with_its_family_named():
    with pytest.raises(ValueError) as e:
        sweep_run.resolve_models({"models": ["morphcond_riffer"]}, fetch=_fetch)
    assert "control" in str(e.value)


def test_a_preset_across_two_models_yields_one_cell_per_model(tmp_path):
    calls = []
    spec = {"name": "x", "payload": {"prompt": "goa", "duration": 10.0},
            "models": ["MDB-aaaa1111", "MDB-bbbb2222"], "seeds": [7]}
    r = sweep_run.run(spec, tmp_path, post=_ok_post(calls), fetch=_fetch)
    assert r["rendered"] == 2
    assert sorted(c["ckpt_path"] for c in calls) == ["/m/a.ckpt", "/m/b.ckpt"]


def test_the_model_coordinate_is_the_label_not_the_path(tmp_path):
    spec = {"name": "x", "payload": {"prompt": "goa", "duration": 10.0},
            "models": ["MDB-aaaa1111"], "seeds": [7]}
    sweep_run.run(spec, tmp_path, post=_ok_post([]), fetch=_fetch)
    rec = json.loads((tmp_path / "manifest.jsonl").read_text().strip())
    assert rec["coords"]["model"] == "dorlor_ab_r128"
    assert rec["payload"]["ckpt_path"] == "/m/a.ckpt"


def test_models_cross_with_other_axes(tmp_path):
    calls = []
    spec = {"name": "x", "payload": {"prompt": "goa", "duration": 10.0,
                                     "dora": {"name": "none", "strength": 1.0}},
            "models": ["MDB-aaaa1111", "MDB-bbbb2222"],
            "axes": {"strength": [1.0, 1.5]}, "seeds": [7]}
    r = sweep_run.run(spec, tmp_path, post=_ok_post(calls), fetch=_fetch)
    assert r["rendered"] == 4


def test_the_cell_id_is_keyed_on_the_LABEL_so_a_remount_does_not_break_resume(tmp_path):
    # The same model under a different mount point (Mantu vs Mantu1) must resume,
    # not re-render. Keying cell_id on the path would silently redo the sweep.
    spec = {"name": "x", "payload": {"prompt": "goa", "duration": 10.0},
            "models": ["MDB-aaaa1111"], "seeds": [7]}
    sweep_run.run(spec, tmp_path, post=_ok_post([]), fetch=_fetch)
    moved = [dict(MODELS[0], path="/OTHERMOUNT/a.ckpt")] + MODELS[1:]
    calls = []
    r = sweep_run.run(spec, tmp_path, post=_ok_post(calls),
                      fetch=lambda _u=None: {"models": moved})
    assert r["skipped"] == 1 and calls == []
