# Owner: WINTERMUTE (created 2026-10-13)
"""forge.modelload: the time-based model-load fraction and ETA behind the top-bar load bar."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from forge import modelload  # noqa: E402


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(modelload, "HISTORY_PATH", tmp_path / "times.json")
    monkeypatch.setattr(modelload, "_loaded", False)
    modelload.end(ok=False)
    modelload._history.clear()
    yield
    modelload.end(ok=False)
    modelload._history.clear()


def test_idle_is_none():
    assert modelload.snapshot() is None


def test_first_load_uses_priors_and_has_an_eta():
    modelload.begin("m", ["free", "base model", "full finetune"])
    s = modelload.snapshot()
    assert s["stage"] == "free" and s["stage_index"] == 1 and s["stage_count"] == 3
    assert s["expected_sec"] == 76.0          # 1 + 15 + 60
    assert 74.0 < s["eta_sec"] <= 76.0
    assert s["fraction"] is not None


def test_unknown_stage_without_prior_is_indeterminate():
    modelload.begin("m", ["free", "something new"])
    s = modelload.snapshot()
    assert s["fraction"] is None and s["eta_sec"] is None and s["expected_sec"] is None


def test_measured_history_wins_and_persists_across_restart():
    modelload._history.update({("m", "free"): 1.0, ("m", "base model"): 8.0, ("m", "adapter"): 1.0})
    modelload.begin("m", ["free", "base model", "adapter"])
    modelload.stage("base model")
    t = time.time()
    s = modelload.snapshot(now=t + 4.0)
    assert s["expected_sec"] == 10.0
    assert abs(s["fraction"] - 0.5) < 0.02          # 1 s done + 4 of 8 s
    assert abs(s["eta_sec"] - 5.0) < 0.1            # 4 s left of base + 1 s adapter
    # Running long: capped below the stage end, never reads done; ETA bottoms out at what follows.
    late = modelload.snapshot(now=t + 100)
    assert late["fraction"] <= 0.86 and late["eta_sec"] == 1.0
    modelload.end()
    # A "restart": the in-memory table is gone, the file is not.
    modelload._history.clear()
    modelload._loaded = False
    modelload.begin("m", ["free", "base model"])
    # Measured (near 0 s in a test), read back from disk -- not the 15 s prior.
    assert modelload._state["expected"][1] < 1.0


def test_failed_load_does_not_teach_history():
    modelload.begin("m", ["free", "base model"])
    modelload.stage("base model")
    modelload.end(ok=False)
    assert modelload._history == {}
    assert not modelload.HISTORY_PATH.exists()
