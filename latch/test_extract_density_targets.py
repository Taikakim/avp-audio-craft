"""extract_density_targets: per-frame onsets-per-beat curve at the SA3 latent frame rate."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_density_targets import FPS, onset_per_beat_ts  # noqa: E402


def test_steady_pattern_gives_constant_onsets_per_beat():
    bpm, T = 120.0, 2048
    # two onsets per beat (eighth notes) for the whole crop
    times = np.arange(0, T / FPS, 60.0 / bpm / 2)
    ts = onset_per_beat_ts(times, bpm, T)
    assert ts.shape == (T,)
    mid = ts[200:-200]
    assert np.allclose(mid, 2.0, atol=0.15)


def test_density_follows_a_change_in_pattern():
    bpm, T = 140.0, 2048
    half = T / FPS / 2
    beat = 60.0 / bpm
    times = np.concatenate([np.arange(0, half, beat), np.arange(half, T / FPS, beat / 4)])
    ts = onset_per_beat_ts(times, bpm, T)
    assert abs(ts[300] - 1.0) < 0.2 and abs(ts[-300] - 4.0) < 0.3


def test_no_onsets_is_zero_and_bad_bpm_is_rejected():
    assert onset_per_beat_ts(np.array([]), 130.0, 512).max() == 0.0
    try:
        onset_per_beat_ts(np.array([1.0]), 0.0, 512)
    except ValueError:
        return
    raise AssertionError("bpm 0 must raise")


def test_pick_tempo_prefers_in_range_candidate_and_folds_otherwise():
    from extract_density_targets import pick_tempo
    assert pick_tempo([[69.0, 0.5], [138.0, 0.3]]) == 138.0
    assert pick_tempo([[69.0, 0.9]]) == 138.0
    assert pick_tempo([[280.0, 0.9]]) == 140.0
    assert pick_tempo([]) == 0.0
