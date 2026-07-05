"""Tests for probe_layer_feature_map.py — the CPU-side scaffold that turns
per-layer, per-frame DiT activations into a layer×feature encodability map.
GPU activation extraction is deferred; these test the pure analysis functions
against synthetic data with known layer→feature relationships."""
import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from probe_layer_feature_map import (
    load_features,
    frame_probe_r2,
    lagged_xcorr,
    build_feature_map,
    pool_frames,
)


def rng(seed=0):
    return np.random.default_rng(seed)


# ---------------------------------------------------------------- frame_probe_r2

def test_frame_probe_r2_linear_feature_is_high():
    r = rng(1)
    X = r.standard_normal((600, 16))
    w = r.standard_normal(16)
    y = X @ w + 0.01 * r.standard_normal(600)      # feature IS a linear readout of acts
    assert frame_probe_r2(X, y) > 0.95


def test_frame_probe_r2_unrelated_feature_is_near_zero():
    r = rng(2)
    X = r.standard_normal((600, 16))
    y = r.standard_normal(600)                      # independent of X
    assert frame_probe_r2(X, y) < 0.1               # held-out R^2 ~0 (can be slightly negative)


def test_frame_probe_r2_vector_feature_mean_over_outputs():
    # hpcp-like [N, k] multi-output: linear in X -> high mean R^2
    r = rng(3)
    X = r.standard_normal((600, 16))
    W = r.standard_normal((16, 5))
    Y = X @ W + 0.01 * r.standard_normal((600, 5))
    assert frame_probe_r2(X, Y) > 0.95


def test_frame_probe_r2_handles_constant_feature():
    # zero-variance target must not crash / must be ~0, not NaN
    X = rng(4).standard_normal((200, 8))
    y = np.full(200, 3.0)
    r2 = frame_probe_r2(X, y)
    assert np.isfinite(r2)


# ---------------------------------------------------------------- lagged_xcorr

def test_lagged_xcorr_detects_shift():
    r = rng(5)
    a = r.standard_normal(500)
    k = 7
    b = np.roll(a, k)                               # b lags a by k frames
    lag, corr = lagged_xcorr(a, b, max_lag=20)
    assert lag == k
    assert corr > 0.9


def test_lagged_xcorr_zero_lag_for_aligned():
    r = rng(6)
    a = r.standard_normal(500)
    lag, corr = lagged_xcorr(a, a, max_lag=20)
    assert lag == 0 and corr > 0.99


def test_lagged_xcorr_low_for_unrelated():
    r = rng(7)
    a = r.standard_normal(500); b = rng(8).standard_normal(500)
    _, corr = lagged_xcorr(a, b, max_lag=20)
    assert abs(corr) < 0.3


# ---------------------------------------------------------------- pool_frames

def test_pool_frames_concatenates_clips_per_layer():
    # two clips, 3 layers, T=10 frames, d=4
    clips = [np.zeros((3, 10, 4)) + i for i in range(2)]  # clip i filled with i
    pooled = pool_frames(clips)
    assert len(pooled) == 3                          # per layer
    assert pooled[0].shape == (20, 4)                # 2 clips * 10 frames
    assert (pooled[0][:10] == 0).all() and (pooled[0][10:] == 1).all()


# ---------------------------------------------------------------- build_feature_map

def test_build_feature_map_localizes_relationship():
    # 3 layers; feature 'onset' is a linear readout of LAYER 1 only.
    r = rng(9)
    N, d = 800, 12
    acts = [r.standard_normal((N, d)) for _ in range(3)]
    w = r.standard_normal(d)
    feats = {
        "onset": acts[1] @ w + 0.01 * r.standard_normal(N),   # lives in layer 1
        "rms": r.standard_normal(N),                          # unrelated to all
    }
    out = build_feature_map(acts, feats)
    R2 = out["r2"]
    assert R2.shape == (3, 2)
    oi = out["features"].index("onset")
    assert R2[1, oi] > 0.9                            # layer 1 encodes onset
    assert R2[0, oi] < 0.2 and R2[2, oi] < 0.2        # other layers don't
    ri = out["features"].index("rms")
    assert R2[:, ri].max() < 0.2                      # rms encoded nowhere


def test_build_feature_map_argmax_layer_per_feature():
    r = rng(10)
    N, d = 800, 12
    acts = [r.standard_normal((N, d)) for _ in range(3)]
    feats = {"f": acts[2] @ r.standard_normal(d)}     # lives in layer 2
    out = build_feature_map(acts, feats)
    assert out["best_layer"]["f"] == 2


# ---------------------------------------------------------------- load_features

def test_load_features_from_npz(tmp_path):
    p = tmp_path / "clip.TIMESERIES.npz"
    np.savez(p, onset_envelope_ts=np.arange(4096.0),
             hpcp_ts=np.ones((4096, 12)), rms_bass_ts=np.zeros(4096))
    feats = load_features(str(p), names=["onset_envelope_ts", "hpcp_ts"])
    assert feats["onset_envelope_ts"].shape == (4096,)
    assert feats["hpcp_ts"].shape == (4096, 12)
    assert "rms_bass_ts" not in feats                 # only requested names


def test_load_features_subsample_frames(tmp_path):
    p = tmp_path / "clip.TIMESERIES.npz"
    np.savez(p, onset_envelope_ts=np.arange(4096.0))
    feats = load_features(str(p), names=["onset_envelope_ts"], n_frames=512)
    assert feats["onset_envelope_ts"].shape == (512,)
