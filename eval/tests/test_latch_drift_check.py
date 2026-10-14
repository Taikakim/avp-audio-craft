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


def test_timbre_change_with_same_notes_is_not_flagged():
    """Kim's case: bass/mid steering changes balance and dynamics, melody and rhythm stay -> reported, not flagged."""
    from scipy.signal import butter, sosfilt
    with tempfile.TemporaryDirectory() as td:
        pairs = []
        for i, bpm in enumerate((132, 140, 146, 150)):
            x = track(bpm, True, seed=i)
            y = sosfilt(butter(2, 3000, "lowpass", fs=SR, output="sos"), x) * 2.0       # darker and louder, same hits
            pairs.append({"id": f"c{i}", "base": write(td, f"b{i}", x), "steered": write(td, f"s{i}", y.astype(np.float32))})
        res = d.compare(pairs, 1.0)
        assert all(not r["flags"] for r in res["rows"]), [r["flags"] for r in res["rows"]]
        assert abs(res["summary"]["rms_db"]["mean_delta"]) > 3.0            # it really did change -- just not as a defect
        assert res["summary"]["rhythm_sim"]["min"] > 0.9


def test_moved_hits_are_flagged_by_rhythm_sim():
    with tempfile.TemporaryDirectory() as td:
        pairs = [{"id": "c", "base": write(td, "b", track(140, False)), "steered": write(td, "s", np.roll(track(140, False), int(0.21 * SR)))},
                 {"id": "c2", "base": write(td, "b2", track(132, False, seed=2)), "steered": write(td, "s2", track(132, False, seed=2))}]
        res = d.compare(pairs, 1.0)
        assert "rhythm_sim" in res["rows"][0]["flags"] and "rhythm_sim" not in res["rows"][1]["flags"]


def test_changed_notes_are_flagged_by_chroma_sim():
    def melody(notes, dur=8.0):
        t = np.arange(int(dur * SR)) / SR
        seg = len(t) // len(notes)
        x = np.zeros(len(t), dtype=np.float32)
        for n, m in enumerate(notes):
            f = 440 * 2 ** ((m - 69) / 12)
            x[n * seg:(n + 1) * seg] = 0.4 * np.sin(2 * np.pi * f * t[n * seg:(n + 1) * seg])
        return x
    with tempfile.TemporaryDirectory() as td:
        a, b = melody([60, 64, 67, 72]), melody([61, 65, 68, 73])      # every note a semitone up: same rhythm, different pitch classes
        same = d.compare([{"id": "x", "base": write(td, "a", a), "steered": write(td, "a2", a * 0.5)}], 1.0)
        diff = d.compare([{"id": "y", "base": write(td, "a3", a), "steered": write(td, "b", b)}], 1.0)
        assert same["rows"][0]["sims"]["chroma_sim"] > 0.95 and "chroma_sim" not in same["rows"][0]["flags"]
        assert diff["rows"][0]["sims"]["chroma_sim"] < 0.5 and "chroma_sim" in diff["rows"][0]["flags"]
