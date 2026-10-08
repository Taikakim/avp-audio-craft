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


def test_zero_phase_split_reconstructs_the_input_exactly_unlike_lr4():
    t = np.arange(SR * 3) / SR                       # energy around the 150 Hz crossover, where kick and bassline live
    x = np.stack([np.sin(2 * np.pi * 120 * t) + np.sin(2 * np.pi * 180 * t)] * 2)
    lo, hi = dsp.split_zero_phase(x, 150.0, SR)
    inner = slice(SR // 2, -SR // 2)               # the far end of an array rings; keep windows away from it
    assert _db(dsp.rms((lo + hi - x)[:, inner])) - _db(dsp.rms(x[:, inner])) < -120.0
    # the causal LR4 pair does not put the input back (all-pass phase): this is why drums use the zero-phase split
    clo, chi = dsp.lr4_split(x, 150.0, SR)
    assert _db(dsp.rms((clo + chi - x)[:, inner])) - _db(dsp.rms(x[:, inner])) > -3.0


def test_drums_crossfade_edges_are_the_original_clips():
    rng = np.random.default_rng(3)
    a = rng.standard_normal((2, SR * 4)); b = rng.standard_normal((2, SR * 4))
    al, ah = dsp.split_zero_phase(a, 150.0, SR); bl, bh = dsp.split_zero_phase(b, 150.0, SR)
    w = slice(SR // 2, SR // 2 + SR * 2)
    out = dsp.drums_crossfade(al[:, w], ah[:, w], bl[:, w], bh[:, w])
    n = SR // 200                                   # 5 ms
    assert _db(dsp.rms((out - a[:, w])[:, :n])) - _db(dsp.rms(a[:, w][:, :n])) < -40.0     # starts as A
    assert _db(dsp.rms((out - b[:, w])[:, -n:])) - _db(dsp.rms(b[:, w][:, -n:])) < -40.0   # ends as B


def test_kick_ramp_choice_depends_on_whether_the_kicks_share_a_grid():
    n = SR * 2
    t = np.arange(n) / SR
    mid = slice(int(n * 0.45), int(n * 0.55))
    zero = np.zeros((2, n))
    # coherent kicks (same tone in both clips, i.e. after Phase 0): linear keeps the level, equal-power bumps +3 dB
    k = np.stack([0.5 * np.sin(2 * np.pi * 60 * t)] * 2)
    lin = dsp.drums_crossfade(k, zero, k, zero, kick="linear")
    ep = dsp.drums_crossfade(k, zero, k, zero, kick="equal_power")
    assert abs(_db(dsp.rms(lin[:, mid])) - _db(dsp.rms(k[:, mid]))) < 0.5
    assert _db(dsp.rms(ep[:, mid])) - _db(dsp.rms(k[:, mid])) > 2.5
    # unrelated kicks (no shared grid, e.g. before Phase 0): equal-power keeps the level, linear digs a ~3 dB hole
    rng = np.random.default_rng(0)
    ka = dsp.split_zero_phase(0.3 * rng.standard_normal((2, n)), 150.0, SR)[0]
    kb = dsp.split_zero_phase(0.3 * rng.standard_normal((2, n)), 150.0, SR)[0]
    ref = 0.5 * (dsp.rms(ka[:, mid]) + dsp.rms(kb[:, mid]))
    ep = dsp.drums_crossfade(ka, zero, kb, zero, kick="equal_power")
    lin = dsp.drums_crossfade(ka, zero, kb, zero, kick="linear")
    assert abs(_db(dsp.rms(ep[:, mid])) - _db(ref)) < 1.0
    assert _db(dsp.rms(lin[:, mid])) < _db(ref) - 2.0


def test_percussion_band_is_equal_power():
    n = SR * 2
    mid = slice(int(n * 0.45), int(n * 0.55))
    rng = np.random.default_rng(1)
    pa = dsp.split_zero_phase(0.2 * rng.standard_normal((2, n)), 1000.0, SR)[1]
    pb = dsp.split_zero_phase(0.2 * rng.standard_normal((2, n)), 1000.0, SR)[1]
    zero = np.zeros((2, n))
    out = dsp.drums_crossfade(zero, pa, zero, pb, kick="linear")
    ref = 0.5 * (dsp.rms(pa[:, mid]) + dsp.rms(pb[:, mid]))
    assert abs(_db(dsp.rms(out[:, mid])) - _db(ref)) < 1.0


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


def test_edge_blend_returns_the_reference_at_both_ends_and_the_generated_layer_in_the_middle():
    rng = np.random.default_rng(5)
    gen = rng.standard_normal((2, 10000))
    ref = rng.standard_normal((2, 10000))
    out = dsp.edge_blend(gen, ref, 2000)
    assert np.allclose(out[:, 0], ref[:, 0]) and np.allclose(out[:, -1], ref[:, -1])
    assert np.allclose(out[:, 2000:-2000], gen[:, 2000:-2000])
    # equal-power weights: gen^2 + ref^2 = 1 everywhere
    ones = dsp.edge_blend(np.ones((1, 10000)), np.zeros((1, 10000)), 2000)[0]
    zeros = dsp.edge_blend(np.zeros((1, 10000)), np.ones((1, 10000)), 2000)[0]
    assert np.allclose(ones ** 2 + zeros ** 2, 1.0)


def test_edge_blend_rejects_an_edge_that_does_not_fit():
    x = np.zeros((2, 100))
    with pytest.raises(ValueError):
        dsp.edge_blend(x, x, 60)
    with pytest.raises(ValueError):
        dsp.edge_blend(x, np.zeros((2, 99)), 10)


# ----------------------------------------------------------------------------------------------- sync measurement

def _clicks(times, n, f0=60.0, seed=0):
    """A kick-like thump (decaying 60 Hz sine) at each time, plus a little hiss, (2, n)."""
    x = np.zeros(n)
    k = np.arange(int(0.12 * SR))
    thump = np.exp(-k / (0.03 * SR)) * np.sin(2 * np.pi * f0 * k / SR)
    for t in times:
        i = int(round(t * SR))
        if 0 <= i < n - len(k):
            x[i:i + len(k)] += thump
    x += 0.01 * np.random.default_rng(seed).standard_normal(n)
    return np.stack([x, x])


def test_kick_onsets_recover_the_click_times():
    bpm = 130.0
    times = 0.2 + np.arange(16) * 60.0 / bpm
    got = dsp.kick_onsets(_clicks(times, SR * 9), SR)
    assert len(got) == len(times)
    assert np.abs(got - times).max() < 0.012                      # within 12 ms, a constant bias at most


def test_grid_offsets_see_a_constant_shift_and_a_tempo_drift():
    n = SR * 9
    a = dsp.kick_onsets(_clicks(0.2 + np.arange(16) * 60.0 / 130.0, n), SR)
    # B 40 ms late, same tempo: a constant +40 ms
    _, off = dsp.grid_offsets_ms(a, dsp.kick_onsets(_clicks(0.24 + np.arange(16) * 60.0 / 130.0, n, seed=1), SR))
    assert np.abs(off - 40.0).max() < 6.0
    # B at 136 BPM from the same start: the offset DRIFTS (B's beats come earlier and earlier: negative and growing)
    _, off = dsp.grid_offsets_ms(a, dsp.kick_onsets(_clicks(0.2 + np.arange(17) * 60.0 / 136.0, n, seed=2), SR))
    per_beat = 60000.0 / 130.0 - 60000.0 / 136.0                  # ms gained per beat
    assert off[0] == pytest.approx(0.0, abs=8.0)
    assert off[8] == pytest.approx(-8 * per_beat, abs=10.0)       # 8 beats in


def test_grid_offsets_need_two_onsets_each():
    assert dsp.grid_offsets_ms([1.0], [1.0, 2.0])[1].size == 0
    assert dsp.grid_offsets_ms([1.0, 2.0], [])[1].size == 0


def test_onset_lag_has_the_documented_sign_and_size():
    n = SR * 6
    times = 0.3 + np.cumsum(np.random.default_rng(4).uniform(0.18, 0.5, 14))      # irregular, so no beat ambiguity
    ref = _clicks(times, n, seed=5)
    late = _clicks(times + 0.025, n, seed=6)                       # A = 25 ms late relative to B
    lag, corr = dsp.onset_lag_ms(late, ref, SR)
    assert lag == pytest.approx(25.0, abs=4.0) and corr > 0.5
    lag, corr = dsp.onset_lag_ms(ref, late, SR)
    assert lag == pytest.approx(-25.0, abs=4.0)
    lag, _ = dsp.onset_lag_ms(ref, ref, SR)
    assert abs(lag) < 1.0


def test_onset_lag_reports_low_correlation_for_unrelated_signals():
    rng = np.random.default_rng(7)
    a = _clicks(0.3 + np.cumsum(rng.uniform(0.18, 0.5, 14)), SR * 6, seed=8)
    b = _clicks(0.3 + np.cumsum(rng.uniform(0.18, 0.5, 14)), SR * 6, seed=9)
    assert dsp.onset_lag_ms(a, b, SR)[1] < 0.3


# ----------------------------------------------------------------------------------------------- Phase 0 helpers

def _kicks(times, n, seed=0):
    x = np.zeros(n)
    k = np.arange(int(0.12 * SR))
    thump = np.exp(-k / (0.03 * SR)) * np.sin(2 * np.pi * 60.0 * k / SR)
    for t in times:
        i = int(round(t * SR))
        if 0 <= i < n - len(k):
            x[i:i + len(k)] += thump
    x += 0.003 * np.random.default_rng(seed).standard_normal(n)
    return np.stack([x, x])


def test_phase_shift_sign_b_late_gives_a_negative_delay_and_b_early_a_positive_one():
    """s > 0 means B is EARLY and must be delayed (apply as b_lo -= s). B late -> s < 0."""
    n, beat = SR * 6, int(round(SR * 60 / 140.0))
    grid = 0.2 + np.arange(12) * 60 / 140.0
    a = _kicks(grid, n, 1)
    s, ncc, _ = dsp.phase_shift(a, _kicks(grid + 0.05, n, 2), beat, sr=SR)       # B 50 ms late
    assert s == pytest.approx(-0.05 * SR, abs=0.004 * SR) and ncc > 0.9
    s, ncc, _ = dsp.phase_shift(a, _kicks(grid - 0.05, n, 3), beat, sr=SR)       # B 50 ms early
    assert s == pytest.approx(0.05 * SR, abs=0.004 * SR) and ncc > 0.9
    s, _, ncc0 = dsp.phase_shift(a, _kicks(grid, n, 4), beat, sr=SR)             # already aligned
    assert abs(s) < 0.003 * SR and ncc0 > 0.9


def test_applying_the_shift_the_documented_way_puts_the_kicks_on_one_grid():
    """The whole contract in one place: take B's window `b_lo - s`, and the kick offsets measured on the result vanish."""
    n, beat, L = SR * 8, int(round(SR * 60 / 140.0)), SR * 3
    grid = 0.2 + np.arange(16) * 60 / 140.0
    a = _kicks(grid, n, 1)
    b = _kicks(grid + 0.06, n, 2)                                                # B's kicks 60 ms late
    a_lo, b_lo = SR * 2, SR * 2
    s, _, _ = dsp.phase_shift(a[:, a_lo:a_lo + L], b[:, b_lo:b_lo + L], beat, sr=SR)
    before = dsp.grid_offsets_ms(dsp.kick_onsets(a[:, a_lo:a_lo + L], SR), dsp.kick_onsets(b[:, b_lo:b_lo + L], SR))[1]
    after_good = dsp.grid_offsets_ms(dsp.kick_onsets(a[:, a_lo:a_lo + L], SR),
                                     dsp.kick_onsets(b[:, b_lo - s:b_lo - s + L], SR))[1]
    after_bad = dsp.grid_offsets_ms(dsp.kick_onsets(a[:, a_lo:a_lo + L], SR),
                                    dsp.kick_onsets(b[:, b_lo + s:b_lo + s + L], SR))[1]
    assert np.abs(before - 60).max() < 8 and np.abs(after_good).max() < 8        # fixed
    assert np.abs(after_bad - 120).max() < 10                                    # the opposite sign doubles the offset


def test_vectorised_phase_shift_matches_a_plain_loop():
    rng = np.random.default_rng(11)
    n = SR * 2
    a = np.stack([np.convolve(rng.standard_normal(n), np.ones(400) / 400, "same")] * 2)
    b = np.roll(a, 700, axis=1) + 0.1 * rng.standard_normal(a.shape)
    beat = int(round(SR * 60 / 130.0))
    s, ncc_s, ncc_0 = dsp.phase_shift(a, b, beat, sr=SR)
    ea, eb = dsp.kick_env(a, SR), dsp.kick_env(b, SR)
    m = int(round(beat / 4))
    best, best_score = 0, -np.inf
    for k in range(-m, m + 1):                                                    # the original loop, line for line
        ov = len(ea) - abs(k)
        lo_a, lo_b = max(0, k), max(0, -k)
        na = np.sqrt((ea[lo_a:lo_a + ov] ** 2).sum()) * np.sqrt((eb[lo_b:lo_b + ov] ** 2).sum())
        v = float(np.sum(ea[lo_a:lo_a + ov] * eb[lo_b:lo_b + ov]) / max(na, 1e-12))
        score = v - 0.05 * abs(k) / m
        if score > best_score:
            best, best_score = k, score
    assert s == best


def test_shift_samples_delays_advances_and_keeps_the_length():
    x = np.arange(1, 11, dtype=float).reshape(1, 10)
    assert np.array_equal(dsp.shift_samples(x, 3)[0], [0, 0, 0, 1, 2, 3, 4, 5, 6, 7])
    assert np.array_equal(dsp.shift_samples(x, -3)[0], [4, 5, 6, 7, 8, 9, 10, 0, 0, 0])
    assert dsp.shift_samples(x, 0) is x
    assert not dsp.shift_samples(x, 10).any() and not dsp.shift_samples(x, -25).any()


def test_bungee_missing_interpreter_says_how_to_fix_it():
    with pytest.raises(RuntimeError, match="V7_BUNGEE_PY"):
        dsp.bungee_stretch(np.zeros((2, 1000)), 1.05, SR, python="/no/such/python")
    x = np.zeros((2, 10))
    assert dsp.bungee_stretch(x, 1.0004, SR) is x                                 # a speed of ~1 is a no-op


# ----------------------------------------------------------------------------------------------- tempo, drift, grid residuals

def _quantised_downbeats(bpm, n=24, t0=0.37, step=0.01):
    """What madmom's 100 Hz output gives: true bar times rounded to 10 ms."""
    bar = 240.0 / bpm
    return np.round((t0 + np.arange(n) * bar) / step) * step


def test_fit_bpm_is_exact_where_the_median_bar_interval_is_not():
    """transition 0 of 2026-10-08: 132.08 -> 136.06 BPM. The median of 10 ms-quantised bar intervals is off by tenths
    of a BPM, which as a stretch ratio is a drift; the least-squares slope recovers the tempo."""
    for bpm in (132.08, 136.06, 129.49, 156.98):
        db = _quantised_downbeats(bpm)
        regression = dsp.fit_bpm(db)
        median = 240.0 / float(np.median(np.diff(db)))
        assert regression == pytest.approx(bpm, abs=0.05)
        assert abs(median - bpm) > abs(regression - bpm)               # the old way is never better
    db = _quantised_downbeats(132.08)
    assert abs(240.0 / float(np.median(np.diff(db))) - 132.08) > 0.15  # ~0.2 BPM off on its own; A and B err in opposite
    #                                                                    directions, so the RATIO is off by 0.4 % (next test)


def test_the_stretch_ratio_from_quantised_downbeats_matches_the_true_ratio():
    a, b = 132.08, 136.06
    true = b / a
    from_regression = dsp.fit_bpm(_quantised_downbeats(b)) / dsp.fit_bpm(_quantised_downbeats(a, t0=0.5))
    from_median = (240.0 / float(np.median(np.diff(_quantised_downbeats(b))))) / (240.0 / float(np.median(np.diff(_quantised_downbeats(a, t0=0.5)))))
    assert abs(from_regression - true) < 0.0008                        # < 1.1 ms/s
    assert abs(from_median - true) > abs(from_regression - true)


def test_fit_bpm_needs_three_downbeats():
    with pytest.raises(ValueError):
        dsp.fit_bpm([0.0, 1.8])


def test_drift_is_the_slope_and_a_constant_offset_is_not_drift():
    t = np.arange(0, 14, 1.76)
    assert dsp.drift_ms_per_s(t, 40.0 + 0 * t) == pytest.approx(0.0, abs=1e-9)          # phase error
    assert dsp.drift_ms_per_s(t, 3.99 * t) == pytest.approx(3.99, abs=1e-9)              # tempo-ratio error
    assert dsp.drift_ms_per_s([1.0, 2.0], [0.0, 5.0]) == 0.0


def test_grid_residuals_flag_a_generated_span_that_left_the_grid():
    period = 60.0 / 136.0
    grid = 0.3 + np.arange(24) * period
    ref = np.concatenate([grid[:6], grid[12:]])                        # the real material around a gap
    on_grid = grid[6:12] + np.random.default_rng(0).normal(0, 0.004, 6)
    galloping = grid[6:12] + np.array([0, 0.03, -0.02, 0.05, -0.04, 0.02])
    assert np.abs(dsp.grid_residuals_ms(ref, on_grid, period)).max() < 12
    assert np.abs(dsp.grid_residuals_ms(ref, galloping, period)).max() > 40
    assert dsp.grid_residuals_ms(ref[:2], on_grid, period).size == 0 and dsp.grid_residuals_ms(ref, [], period).size == 0


# ----------------------------------------------------------------------------------------------- robust drift and the sync verdict

def test_drift_ignores_a_single_bad_bar():
    """The real 8-bar case from the Arc run: seven bars within 5 ms and one fill at +102 ms. A least-squares slope read it
    as +3.63 ms/s (51 ms over the window); the robust slope reads ~0."""
    per_bar = [2.8, 1.2, -4.8, 0.0, -3.2, -2.0, 102.4, -4.2]
    t = np.arange(8) * 1.76
    assert abs(float(np.polyfit(t, per_bar, 1)[0])) > 3.0                  # what it used to say
    assert abs(dsp.drift_ms_per_s(t, per_bar)) < 1.0                       # what it says now
    assert dsp.drift_ms_per_s(t, 3.99 * t) == pytest.approx(3.99, abs=1e-6)  # a real, steady drift is still seen


def test_grid_verdict_reports_one_outlier_bar_and_still_fails_a_real_problem():
    per_bar = [2.8, 1.2, -4.8, 0.0, -3.2, -2.0, 102.4, -4.2]
    synced, outliers = dsp.grid_verdict(per_bar, 0.0, 14.1, 25.0)
    assert synced is True and outliers == [7]                              # one fill in eight is a note, not a verdict
    assert dsp.grid_verdict([2.0, 3.0, 90.0, 80.0, 1.0, 2.0, 3.0, 2.0], 0.0, 14.1, 25.0) == (False, [3, 4])   # two bad bars in eight: not ok
    assert dsp.grid_verdict([2.0] * 8, 3.99, 14.1, 25.0)[0] is False       # a steady drift of 56 ms over the window
    assert dsp.grid_verdict([2.0, 90.0], 0.0, 3.4, 25.0) == (False, [2])   # with 2 bars every bar must pass
    assert dsp.grid_verdict([2.0, None, 1.0, 2.0, 3.0], 0.0, 8.8, 25.0) == (True, [2])   # no kick pairs in one bar of five: an outlier
    assert dsp.grid_verdict([2.0, None, 1.0, 2.0], 0.0, 7.0, 25.0) == (False, [2])           # with four bars every bar must pass
    assert dsp.grid_verdict([], 0.0, 1.0, 25.0)[0] is False


def test_pad_end_to_frame_pads_the_end_to_a_whole_number_of_frames():
    x = np.arange(10, dtype=float).reshape(1, 10)
    y = dsp.pad_end_to_frame(x, 4)
    assert y.shape == (1, 12) and np.array_equal(y[0, :10], x[0]) and not y[0, 10:].any()
    assert dsp.pad_end_to_frame(x, 5) is x and dsp.pad_end_to_frame(x, 10) is x           # already whole: untouched
    assert dsp.pad_end_to_frame(np.zeros((2, 3, 7)), 4).shape == (2, 3, 8)
