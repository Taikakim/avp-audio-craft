"""Tests for fingerprint assembly + window-scalar alignment fix in dataset.py.

Unit tests use synthetic numpy arrays — no real latents required.
The integration test uses a temporary directory with mock .npy/.json/.TIMESERIES.npz,
so it runs offline and verifies volatile dims come from the window, NOT the crop scalar.
"""

from __future__ import annotations

import glob
import json
import os
import tempfile

import numpy as np
import pytest
import torch

from sa3_control.dataset import (
    LatentControlDataset,
    fingerprint_in_dim,
    window_energy,
    window_onset_density,
)


# ---------------------------------------------------------------------------
# Helper-function unit tests
# ---------------------------------------------------------------------------

def test_fingerprint_in_dim_variants():
    k = 6
    assert fingerprint_in_dim("A", k) == k + 1 + 3   # genre+other + year + bpm + sync
    assert fingerprint_in_dim("B", k) == k + 1 + 5   # + onset + energy
    assert fingerprint_in_dim("C", k) == k + 1 + 1   # genre+other + year only


def test_window_energy_is_mean():
    assert abs(window_energy(np.array([0.2, 0.4, 0.6], np.float32)) - 0.4) < 1e-6


def test_window_onset_density_counts_peaks_per_second():
    env = np.zeros(1077, np.float32)                  # ~100 s at 10.767 Hz
    env[[100, 300, 500, 700, 900]] = 1.0              # 5 isolated peaks
    d = window_onset_density(env, frame_rate=10.767)
    assert abs(d - 5.0 / (1077 / 10.767)) < 0.2      # ~5 onsets / ~100 s


def test_window_onset_density_empty_returns_zero():
    assert window_onset_density(np.zeros(2, np.float32)) == 0.0


# ---------------------------------------------------------------------------
# Integration test — mock directory (no real latents required)
# ---------------------------------------------------------------------------

def _make_mock_crop(tmpdir: str, name: str, meta: dict,
                    onset_env: np.ndarray, rms_mid: np.ndarray,
                    T: int = 512) -> str:
    """Write a synthetic .npy + .json + .TIMESERIES.npz into tmpdir."""
    lat = np.zeros((256, T), dtype=np.float32)
    np.save(os.path.join(tmpdir, f"{name}.npy"), lat)
    with open(os.path.join(tmpdir, f"{name}.json"), "w") as f:
        json.dump(meta, f)
    np.savez(
        os.path.join(tmpdir, f"{name}.TIMESERIES.npz"),
        onset_envelope_ts=onset_env.astype(np.float32),
        rms_energy_mid_ts=rms_mid.astype(np.float32),
        # beat_activation_ts needed for beat-aligned start (fallback to random is fine)
        beat_activation_ts=np.zeros(T, dtype=np.float32),
    )
    return os.path.join(tmpdir, f"{name}.npy")


VOCAB = ["Electronic---Goa Trance", "Electronic---Psy-Trance", "Electronic---Techno"]


def test_fingerprint_variant_a_shape_and_genre_order():
    """Variant A: shape == k+1+3; genre dims come from style_genre in the correct order."""
    k = len(VOCAB)
    with tempfile.TemporaryDirectory() as tmpdir:
        meta = {
            "style_genre": {
                "Electronic---Goa Trance": 0.7,
                "Electronic---Psy-Trance": 0.2,
                "other": 0.1,
            },
            "release_year": 2000,
            "bpm_madmom": 145.0,
            "syncopation": 0.3,
        }
        T = 512
        _make_mock_crop(tmpdir, "crop_a", meta,
                        onset_env=np.zeros(T, dtype=np.float32),
                        rms_mid=np.ones(T, dtype=np.float32) * 0.5)

        ds = LatentControlDataset(
            tmpdir, controls=(), audio_ref=None,
            fingerprint=True, genre_vocab=VOCAB, fp_variant="A",
        )
        item = ds[0]
        fp = item["fingerprint"]

        expected_dim = fingerprint_in_dim("A", k)
        assert fp.shape == (expected_dim,), f"shape {fp.shape} != ({expected_dim},)"

        # genre block: first 3 dims are the vocab probs, then other
        assert abs(fp[0].item() - 0.7) < 1e-5, "Goa Trance prob wrong"
        assert abs(fp[1].item() - 0.2) < 1e-5, "Psy-Trance prob wrong"
        assert abs(fp[2].item() - 0.0) < 1e-5, "Techno prob should be 0 (absent)"
        assert abs(fp[3].item() - 0.1) < 1e-5, "other bucket wrong"


def test_fingerprint_variant_b_volatile_dims_use_window_not_json_scalar():
    """Variant B: onset_density and energy come from the sliced timeseries window,
    NOT from any crop-level JSON scalar.  We construct a mock where they differ
    and assert the window-computed value wins."""
    k = len(VOCAB)
    with tempfile.TemporaryDirectory() as tmpdir:
        T = 512
        # onset_envelope: 3 isolated peaks in the full window → computable density
        onset_env = np.zeros(T, dtype=np.float32)
        onset_env[[50, 150, 300]] = 1.0

        # rms_mid: constant 0.6 across the window
        rms_mid = np.full(T, 0.6, dtype=np.float32)

        # JSON has a stale crop-level onset_density scalar that differs from window
        meta = {
            "style_genre": {},
            "release_year": 1998,
            "bpm_madmom": 140.0,
            "syncopation": 0.5,
            # This is the STALE crop-level scalar — should NOT appear in the fingerprint
            "onset_density": 99.0,
        }
        _make_mock_crop(tmpdir, "crop_b", meta, onset_env, rms_mid, T=T)

        ds = LatentControlDataset(
            tmpdir, controls=(), audio_ref=None,
            fingerprint=True, genre_vocab=VOCAB, fp_variant="B",
            onset_norm=(0.0, 1.0), energy_norm=(0.0, 1.0),
        )
        item = ds[0]
        fp = item["fingerprint"]

        expected_dim = fingerprint_in_dim("B", k)
        assert fp.shape == (expected_dim,), f"shape {fp.shape} != ({expected_dim},)"

        # volatile onset dim (index k+1+1+2 = k+4)
        # window-computed density = 3 peaks / (512/10.767) ≈ 3/47.5 ≈ 0.063
        window_density = window_onset_density(onset_env)
        onset_norm_val = (window_density - 0.0) / 1.0  # onset_norm=(0,1)
        fp_onset_idx = k + 1 + 1 + 2  # genre+other + year + bpm + sync = indices 0..k+3, then onset
        assert abs(fp[fp_onset_idx].item() - onset_norm_val) < 1e-4, (
            f"onset dim {fp[fp_onset_idx].item():.4f} != window-computed {onset_norm_val:.4f}; "
            "volatile dim must come from window timeseries, not the crop JSON scalar (99.0)"
        )

        # volatile energy dim (index k+1+1+3 = k+5)
        window_en = window_energy(rms_mid)
        energy_norm_val = (window_en - 0.0) / 1.0
        fp_energy_idx = fp_onset_idx + 1
        assert abs(fp[fp_energy_idx].item() - energy_norm_val) < 1e-4, (
            f"energy dim {fp[fp_energy_idx].item():.4f} != window-computed {energy_norm_val:.4f}"
        )


def test_fingerprint_variant_c_shape():
    """Variant C: only genre+other+year, no bpm/sync/onset/energy."""
    k = len(VOCAB)
    with tempfile.TemporaryDirectory() as tmpdir:
        T = 512
        meta = {"style_genre": {}, "release_year": 1995}
        _make_mock_crop(tmpdir, "crop_c", meta,
                        onset_env=np.zeros(T, dtype=np.float32),
                        rms_mid=np.zeros(T, dtype=np.float32))

        ds = LatentControlDataset(
            tmpdir, controls=(), audio_ref=None,
            fingerprint=True, genre_vocab=VOCAB, fp_variant="C",
        )
        fp = ds[0]["fingerprint"]
        assert fp.shape == (fingerprint_in_dim("C", k),)


# ---------------------------------------------------------------------------
# Optional: real-latents integration test (skipped if NVMe mirror not present)
# ---------------------------------------------------------------------------

LAT = "/home/kim/Projects/latents_sa3"
GENRE_VOCAB_JSON = "/home/kim/Projects/SAO/control/sa3_control/genre_vocab.json"


@pytest.mark.skipif(
    not glob.glob(os.path.join(LAT, "*.npy")),
    reason="NVMe latents_sa3 not present",
)
def test_fingerprint_item_shape_variant_a_real_latents():
    vocab = json.load(open(GENRE_VOCAB_JSON))["vocab"]
    ds = LatentControlDataset(
        LAT, controls=(), audio_ref=None,
        fingerprint=True, genre_vocab=vocab, fp_variant="A",
        random_crop_frames=512,
    )
    fp = ds[0]["fingerprint"]
    from sa3_control.dataset import fingerprint_in_dim  # noqa: F401 (already imported)
    assert fp.shape == (fingerprint_in_dim("A", len(vocab)),)
