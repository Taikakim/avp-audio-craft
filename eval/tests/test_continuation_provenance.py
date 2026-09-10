"""A continuation must not silently be rendered by a different model than its prefix.

/longform init_latent_path continues a prior render's LATENT, but the adapter and
strength are re-specified by the caller. If the caller says nothing, the render
falls back to whatever the server has resident; if the caller says something
different from the prefix, nothing warns. Either way the tail can be a different
model than the head, with no record. This tests the recovery.
"""
import json
import sys

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import continuation as cont


def _job(tmp_path, **params):
    d = tmp_path / "20260826-010101-gen"
    d.mkdir()
    (d / "result.json").write_text(json.dumps({
        "status": "ok", "seed": 7,
        "meta": {"op": "longform", "dora_loaded": "hof", "params_echo": params}}))
    (d / "out_00.z0.npy").write_bytes(b"")
    return d / "out_00.z0.npy"


def test_nothing_next_to_the_latent_yields_an_empty_recovery(tmp_path):
    p = tmp_path / "loose.z0.npy"
    p.write_bytes(b"")
    assert cont.recover(str(p)) == {}


def test_a_sibling_result_json_yields_the_prefixs_ckpt_and_dora(tmp_path):
    z = _job(tmp_path, ckpt_path="/m/a.ckpt",
             dora={"name": "hof", "strength": 0.8})
    got = cont.recover(str(z))
    assert got["ckpt_path"] == "/m/a.ckpt"
    assert got["dora"]["strength"] == 0.8
    assert got["source"].endswith("result.json")


def test_an_mmline_sidecar_is_read_when_there_is_no_result_json(tmp_path):
    z = tmp_path / "cell_003.z0.npy"
    z.write_bytes(b"")
    (tmp_path / "cell_003.mmline.json").write_text(json.dumps(
        {"label": "dora128_everything", "ckpt": "/m/b.ckpt", "strength": 1.25}))
    got = cont.recover(str(z))
    assert got["ckpt_path"] == "/m/b.ckpt"
    assert got["dora"]["strength"] == 1.25
    assert got["label"] == "dora128_everything"


def test_a_request_that_says_nothing_ADOPTS_the_prefix(tmp_path):
    z = _job(tmp_path, ckpt_path="/m/a.ckpt", dora={"name": "hof", "strength": 0.8})
    req = {"init_latent_path": str(z), "prompt": "x"}
    warnings = cont.apply(req, cont.recover(str(z)))
    assert req["ckpt_path"] == "/m/a.ckpt"
    assert req["dora"]["name"] == "hof"
    assert any("recovered" in w for w in warnings)


def test_a_request_that_AGREES_with_the_prefix_is_silent(tmp_path):
    z = _job(tmp_path, ckpt_path="/m/a.ckpt", dora={"name": "hof", "strength": 0.8})
    req = {"ckpt_path": "/m/a.ckpt", "dora": {"name": "hof", "strength": 0.8}}
    assert cont.apply(req, cont.recover(str(z))) == []


def test_a_request_that_DISAGREES_is_obeyed_but_warned_about_by_name(tmp_path):
    # The caller wins -- deliberately rendering a tail with another model is a
    # legitimate experiment. What is not legitimate is doing it without a record.
    z = _job(tmp_path, ckpt_path="/m/a.ckpt", dora={"name": "hof", "strength": 0.8})
    req = {"ckpt_path": "/m/OTHER.ckpt"}
    warnings = cont.apply(req, cont.recover(str(z)))
    assert req["ckpt_path"] == "/m/OTHER.ckpt"
    assert len(warnings) == 1
    assert "/m/a.ckpt" in warnings[0] and "/m/OTHER.ckpt" in warnings[0]


def test_a_strength_mismatch_is_its_own_warning(tmp_path):
    z = _job(tmp_path, ckpt_path="/m/a.ckpt", dora={"name": "hof", "strength": 0.8})
    req = {"ckpt_path": "/m/a.ckpt", "dora": {"name": "hof", "strength": 1.0}}
    w = cont.apply(req, cont.recover(str(z)))
    assert len(w) == 1 and "0.8" in w[0] and "1.0" in w[0]


def test_an_unreadable_sidecar_is_not_fatal(tmp_path):
    z = tmp_path / "x.z0.npy"
    z.write_bytes(b"")
    (tmp_path / "result.json").write_text("{ not json")
    assert cont.recover(str(z)) == {}
