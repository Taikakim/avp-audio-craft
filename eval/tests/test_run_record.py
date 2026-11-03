# Owner: THE-FINN (created 2026-11-03)
import importlib.util, json, multiprocessing as mp, os, pytest, sys
s = importlib.util.spec_from_file_location("run_record", os.path.join(os.path.dirname(__file__), "..", "..", "Misc", "run_record.py")); rr = importlib.util.module_from_spec(s); s.loader.exec_module(rr)

def meta(d): return json.load(open(os.path.join(d, "run_meta.json")))

def _seed(d, **kw):
    with open(os.path.join(d, "run_meta.json"), "w") as f: json.dump(kw, f)

@pytest.mark.parametrize("old", [None, "heard it", [{"date": "x", "verdict": "a"}], {"date": "x", "verdict": "b"}])
def test_human_verdict_keeps_every_old_shape(tmp_path, old):
    d = str(tmp_path); _seed(d, purpose="p", kim_feedback=old, result={"keep": 1}, custom="stay")
    rr.append(d, "human", "W", "sounds right", "page.html"); m = meta(d)
    assert m["result"] == {"keep": 1} and m["custom"] == "stay" and m["purpose"] == "p"
    assert len(m["evaluations"]) == 1 and m["evaluations"][0]["text"] == "sounds right"
    fb = json.dumps(m["kim_feedback"]); assert "sounds right" in fb
    if old: assert ("heard it" in fb) or ('"a"' in fb) or ('"b"' in fb)

def test_auto_result_does_not_touch_kim_feedback(tmp_path):
    d = str(tmp_path); _seed(d, kim_feedback="mine")
    rr.append(d, "auto", "F", "val 0.2", data={"val": 0.2}); m = meta(d)
    assert m["kim_feedback"] == "mine" and m["evaluations"][0]["data"] == {"val": 0.2}

def test_append_creates_a_sidecar_and_accumulates(tmp_path):
    d = str(tmp_path); rr.append(d, "auto", "F", "one"); rr.append(d, "auto", "F", "two")
    assert [e["text"] for e in meta(d)["evaluations"]] == ["one", "two"]

def test_corrupt_sidecar_stops_rather_than_replaces(tmp_path):
    d = str(tmp_path); p = os.path.join(d, "run_meta.json"); open(p, "w").write("{broken")
    with pytest.raises(ValueError): rr.append(d, "auto", "F", "x")
    assert open(p).read() == "{broken"

def test_bad_kind_refused(tmp_path):
    with pytest.raises(SystemExit): rr.append(str(tmp_path), "ear", "F", "x")

def _w(a): rr.append(a[0], "auto", "F", str(a[1]))
def test_concurrent_appends_all_land(tmp_path):
    d = str(tmp_path)
    with mp.Pool(6) as p: p.map(_w, [(d, i) for i in range(30)])
    assert sorted(int(e["text"]) for e in meta(d)["evaluations"]) == list(range(30))

def test_snapshot_keeps_both_versions_on_changed_code(tmp_path):
    d = tmp_path / "run"; d.mkdir(); sc = tmp_path / "train.py"; sc.write_text("a=1\n")
    rr.snapshot(str(d), [str(sc)]); rr.snapshot(str(d), [str(sc)]); assert (d / "_code" / "train.py").read_text() == "a=1\n"
    assert len([x for x in os.listdir(d / "_code") if x.startswith("train")]) == 1
    sc.write_text("a=2\n"); rr.snapshot(str(d), [str(sc)]); got = [x for x in os.listdir(d / "_code") if x.startswith("train")]
    assert len(got) == 2 and (d / "_code" / "train.py").read_text() == "a=1\n" and len(meta(str(d))["code_snapshot"]) == 3

def test_check_reports_gaps_and_naming(tmp_path):
    d = tmp_path / "chroma_latch_avp_d512_20261103"; d.mkdir(); miss, note = rr.check(str(d)); assert "run_meta.purpose" in miss and not note
    e = tmp_path / "C3_arm"; e.mkdir(); _, note = rr.check(str(e)); assert note
