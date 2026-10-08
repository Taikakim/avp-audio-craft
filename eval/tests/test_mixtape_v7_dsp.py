"""Unit tests for mixtape_v7_dsp (synthetic signals only: no stems, no SA3, no GPU)."""
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.signal import butter, sosfreqz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mixtape_v7_dsp as dsp  # noqa: E402

SR = 44100


def _db(x):
    return 20 * np.log10(np.maximum(x, 1e-12))


def test_lr4_pair_sums_magnitude_flat_and_butter4_does_not():
    fc = 150.0
    w, lo = sosfreqz(dsp.lr4_sos(fc, "low", SR), worN=8192, fs=SR)
    _, hi = sosfreqz(dsp.lr4_sos(fc, "high", SR), worN=8192, fs=SR)
    band = w > 20
    assert np.abs(_db(np.abs(lo + hi)[band])).max() < 0.05  # dB

    # why lr4_sos exists: butter(4) LP + HP has a +3 dB bump at the crossover
    b_lo = sosfreqz(butter(4, fc, "low", fs=SR, output="sos"), worN=8192, fs=SR)[1]
    b_hi = sosfreqz(butter(4, fc, "high", fs=SR, output="sos"), worN=8192, fs=SR)[1]
    assert _db(np.abs(b_lo + b_hi)[band]).max() > 2.9


def test_ramps_are_complementary():
    d, u = dsp.linear_ramps(1000)
    assert np.allclose(d + u, 1.0)
    d, u = dsp.equal_power_ramps(1000)
    assert np.allclose(d ** 2 + u ** 2, 1.0)
    assert d[0] == pytest.approx(1.0) and u[-1] == pytest.approx(1.0)


def test_bass_handover_is_hard_with_a_short_equal_power_blend():
    n, h, blend = 20000, 10000, int(SR * 0.05)
    a = np.ones((2, n))
    b = 2 * np.ones((2, n))
    mix, ga, gb = dsp.bass_handover(a, b, h, blend)
    assert np.allclose(ga ** 2 + gb ** 2, 1.0)                 # no level hole, no bump
    lo, hi = h - blend // 2, h - blend // 2 + blend
    assert np.all(ga[:lo] == 1) and np.all(gb[:lo] == 0)       # A alone before the blend
    assert np.all(ga[hi:] == 0) and np.all(gb[hi:] == 1)       # B at FULL level right after it
    assert np.all(mix[:, :lo] == 1) and np.all(mix[:, hi:] == 2)
    assert int(((ga > 0) & (gb > 0)).sum()) <= blend           # overlap never longer than the blend


def test_bass_handover_rejects_a_blend_that_does_not_fit():
    a = np.zeros((2, 1000))
    with pytest.raises(ValueError):
        dsp.bass_handover(a, a, h=10, blend=500)
    with pytest.raises(ValueError):
        dsp.bass_handover(a, np.zeros((2, 999)), h=500, blend=50)


def test_drums_crossfade_keeps_level_for_coherent_kick_and_incoherent_percussion():
    n = SR * 2
    t = np.arange(n) / SR
    mid = slice(int(n * 0.45), int(n * 0.55))
    edge = slice(int(n * 0.1), int(n * 0.9))

    # kick band: the SAME 60 Hz tone in both clips (coherent) -> amplitude must stay put
    kick = np.stack([0.5 * np.sin(2 * np.pi * 60 * t)] * 2)
    out = dsp.drums_crossfade(kick, kick, SR)
    assert abs(_db(dsp.rms(out[:, mid])) - _db(dsp.rms(kick[:, mid]))) < 1.0

    # percussion band: independent noise (incoherent) -> power must stay put (a linear ramp dips ~3 dB)
    rng = np.random.default_rng(0)
    na = 0.2 * rng.standard_normal((2, n))
    nb = 0.2 * rng.standard_normal((2, n))
    na, nb = dsp.lr4_split(na, 1000.0, SR)[1], dsp.lr4_split(nb, 1000.0, SR)[1]   # keep it well above 150 Hz
    out = dsp.drums_crossfade(na, nb, SR)
    ref = 0.5 * (dsp.rms(na[:, edge]) + dsp.rms(nb[:, edge]))
    assert abs(_db(dsp.rms(out[:, mid])) - _db(ref)) < 1.0
    lin = dsp.crossfade(na, nb, kind="linear")
    assert _db(dsp.rms(lin[:, mid])) < _db(ref) - 2.0           # the bug this replaces


def test_safe_slice_pads_both_ends_and_is_exact_inside():
    x = np.arange(20, dtype=np.float32).reshape(2, 10)
    assert np.array_equal(dsp.safe_slice(x, 2, 6), x[:, 2:6])
    left = dsp.safe_slice(x, -3, 4)
    assert left.shape == (2, 7) and np.all(left[:, :3] == 0) and np.array_equal(left[:, 3:], x[:, :4])
    right = dsp.safe_slice(x, 7, 13)
    assert right.shape == (2, 6) and np.array_equal(right[:, :3], x[:, 7:]) and np.all(right[:, 3:] == 0)
    assert np.all(dsp.safe_slice(x, 50, 60) == 0)               # entirely outside


def test_match_rms_scales_and_clamps():
    rng = np.random.default_rng(1)
    x = rng.standard_normal((2, 5000))
    ref = 0.5 * rng.standard_normal((2, 5000))
    y, g = dsp.match_rms(x, ref)
    assert dsp.rms(y) == pytest.approx(dsp.rms(ref), rel=1e-6) and 0.25 < g < 4
    _, g = dsp.match_rms(x, 100 * ref)
    assert g == 4.0
    z, g = dsp.match_rms(np.zeros((2, 10)), ref)
    assert g == 1.0 and not z.any()


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, 1e11])
def test_assert_finite_catches_the_13e_signatures(bad):
    x = np.zeros((2, 100))
    x[1, 50] = bad
    with pytest.raises(FloatingPointError):
        dsp.assert_finite(x, "other")


def test_assert_finite_returns_the_peak():
    x = np.zeros((2, 100))
    x[0, 3] = -0.8
    assert dsp.assert_finite(x, "other") == pytest.approx(0.8)
