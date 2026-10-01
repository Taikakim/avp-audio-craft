import numpy as np
import pytest

import forge_testutil  # noqa: F401
from forge.analysis import analyze_audio


def click_track(bpm=120.0, seconds=16.0, sr=22050, accent_every=4):
    y = np.zeros(int(seconds * sr), dtype=np.float32)
    rng = np.random.default_rng(0)
    beat = 60.0 / bpm
    for k in range(int(seconds / beat)):
        s = int(k * beat * sr)
        amp = 1.0 if k % accent_every == 0 else 0.35
        n = int(0.012 * sr)
        y[s:s + n] += amp * rng.standard_normal(min(n, len(y) - s)).astype(np.float32)
    return np.stack([y, y])


def test_click_track_tempo_and_downbeats():
    sr = 22050
    r = analyze_audio(click_track(sr=sr), sr)
    assert r["source"] == "librosa"
    assert any(abs(c - 120.0) < 1.5 for c in r["bpm_candidates"])
    downs = np.asarray(r["downbeats_sec"])
    assert len(downs) >= 5
    assert np.median(np.diff(downs)) == pytest.approx(2.0, abs=0.06)
    phase = downs[0] % 2.0
    assert phase < 0.1 or phase > 1.9
    assert r["duration_sec"] == pytest.approx(16.0, abs=0.01)


def test_hint_wins():
    sr = 22050
    r = analyze_audio(click_track(sr=sr), sr, bpm_hint=122.4)
    assert r["bpm"] == 122.4 and r["source"] == "sidecar"


def test_silence_does_not_crash():
    r = analyze_audio(np.zeros((2, 22050 * 3), dtype=np.float32), 22050)
    assert r["duration_sec"] == pytest.approx(3.0)
    assert isinstance(r["bpm"], float)
