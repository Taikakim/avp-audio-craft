# Owner: GHOST-NOTE (created 2026-10-14)
"""Positive/negative controls for latch_drift_check: a feature that really moved must be seen; one that did not must not be."""
import os
import sys
import tempfile

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import latch_drift_check as d  # noqa: E402

SR = 22050


def track(bpm, hats=False, dur=16.0, seed=0, gain=1.0):
    rng = np.random.default_rng(seed)
    x = np.zeros(int(dur * SR), dtype=np.float32)
    beat = 60.0 / bpm
    def burst(t0, n, f0, amp):
        i = int(t0 * SR)
        k = np.arange(n)
        x[i:i + n] += (amp * np.exp(-k / (n / 5)) * np.sin(2 * np.pi * f0 * k / SR))[: max(0, len(x) - i)] if i + n <= len(x) else 0
    for b in range(int(dur / beat)):
        burst(b * beat, 2000, 70, 0.8)
    if hats:
        for s in range(int(dur / (beat / 4))):
            i = int(s * beat / 4 * SR)
            n = 600
            if i + n < len(x):
                x[i:i + n] += (0.3 * rng.standard_normal(n) * np.exp(-np.arange(n) / 120)).astype(np.float32)
    return (gain * x).astype(np.float32)


def write(td, name, x):
    p = os.path.join(td, name + ".wav")
    sf.write(p, x, SR)
    return p


def test_hat_barrage_is_flagged_and_tempo_is_not():
    with tempfile.TemporaryDirectory() as td:
        pairs = []
        for i, bpm in enumerate((132, 140, 146, 150)):     # spread of base material so z has a denominator
            pairs.append({"id": f"c{i}", "base": write(td, f"b{i}", track(bpm, False, seed=i)),
                          "steered": write(td, f"s{i}", track(bpm, True, seed=i)), "target": "onset_rate"})
        res = d.compare(pairs, 1.0)
        assert res["summary"]["hat_rate"]["n_flagged"] >= 3, res["summary"]["hat_rate"]
        assert abs(res["summary"]["bpm"]["mean_delta"]) < 2.0, res["summary"]["bpm"]


def test_tempo_drift_is_flagged_and_hats_are_not():
    with tempfile.TemporaryDirectory() as td:
        pairs = []
        for i, bpm in enumerate((132, 140, 146, 150)):
            pairs.append({"id": f"c{i}", "base": write(td, f"b{i}", track(bpm, False, seed=i)),
                          "steered": write(td, f"s{i}", track(bpm * 1.08, False, seed=i))})
        res = d.compare(pairs, 1.0)
        assert res["summary"]["bpm"]["mean_delta"] > 5.0, res["summary"]["bpm"]
        assert abs(res["summary"]["hat_rate"]["mean_delta"]) < 1.0


def test_identical_pairs_flag_nothing():
    with tempfile.TemporaryDirectory() as td:
        pairs = [{"id": f"c{i}", "base": write(td, f"b{i}", track(b, True, seed=i)), "steered": write(td, f"s{i}", track(b, True, seed=i))}
                 for i, b in enumerate((132, 146))]
        res = d.compare(pairs, 1.0)
        assert all(not r["flags"] for r in res["rows"])
