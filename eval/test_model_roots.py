import json
from pathlib import Path

import pytest

import model_roots


def _cfg(tmp_path, mount_candidates, marker):
    return {
        "version": 1,
        "mounts": {"DRIVE": {"candidates": mount_candidates, "marker": marker}},
        "roots": [
            {"id": "runs", "label": "runs", "path": "${DRIVE}/runs", "priority": 20},
            {"id": "other", "label": "other", "path": "${DRIVE}/other", "priority": 10},
        ],
    }


def test_resolve_mounts_picks_the_candidate_carrying_the_marker(tmp_path):
    good = tmp_path / "Mantu1"
    (good / "sa3_lora_runs").mkdir(parents=True)
    bad = tmp_path / "Mantu"
    bad.mkdir()
    cfg = _cfg(tmp_path, [str(bad), str(good)], "sa3_lora_runs")
    assert model_roots.resolve_mounts(cfg) == {"DRIVE": str(good)}


def test_resolve_mounts_reports_none_when_no_candidate_is_mounted(tmp_path):
    cfg = _cfg(tmp_path, [str(tmp_path / "nope")], "sa3_lora_runs")
    assert model_roots.resolve_mounts(cfg) == {"DRIVE": None}


def test_expand_returns_none_for_an_unresolved_mount():
    assert model_roots.expand("${DRIVE}/runs", {"DRIVE": None}) is None
    assert model_roots.expand("${DRIVE}/runs", {"DRIVE": "/mnt/d"}) == "/mnt/d/runs"


def test_resolve_roots_marks_availability_and_sorts_by_priority(tmp_path):
    drive = tmp_path / "Mantu"
    (drive / "sa3_lora_runs").mkdir(parents=True)
    (drive / "runs").mkdir()
    cfg = _cfg(tmp_path, [str(drive)], "sa3_lora_runs")
    roots = model_roots.resolve_roots(cfg)
    assert [r.id for r in roots] == ["runs", "other"]
    assert roots[0].available is True and roots[0].path == str(drive / "runs")
    assert roots[1].available is False       # ${DRIVE}/other does not exist
    assert roots[1].path == str(drive / "other")


def test_disabled_roots_are_returned_but_flagged(tmp_path):
    drive = tmp_path / "Mantu"
    (drive / "sa3_lora_runs").mkdir(parents=True)
    (drive / "runs").mkdir()
    cfg = _cfg(tmp_path, [str(drive)], "sa3_lora_runs")
    cfg["roots"][0]["enabled"] = False
    roots = model_roots.resolve_roots(cfg)
    assert roots[0].enabled is False


def test_shipped_config_parses_and_declares_every_known_root():
    cfg = model_roots.load_config()
    ids = {r["id"] for r in cfg["roots"]}
    assert {"local_dora", "lumi_uuid", "lumi_mantu", "control"} <= ids
    for r in cfg["roots"]:
        assert r["path"].startswith("${"), f"{r['id']} must template a mount, not hardcode a drive"


def test_load_config_accepts_an_explicit_path(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"version": 1, "mounts": {}, "roots": []}))
    assert model_roots.load_config(p)["roots"] == []
