"""A measured curve must reach the guidance layer, not just a kind+value shape.

model.py has always consumed cfg["target_raw"], but resolve_latch never forwarded
it, so /generate could only request constant/ramp/beat_grid. That made the decisive
question about trajectory conditioning -- "does a REAL envelope transfer its rhythm
to a differently-prompted render?" -- unaskable through the server.
"""
import sys

import pytest

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import explorer_render_server as srv


HEAD_DIR = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium"


@pytest.fixture(autouse=True)
def _registry(monkeypatch):
    """HEADS is populated by scan_latch_heads() at server boot, which loads 17
    checkpoints off disk. Inject the two entries these tests name instead."""
    monkeypatch.setattr(srv, "HEADS", {
        n: {"name": n, "family": "medium", "default_gain": 512.0,
            "path": f"{HEAD_DIR}/latch_sa3_{n}_best.pt",
            "target_kind_default": "constant", "value_default": -30.0}
        for n in ("onset_envelope", "rms_drums")})


def _slot(**kw):
    s = {"head": "onset_envelope", "gain": 512.0}
    s.update(kw)
    return s


def test_a_measured_curve_reaches_the_config():
    curve = [[0.0, 1.0, 0.0, 1.0]]
    cfgs, hp = srv.resolve_latch([_slot(target_raw=curve)], {})
    assert cfgs[0]["target_raw"] == curve


def test_kind_and_value_are_dropped_when_a_curve_is_given():
    """Otherwise the two could silently disagree and nobody would know which won."""
    cfgs, _ = srv.resolve_latch([_slot(target_raw=[[0.0, 1.0]], kind="constant",
                                       value=-30.0)], {})
    assert "kind" not in cfgs[0] and "value" not in cfgs[0]


def test_the_ordinary_kind_value_path_is_untouched():
    cfgs, _ = srv.resolve_latch([_slot(kind="constant", value=-12.0)], {})
    assert cfgs[0]["kind"] == "constant" and cfgs[0]["value"] == -12.0
    assert "target_raw" not in cfgs[0]


def test_a_degenerate_curve_is_refused_rather_than_silently_broadcast():
    with pytest.raises(ValueError):
        srv.resolve_latch([_slot(target_raw=[[0.5]])], {})


def test_a_curve_survives_alongside_a_second_ordinary_slot():
    cfgs, _ = srv.resolve_latch(
        [_slot(target_raw=[[0.0, 1.0]]), _slot(head="rms_drums", kind="constant",
                                               value=-20.0, gain=256.0)], {})
    assert "target_raw" in cfgs[0] and cfgs[1]["value"] == -20.0
    # gain normalisation still applies: per-slot weight = gain / slot-1 gain
    assert cfgs[1]["weight"] == pytest.approx(0.5)
