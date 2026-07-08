"""Tests for window_onset_density_active — the outro-cheat fix (Kim 2026-07-07):
onset density measured over ACTIVE time only, so empty tails / outro silence
can't fake a low density."""
import numpy as np
import pytest

from sa3_control.dataset import window_onset_density, window_onset_density_active

FR = 10.767


def _env_with_onsets(n_frames, onset_every, active_mask=None):
    """Synthetic onset envelope: bumps every `onset_every` frames where active."""
    env = np.random.default_rng(0).uniform(0.0, 0.05, n_frames).astype(np.float32)
    rms = np.zeros(n_frames, dtype=np.float32)
    active = active_mask if active_mask is not None else np.ones(n_frames, bool)
    rms[active] = 0.3
    for i in range(2, n_frames - 2, onset_every):
        if active[i]:
            env[i] = 1.0
    return env, rms


def test_matches_plain_when_fully_active():
    env, rms = _env_with_onsets(430, 6)          # ~40s fully active
    plain = window_onset_density(env, FR)
    act = window_onset_density_active(env, rms, FR)
    assert act == pytest.approx(plain, rel=0.05)


def test_outro_cheat_is_corrected():
    """Half the window is silence: plain density halves (the cheat);
    active density stays at the playing-rate."""
    n = 430
    mask = np.zeros(n, bool); mask[: n // 2] = True
    env, rms = _env_with_onsets(n, 6, active_mask=mask)
    plain = window_onset_density(env, FR)
    act = window_onset_density_active(env, rms, FR)
    assert act > plain * 1.7, (plain, act)       # ~2x once silence is excluded


def test_all_silent_returns_zero():
    env = np.zeros(100, np.float32); rms = np.zeros(100, np.float32)
    assert window_onset_density_active(env, rms, FR) == 0.0
