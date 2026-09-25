"""score_and_publish must scope sanity + CLAP from what is STAGED, not from manifest_live.jsonl.

WHY: manifest_live.jsonl is only rewritten by leg_tables, the last leg. On 2026-09-26 the
goa3_avp_r256 step=6340 pass read the stale served copy in leg_sanity (checked 28 old clips,
none of the 108 new) and in leg_gpu (CLAP scope held 0 of the 108). The fix derives the view
from the raw manifest + the m4a files on disk.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SP = Path(__file__).resolve().parents[1] / "score_and_publish.py"


@pytest.fixture
def sp(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("score_and_publish_under_test", SP)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "MATRIX", tmp_path)
    monkeypatch.setattr(mod, "MANIFEST", tmp_path / "manifest_live.jsonl")
    monkeypatch.setattr(mod, "RAW_MANIFEST", tmp_path / "manifest.jsonl")
    return mod


def _entry(model, pid, native=False):
    e = {"model": model, "ckpt": "step=1", "cfg": 7.0, "strength": 1.0,
         "prompt_id": pid, "file": f"{model}__{pid}.m4a"}
    if native:
        e["duration_mode"] = "native"
    return e


def test_new_cells_visible_before_live_manifest_is_rebuilt(sp, tmp_path):
    old = _entry("armX_old", "p0")
    new = [_entry("armX_new", f"p{i}") for i in range(3)]
    unstaged = _entry("armX_new", "p9")          # manifest runs ahead of its transcode
    native = _entry("armX_new", "pn", native=True)
    (tmp_path / "manifest.jsonl").write_text(
        "\n".join(json.dumps(e) for e in [old, *new, unstaged, native]) + "\n")
    (tmp_path / "manifest_live.jsonl").write_text(json.dumps(old) + "\n")   # stale served copy
    for e in [old, *new, native]:
        (tmp_path / e["file"]).write_bytes(b"x")

    assert sp.manifest_models("armX_new") == ["armX_new"]
    out = tmp_path / "scope.jsonl"
    assert sp.scoped_manifest("armX_new", out) == 3          # native + unstaged excluded
    files = {json.loads(l)["file"] for l in out.read_text().split("\n") if l.strip()}
    assert files == {e["file"] for e in new}


def test_falls_back_to_live_manifest_without_raw(sp, tmp_path):
    e = _entry("armY", "p0")
    (tmp_path / "manifest_live.jsonl").write_text(json.dumps(e) + "\n")
    (tmp_path / e["file"]).write_bytes(b"x")
    assert sp.manifest_models("armY") == ["armY"]
