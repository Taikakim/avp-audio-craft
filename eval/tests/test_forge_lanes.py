import numpy as np
import pytest

import forge_testutil  # noqa: F401
from forge.lanes import place_lanes, place_single

SR = 100
LIN = {"points": [0, 1 / 3, 2 / 3, 1], "curves": [0, 0, 0]}


def lanes(**over):
    base = [{"index": i, "muted": False, "solo": False, "gain": 1.0} for i in range(4)]
    for i, patch in over.items():
        base[int(i[1:])].update(patch)
    return base


def ones(n):
    return np.ones((2, n), dtype=np.float32)


def clip(cid, lane, start, dur, offset=0.0, loop=False):
    return {"id": cid, "lane": lane, "start_sec": start, "offset_sec": offset, "dur_sec": dur, "loop": loop}


def test_placement_trim_and_gain():
    audio = {"a": np.arange(300, dtype=np.float32)[None].repeat(2, 0)}
    out = place_lanes([clip("a", 1, 0.5, 1.0, offset=0.2)], lanes(L1={"gain": 0.5}), [], 400, SR,
                      lambda c: audio[c["id"]])
    assert out[0] is None and out[2] is None and out[3] is None
    buf = out[1]
    assert buf.shape == (2, 400)
    assert buf[0, 49] == 0 and buf[0, 50] == pytest.approx(10.0) and buf[0, 149] == pytest.approx(59.5)
    assert buf[0, 150] == 0


def test_loop_fills_until_next_clip():
    seg = np.arange(10, dtype=np.float32)[None].repeat(2, 0)
    out = place_lanes([clip("a", 0, 0.0, 0.1, loop=True), clip("b", 0, 0.35, 0.05)],
                      lanes(), [], 50, SR, lambda c: seg if c["id"] == "a" else ones(5) * 9)
    b = out[0][0]
    np.testing.assert_allclose(b[:35], np.tile(np.arange(10), 4)[:35])
    np.testing.assert_allclose(b[35:40], 9.0)
    assert np.all(b[40:] == 0)


def test_mute_solo():
    cs = [clip("a", 0, 0, 0.1), clip("b", 2, 0, 0.1)]
    out = place_lanes(cs, lanes(L0={"muted": True}), [], 20, SR, lambda c: ones(10))
    assert out[0] is None and out[2] is not None
    out = place_lanes(cs, lanes(L2={"solo": True}), [], 20, SR, lambda c: ones(10))
    assert out[0] is None and out[2] is not None


def test_overlap_equal_power():
    cs = [clip("a", 0, 0.0, 1.0), clip("b", 0, 0.5, 1.0)]
    ov = [{"lane": 0, "start_sec": 0.5, "end_sec": 1.0, "a_id": "a", "b_id": "b", "curve": LIN}]
    out = place_lanes(cs, lanes(), ov, 150, SR, lambda c: ones(100))[0][0]
    assert out[49] == pytest.approx(1.0)
    assert out[50] == pytest.approx(1.0)                                 # v=0: cos 0 + sin 0 = 1
    v = 25 / 49
    assert out[75] == pytest.approx(np.cos(v * np.pi / 2) + np.sin(v * np.pi / 2), abs=1e-5)
    assert out[99] == pytest.approx(1.0, abs=1e-5)                        # v=1: 0 + 1
    assert out[120] == pytest.approx(1.0)


def test_place_single():
    buf = place_single(clip("a", 3, 0.2, 0.3), 100, SR, ones(50) * 2)
    assert buf[0, 19] == 0 and buf[0, 20] == 2 and buf[0, 49] == 2 and buf[0, 50] == 0
