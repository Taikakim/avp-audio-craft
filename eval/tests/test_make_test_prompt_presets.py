# Owner: WINTERMUTE (created 2026-10-13)
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forge"))
import make_test_prompt_presets as mt  # noqa: E402


def _rows(*specs):
    return [{"prompt_id": "p", "prompt_text": t, "seed": s, "cfg": c, "steps": 24, "model": m}
            for t, s, c, m in specs]


def test_majority_text_and_seed_win_and_the_comment_names_the_rest():
    rows = _rows(("goa", 7, 7.0, "a"), ("goa", 7, 1.0, "b"), ("goa", 7, 16.0, "a"),
                 ("goa old", 7, 7.0, "a"), ("goa", 9, 7.0, "c"))
    p = mt.preset_for("p", rows)
    assert (p["prompt"], p["seed"], p["cfg_scale"], p["duration_sec"]) == ("goa", 7, 7.0, 20.0)
    assert "MULTI-SEED" in p["notes"] and "9 (1 clips)" in p["notes"]
    assert "text drifted" in p["notes"] and "Board CFGs 1, 7, 16" in p["notes"]


def test_writes_one_test_preset_per_prompt_id(tmp_path):
    mf = tmp_path / "manifest.jsonl"
    mf.write_text("\n".join(json.dumps(r) for r in
                            _rows(("techno music", 1234, 7.0, "a")) +
                            [{**_rows(("aavepyora", 1234, 7.0, "a"))[0], "prompt_id": "trig2"}]) + "\nnot json\n")
    assert mt.main(["--manifest", str(mf), "--out", str(tmp_path / "out")]) == 0
    names = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert names == ["test-p.json", "test-trig2.json"]
    assert "Retired id" in json.loads((tmp_path / "out" / "test-trig2.json").read_text())["notes"]
