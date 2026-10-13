#!/usr/bin/env python
# Last edited: GHOST-NOTE 2026-10-13 -- tv_stretch_plan / bungee_stretch_schedule (time-varying stretch)
# Last edited: GHOST-NOTE 2026-10-13 -- kick_grid_shift (onset-based phase alignment, +-1/2 beat)
# Last edited: GHOST-NOTE 2026-10-13 -- tv_filter / other_sweep (the assembler's moving-crossover `other` crossfade, for the smoke renderer)
"""mixtape_v7_dsp.py -- pure numpy/scipy building blocks for the v7 stem transition.

No torch, no SA3, no GPU, no files: everything here runs and is unit-tested anywhere
(eval/tests/test_mixtape_v7_dsp.py). Proposed by KUANG 2026-10-08 as the testable half of
render_v7_4track_smoketest_fast.py; see antigravity.kuang.log for the review it comes from.

All audio is (channels, samples). Positions are integer samples.

lr4_sos() is the same filter as mixtape_assemble_v7.lr4_sos(); it is copied so this module
imports without the mir venv / SA3 (that module pulls in chroma_morph_transitions). Unify when
convenient.
"""
import os
import numpy as np
from scipy.signal import butter, fftconvolve, find_peaks, hilbert, sosfilt, sosfiltfilt, stft
from scipy.stats import theilslopes


def resolve_mantu(p):
    """Dynamically remap broken /run/media/kim/Mantu mount paths to /run/media/kim/Mantu2."""
    if not p:
        return p
    p_str = str(p)
    if "/run/media/kim/Mantu/" in p_str or p_str == "/run/media/kim/Mantu":
        p2 = p_str.replace("/run/media/kim/Mantu", "/run/media/kim/Mantu2", 1)
        if os.path.exists(p2) or not os.path.exists(p_str):
            return p2
    return p_str


# ---------------------------------------------------------------------------------------------
# filters
# ---------------------------------------------------------------------------------------------

def lr4_sos(fc, kind, sr):
    """Linkwitz-Riley 4th order = two cascaded 2nd-order Butterworths.

    NOT butter(4): a 4th-order Butterworth low-pass plus high-pass sums to +3.01 dB at fc.
    The LR4 pair sums magnitude-flat (spec section 5, item 9) provided both use the same fc.
    """
    s = butter(2, fc, btype=kind, fs=sr, output="sos")
    return np.vstack([s, s])


def lr4_split(audio, fc, sr):
    """(low, high) of a (C, N) array. Causal sosfilt; the pair sums to an all-pass, so
    low + high matches the input in magnitude but NOT in phase: on real drums the
    recombination differs from the input by +2.6 dB re the drums (measured, 150 Hz). Right
    for time-varying sweeps (spec section 4, sosfilt with carried state); wrong for a static
    split that must put the original back at unit gain, use split_zero_phase for that."""
    low = sosfilt(lr4_sos(fc, "low", sr), audio, axis=-1)
    high = sosfilt(lr4_sos(fc, "high", sr), audio, axis=-1)
    return low, high


def tv_filter(x, fc_of_n, kind, sr=44100, block=256):
    """Time-varying LR4 with the filter state carried across blocks (sosfilt, never filtfilt); fc is updated per block and
    quantised to 1 % steps so the design is cached. Same as mixtape_assemble_v7.tv_filter. x (C, N);
    fc_of_n(array of sample indices) -> fc per sample."""
    out = np.empty_like(x, dtype=np.float64)
    cache, zi = {}, None
    for lo in range(0, x.shape[1], block):
        hi = min(lo + block, x.shape[1])
        fc = float(fc_of_n(np.array([(lo + hi) // 2]))[0])
        key = int(round(np.log(fc) / 0.01))
        if key not in cache:
            cache[key] = lr4_sos(float(np.exp(key * 0.01)), kind, sr)
        sos = cache[key]
        if zi is None or zi.shape[0] != sos.shape[0]:
            zi = np.zeros((sos.shape[0], x.shape[0], 2))
        y, zi = sosfilt(sos, x[:, lo:hi], axis=-1, zi=zi)
        out[:, lo:hi] = y
    return out


def other_sweep(a, b, sr=44100, fc_hi=16000.0, fc_lo=60.0):
    """The `other` crossfade of the v7c assembler (spec section 4): the outgoing clip is low-passed and the incoming clip
    high-passed at ONE moving LR4 crossover that sweeps exponentially from `fc_hi` to `fc_lo` over the window, so the incoming
    first plays only the extreme highs, then more and more, while the outgoing keeps only the lows, then nothing. The LR4 pair
    sums magnitude-flat, so the level does not dip. a, b: (C, L). Returns (C, L) float64."""
    L = a.shape[-1]
    fc = lambda k: fc_hi * (fc_lo / fc_hi) ** (np.asarray(k, dtype=np.float64) / L)
    return tv_filter(np.asarray(a, dtype=np.float64), fc, "low", sr) + tv_filter(np.asarray(b, dtype=np.float64), fc, "high", sr)


def split_zero_phase(audio, fc, sr):
    """(low, high) with low + high == audio exactly (error -220 dB on real drums).

    Forward-backward Butterworth-2: each band has the LR4 magnitude (-6 dB at fc) and zero
    phase, and |H_lp|^2 + |H_hp|^2 = 1, so the bands add back to the input. Offline only
    (non-causal). Call it on the WHOLE stem and slice afterwards: on a slice the far end
    rings (-3 dB error in the last 5 ms of a 15 s slice, measured), the whole stem is exact
    except its own last ~100 ms, so keep windows >= 0.5 s away from the stem ends."""
    low = sosfiltfilt(butter(2, fc, btype="low", fs=sr, output="sos"), audio, axis=-1)
    high = sosfiltfilt(butter(2, fc, btype="high", fs=sr, output="sos"), audio, axis=-1)
    return low, high


# ---------------------------------------------------------------------------------------------
# slicing and ramps
# ---------------------------------------------------------------------------------------------

def safe_slice(audio, start_idx, end_idx):
    """audio[:, start:end], zero-padded where the range leaves the clip."""
    length = end_idx - start_idx
    out = np.zeros((audio.shape[0], length), dtype=audio.dtype)
    src_start = max(0, start_idx)
    src_end = min(audio.shape[1], end_idx)
    if src_start < src_end:
        dst_start = src_start - start_idx
        out[:, dst_start:dst_start + (src_end - src_start)] = audio[:, src_start:src_end]
    return out


def pad_end_to_frame(audio, frame):
    """Zero-pad (C, N) audio at the END to a whole number of `frame` samples (the autoencoder's downsampling ratio, 4096).
    The SAME autoencoder floors the frame count and CROPS THE FRONT of an input whose length is not a multiple: measured on
    the real model, N = 151*4096 + 3314 comes back 3314 samples (75 ms) early, N = 151*4096 exactly comes back with zero
    shift. `generate` pads at the end itself (a flat a2a measures 0 lag at any length); anything that calls
    pre.encode directly (the sine schedule's reference latents, the latent slerp) must do the same or it sits up to
    one frame (93 ms) out of time with the audio the sampler is working on."""
    n = audio.shape[-1]
    pad = (-n) % int(frame)
    return audio if pad == 0 else np.pad(audio, [(0, 0)] * (audio.ndim - 1) + [(0, pad)])


def linear_ramps(n):
    """(down, up): amplitudes sum to 1. Right for material that is COHERENT in both clips
    (kicks on the shared grid); constant level for coherent sources."""
    up = np.linspace(0.0, 1.0, n)
    return 1.0 - up, up


def equal_power_ramps(n):
    """(down, up): down^2 + up^2 = 1. Right for UNCORRELATED material (hats, noise,
    different pads); constant power for incoherent sources."""
    th = np.linspace(0.0, np.pi / 2, n)
    return np.cos(th), np.sin(th)


# ---------------------------------------------------------------------------------------------
# the stem layers
# ---------------------------------------------------------------------------------------------

def bass_handover(a, b, h, blend):
    """One bassline at a time (spec section 4): A plays to h, B plays from h, with an
    equal-power blend of `blend` samples centred on h (spec: <= 50 ms, against clicks).

    a, b: (C, L) windows of the two bass stems. h: handover sample (window centre).
    Returns (mix, gain_a, gain_b). Raises if the blend does not fit in the window.
    """
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch {a.shape} vs {b.shape}")
    n = a.shape[-1]
    lo = h - blend // 2
    hi = lo + blend
    if blend < 2 or lo < 0 or hi > n:
        raise ValueError(f"blend [{lo}, {hi}) does not fit a window of {n} samples")
    ga = np.zeros(n)
    gb = np.zeros(n)
    ga[:lo] = 1.0
    gb[hi:] = 1.0
    th = np.linspace(0.0, np.pi / 2, blend)
    ga[lo:hi] = np.cos(th)
    gb[lo:hi] = np.sin(th)
    return a * ga + b * gb, ga, gb


def drums_crossfade(a_lo, a_hi, b_lo, b_hi, kick="equal_power"):
    """Drums crossfade from PRE-SPLIT bands (split_zero_phase on the whole stem, then slice).

    Percussion (> fc) always crossfades EQUAL-POWER: it is uncorrelated between clips.
    Kick (< fc) takes `kick`:
      "equal_power" (default): right whenever the two kicks are not on a shared grid. Measured on
          clips 00 -> 01 without Phase 0 (129 vs 136 BPM, no stretch): correlation 0.000, linear
          ramp -2.9 dB in the middle two bars, equal-power +0.0 dB.
      "linear": right ONLY after Phase 0 (stretch + R0.3 alignment) has put both kicks on one grid,
          where they add coherently and amplitudes must sum to 1. Using it earlier digs a hole.
    With one ramp for both bands the split would do nothing; the split exists to allow this choice."""
    n = a_lo.shape[-1]
    if not (a_hi.shape[-1] == b_lo.shape[-1] == b_hi.shape[-1] == n):
        raise ValueError("band windows must have the same length")
    k_dn, k_up = linear_ramps(n) if kick == "linear" else equal_power_ramps(n)
    p_dn, p_up = equal_power_ramps(n)
    return a_lo * k_dn + b_lo * k_up + a_hi * p_dn + b_hi * p_up


def edge_blend(gen, ref, edge):
    """Fade a GENERATED layer in from, and out to, the reference layer over `edge` samples at each end,
    equal-power (spec R0.5: >= 1 bar at both edges). The window then starts and ends as the untouched
    clips do (spec S4) and only its middle is re-generated. gen, ref: (C, L) of the same shape;
    edge <= L // 2."""
    if gen.shape != ref.shape:
        raise ValueError(f"shape mismatch {gen.shape} vs {ref.shape}")
    n = gen.shape[-1]
    if edge < 1 or 2 * edge > n:
        raise ValueError(f"edge {edge} does not fit a window of {n} samples")
    w = np.ones(n)                                   # weight of the generated layer
    th = np.linspace(0.0, np.pi / 2, edge)
    w[:edge] = np.sin(th)
    w[n - edge:] = np.cos(th)
    return gen * w + ref * np.sqrt(np.clip(1.0 - w ** 2, 0.0, 1.0))


def crossfade(a, b, kind="equal_power"):
    """Plain crossfade of two same-shape windows (vocals, fallback `other`)."""
    n = a.shape[-1]
    dn, up = equal_power_ramps(n) if kind == "equal_power" else linear_ramps(n)
    return a * dn + b * up


# ---------------------------------------------------------------------------------------------
# sync: where are the onsets? (measure the AUDIO after every processing step, never trust a stored map)
# ---------------------------------------------------------------------------------------------

def kick_onsets(audio, sr, fc=150.0, min_gap_s=0.25):
    """Kick onset times in seconds from the < fc band of (C, N) audio: envelope slope maxima, so two clips
    are measured the same way. The beat/downbeat maps of a clip are only valid for the audio they were made on;
    after ANY stretch, shift or regeneration, measure again with this (spec section 5, item 1)."""
    x = np.asarray(audio, dtype=np.float64).mean(0)
    low = sosfiltfilt(butter(4, fc, btype="low", fs=sr, output="sos"), x)
    env = sosfiltfilt(butter(2, 40.0, btype="low", fs=sr, output="sos"), np.abs(hilbert(low)))
    d = np.maximum(np.diff(env, prepend=env[0]), 0.0)
    if d.max() <= 0:
        return np.array([])
    peaks, _ = find_peaks(d, height=0.3 * d.max(), distance=max(1, int(min_gap_s * sr)))
    return peaks / sr


def grid_offsets_ms(a_times, b_times):
    """For every onset of A, the signed offset (ms) to the nearest onset of B, wrapped to +-half an inter-onset
    interval. Positive = B is LATE. Returns (a_times_used, offsets_ms); empty arrays if either has < 2 onsets.
    Unlike a cross-correlation of two periodic signals this is not ambiguous modulo the beat period, and a
    tempo gap shows up as a steady drift from onset to onset."""
    a_times, b_times = np.asarray(a_times, float), np.asarray(b_times, float)
    if len(a_times) < 2 or len(b_times) < 2:
        return np.array([]), np.array([])
    half = float(np.median(np.diff(a_times))) / 2
    off = np.array([b_times[np.argmin(np.abs(b_times - t))] - t for t in a_times])
    off = (off + half) % (2 * half) - half
    return a_times, off * 1000.0


def onset_envelope(audio, sr, hop=128, n_fft=1024):
    """Full-band onset strength (half-wave rectified log-spectral flux), one value per `hop` samples."""
    x = np.asarray(audio, dtype=np.float64).mean(0)
    _, _, z = stft(x, fs=sr, nperseg=n_fft, noverlap=n_fft - hop, boundary=None, padded=False)
    mag = np.log1p(10.0 * np.abs(z))
    flux = np.maximum(np.diff(mag, axis=1, prepend=mag[:, :1]), 0.0).sum(0)
    return flux - flux.mean()


def onset_lag_ms(a, b, sr, max_ms=150.0, hop=128):
    """Lag of A relative to B (positive = A is LATE) from the cross-correlation of their onset envelopes, with
    parabolic peak refinement, plus the normalised correlation at the peak (how far to trust the lag: below ~0.2
    the two do not share onsets). Both (C, N), same length."""
    ea, eb = onset_envelope(a, sr, hop), onset_envelope(b, sr, hop)
    n = min(len(ea), len(eb))
    ea, eb = ea[:n], eb[:n]
    c = fftconvolve(ea, eb[::-1], mode="full")
    m = int(max_ms / 1000.0 * sr / hop)
    seg = c[n - 1 - m: n - 1 + m + 1]
    k = int(np.argmax(seg))
    den = 0.0
    if 0 < k < len(seg) - 1:
        den = seg[k - 1] - 2 * seg[k] + seg[k + 1]
    frac = 0.5 * (seg[k - 1] - seg[k + 1]) / den if den != 0 else 0.0
    norm = np.linalg.norm(ea) * np.linalg.norm(eb)
    return ((k - m) + frac) * hop / sr * 1000.0, (float(seg[k] / norm) if norm > 0 else 0.0)


def fit_bpm(downbeats, beats_per_bar=4):
    """BPM from a least-squares slope through ALL downbeats, never from the median bar interval. madmom's 100 Hz
    downbeat output quantises bar intervals to 10 ms: a ratio built from two such medians was off by 0.4 % (1.0341 for
    a true 1.0301), which is 3.99 ms/s of drift, about 25 ms by 42 s, i.e. the hi-hat gallop of 2026-10-08. A
    non-integer BPM is real (the diffusion output is not on an integer grid): never round it. Needs >= 3 downbeats."""
    db = np.asarray(downbeats, dtype=np.float64)
    if len(db) < 3:
        raise ValueError("need at least 3 downbeats for a tempo fit")
    slope = np.polyfit(np.arange(len(db)), db, 1)[0]
    return float(60.0 * beats_per_bar / slope)


def drift_ms_per_s(times_s, offsets_ms):
    """Slope of grid offsets (ms) against time (s), by the ROBUST Theil-Sen fit (median of the pairwise slopes). A
    tempo-ratio error is a steady DRIFT (this is non-zero); a phase error is a constant offset (this is ~0). A least-squares
    fit let ONE bad bar (a fill where the kicks do not pair up: +102 ms in an 8-bar window whose other bars were within
    5 ms) read as +3.6 ms/s of drift. 0.0 with fewer than 3 points."""
    if len(times_s) < 3:
        return 0.0
    return float(theilslopes(np.asarray(offsets_ms, float), np.asarray(times_s, float))[0])


def grid_verdict(per_bar_ms, drift_ms_s, window_s, tol_ms, min_ok_fraction=0.8):
    """Are two clips on one kick grid inside the window? Returns (synced, outlier_bars) with bars numbered from 1.
    Synced needs at least `min_ok_fraction` of the bars within tol_ms (None = no kick pairs in that bar = not ok) AND the
    drift over the whole window within tol_ms. One bad bar in eight or in five (a fill, a break) is an outlier to report,
    not a verdict on the transition; two bad bars in eight, a steady drift or a majority of bad bars is. With 2-4 bars every
    bar must pass."""
    ok = [v is not None and abs(v) <= tol_ms for v in per_bar_ms]
    outliers = [k + 1 for k, good in enumerate(ok) if not good]
    synced = bool(len(ok) > 0 and np.mean(ok) >= min_ok_fraction and abs(drift_ms_s) * window_s <= tol_ms)
    return synced, outliers


def grid_residuals_ms(ref_onsets, test_onsets, period_s):
    """How far `test_onsets` sit from the regular grid that `ref_onsets` define (ms, signed). Each reference onset gets
    the beat index round((t - t0) / period); the line t = a + b*k through them is the grid; every test onset is
    compared with the nearest grid point. Used to check that a generated span (an inpainted drum bridge) kept the
    grid of the real material around it. Empty if there are < 3 reference onsets or no test onsets."""
    ref = np.asarray(ref_onsets, dtype=np.float64)
    test = np.asarray(test_onsets, dtype=np.float64)
    if len(ref) < 3 or len(test) == 0:
        return np.array([])
    k = np.round((ref - ref[0]) / period_s)
    b, a = np.polyfit(k, ref, 1)
    kt = np.round((test - a) / b)
    return (test - (a + b * kt)) * 1000.0


# ---------------------------------------------------------------------------------------------
# level and sanity
# ---------------------------------------------------------------------------------------------

def rms(x):
    return float(np.sqrt(np.mean(np.square(np.asarray(x, dtype=np.float64))))) if np.size(x) else 0.0


def match_rms(x, ref, lo=0.25, hi=4.0):
    """Scale x to the RMS of ref, gain clamped to [lo, hi]. Returns (scaled, gain).
    A generated stem has no inherent level; log the gain so a clamp is visible."""
    r = rms(x)
    if r < 1e-9:
        return x, 1.0
    g = float(np.clip(rms(ref) / r, lo, hi))
    return x * g, g


def assert_finite(x, name, peak_max=16.0):
    """Raise FloatingPointError on NaN/Inf or an absurd peak; return the peak.

    The live-adapter fault (training-findings 13e) returns NaN or ~1e11 at random on the
    ROCm box, and NaN does not raise by itself. Call this on every generated array BEFORE
    it is mixed or written."""
    x = np.asarray(x)
    if not np.isfinite(x).all():
        raise FloatingPointError(f"{name}: contains NaN/Inf (live-adapter fault 13e signature)")
    pk = float(np.abs(x).max()) if x.size else 0.0
    if pk > peak_max:
        raise FloatingPointError(f"{name}: peak {pk:.3g} exceeds {peak_max} (13e signature is ~1e11)")
    return pk


# ---------------------------------------------------------------------------------------------
# tempo matching and phase alignment
# ---------------------------------------------------------------------------------------------

MIR_BUNGEE_PY = "/home/kim/Projects/mir/pitch_venv/bin/python"     # default; override with python= or $V7_BUNGEE_PY


def bungee_stretch(audio, speed, sr=44100, python=None):
    """Time-stretch audio (C, N) using Bungee, run in the mir pitch_venv.
    speed > 1.0 speeds up (shortens duration, raises tempo).

    Raises RuntimeError WITH Bungee's own stderr if it fails or the interpreter is missing (the first version dropped
    it). The caller must check the output length and re-measure the beat map on the result: a stretcher can add
    latency, and a downbeat map scaled by 1/speed is only a prediction (see stretch_clip in render_v7_smoketest.py)."""
    import os
    import subprocess
    import tempfile

    if abs(float(speed) - 1.0) < 0.001:
        return audio
    py = python or os.environ.get("V7_BUNGEE_PY") or MIR_BUNGEE_PY

    with tempfile.TemporaryDirectory() as td:
        src, dst = f"{td}/in.npy", f"{td}/out.npy"
        np.save(src, np.asarray(audio, dtype=np.float32).T)
        code = f"""
import numpy as np
from bungee_python import bungee as B
d = np.load({src!r}).astype(np.float32)
st = B.Bungee(sample_rate={sr}, channels=d.shape[1])
st.set_speed({float(speed)})
chunk = int(0.25 * {sr})
outs = []
for lo in range(0, d.shape[0], chunk):
    y = np.asarray(st.process(d[lo:lo + chunk]), dtype=np.float32)
    if y.ndim == 1: y = y.reshape(-1, d.shape[1])
    outs.append(y)
np.save({dst!r}, np.concatenate(outs, axis=0))
"""
        try:
            r = subprocess.run([py, "-c", code], capture_output=True, text=True)
        except FileNotFoundError as e:
            raise RuntimeError(f"Bungee interpreter not found: {py!r} (set V7_BUNGEE_PY or --bungee-python, "
                               f"or run with --no-stretch)") from e
        if r.returncode != 0:
            raise RuntimeError(f"bungee failed (exit {r.returncode}): {r.stderr.strip()[-600:]}")
        return np.load(dst).T


def bungee_stretch_schedule(audio, times, speeds, sr=44100, python=None):
    """Like bungee_stretch, but the speed follows a piecewise-linear schedule over OUTPUT time (times in s, ascending;
    held constant outside them). Same streaming loop as dj_beatmatch._bungee_stretch_schedule: speed re-read every 0.25 s
    chunk of processed output."""
    import subprocess
    import tempfile

    py = python or os.environ.get("V7_BUNGEE_PY") or MIR_BUNGEE_PY
    with tempfile.TemporaryDirectory() as td:
        src, dst = f"{td}/in.npy", f"{td}/out.npy"
        np.save(src, np.asarray(audio, dtype=np.float32).T)
        code = f"""
import numpy as np
from bungee_python import bungee as B
d = np.load({src!r}).astype(np.float32)
sr = {sr}
st = B.Bungee(sample_rate=sr, channels=d.shape[1])
times = np.array({[float(t) for t in times]!r}, dtype=np.float64)
speeds = np.array({[float(v) for v in speeds]!r}, dtype=np.float64)
chunk = int(0.25 * sr)
outs, out_sec = [], 0.0
for lo in range(0, d.shape[0], chunk):
    st.set_speed(float(np.interp(out_sec, times, speeds)))
    y = np.asarray(st.process(d[lo:lo + chunk]), dtype=np.float32)
    if y.ndim == 1: y = y.reshape(-1, d.shape[1])
    outs.append(y)
    out_sec += y.shape[0] / sr
np.save({dst!r}, np.concatenate(outs, axis=0))
"""
        try:
            r = subprocess.run([py, "-c", code], capture_output=True, text=True)
        except FileNotFoundError as e:
            raise RuntimeError(f"Bungee interpreter not found: {py!r}") from e
        if r.returncode != 0:
            raise RuntimeError(f"bungee failed (exit {r.returncode}): {r.stderr.strip()[-600:]}")
        return np.load(dst).T


def number_kicks(onsets, beat, smooth=5):
    """Kick onsets -> (beat indices kk, smoothed times ts) or None (<8 beats). An onset is kept only if its interval to the last
    kept one is a whole number of beats +-20 %; missed kicks are filled on the line between neighbours; the residual from the
    straight line is median(smooth)+mean(3) filtered (same end points and overall slope)."""
    on = np.sort(np.asarray(onsets, dtype=float))
    if len(on) < 8:
        return None
    kept, ks = [on[0]], [0]
    for t in on[1:]:
        n = int(round((t - kept[-1]) / beat))
        if n >= 1 and abs((t - kept[-1]) - n * beat) < 0.2 * beat:
            kept.append(t)
            ks.append(ks[-1] + n)
    if len(kept) < 8:
        return None
    kk = np.arange(int(ks[0]), int(ks[-1]) + 1)
    tt = np.interp(kk, np.array(ks, float), np.array(kept))
    res = tt - (tt[0] + (kk - kk[0]) * (tt[-1] - tt[0]) / max(len(kk) - 1, 1))
    from scipy.ndimage import median_filter, uniform_filter1d
    res_s = uniform_filter1d(median_filter(res, size=smooth, mode="nearest"), size=3, mode="nearest")
    return kk, tt - res + res_s, len(kept)


def follow_targets(on_b, c_b, beat_b, c_out, tt_a, c_src, v_g):
    """Target OUTPUT times (s) for A's numbered beats `tt_a` (smoothed source times) so that they land on B's own kicks: B's
    kicks (`on_b`, source s, its window centred at c_b) are numbered/smoothed, extended with beat_b outside the measured span;
    A beat k (nominal output time relative to the centre (tt-c_src)/v_g) takes the B kick nearest in that timing; the
    result is placed at c_out + that B time. Returns None when B has <8 numberable kicks."""
    nb = number_kicks(on_b, beat_b)
    if nb is None:
        return None
    mb, ub, _ = nb
    ub = ub - c_b
    oa = (tt_a - c_src) / v_g
    f = np.round((oa - ub[0]) / beat_b).astype(int)
    m = np.clip(f, 0, len(ub) - 1)
    g = ub[m] + (f - m) * beat_b                                  # beyond B's measured span: continue at beat_b
    return c_out + g


def tv_stretch_plan(onsets, beat_a, beat_b, v_g, n_src_sec, v_clip=0.08, smooth=5, target_fn=None):
    """Time-varying stretch for a clip whose tempo WANDERS (a constant stretch leaves a drift that grows through the window).
    `onsets`: kick onset times (s, source) of the region that must land on B's grid; beat_a/beat_b: nominal beat period of the clip
    and of the target; v_g: the constant speed used outside the region. Onsets are numbered by beat (an onset is kept only if
    its interval to the last kept one is a whole number of beats +-20 %), the numbered times are smoothed, and the output
    time of beat k is made T0 + k*beat_b. Speed between knots = source interval / beat_b, clipped to v_g*(1+-v_clip).
    Returns {"times","speeds" (output-time schedule for bungee_stretch_schedule), "src","out" (the realised monotone map, 1 ms),
    "n_kicks"} or None when fewer than 8 beats can be numbered. out_of_src(s) = np.interp(s, plan["src"], plan["out"])."""
    nk = number_kicks(onsets, beat_a, smooth)
    if nk is None:
        return None
    kk, ts, n_kept = nk
    kept = range(n_kept)
    T_k = ts[0] / v_g + (kk - kk[0]) * beat_b                   # default: a constant grid at B's tempo
    if target_fn is not None:                                    # or: wherever B's own kicks are (target_fn(ts) -> output s)
        tg = target_fn(ts)
        if tg is None:
            return None
        T_k = np.maximum.accumulate(np.asarray(tg, float) + np.arange(len(tg)) * 1e-6)
    d = np.diff(ts)
    v_int = np.clip(d / np.maximum(np.diff(T_k), 1e-3), v_g * (1 - v_clip), v_g * (1 + v_clip))
    v_knot = np.concatenate([[v_int[0]], 0.5 * (v_int[:-1] + v_int[1:]), [v_int[-1]]])
    T0 = float(T_k[0])                                          # constant speed (ts[0]/T0) up to the first knot
    v_pre = float(np.clip(ts[0] / max(T0, 1e-3), v_g * (1 - v_clip), v_g * (1 + v_clip)))
    T0 = ts[0] / v_pre
    T = np.concatenate([[0.0], T0 + np.concatenate([[0.0], np.cumsum(d / v_int)])])
    times = T.tolist() + []
    speeds = [v_pre] + v_knot.tolist()
    grid = np.arange(0.0, T[-1] + n_src_sec / v_g + 1.0, 0.001)
    sp = np.interp(grid, times, speeds)
    src = np.concatenate([[0.0], np.cumsum(sp[:-1] * np.diff(grid))])
    return {"times": times, "speeds": speeds, "src": src, "out": grid, "n_kicks": int(len(kept)),
            "v_min": float(v_int.min()), "v_max": float(v_int.max())}


def shift_samples(x, s):
    """x (C, N) delayed by s samples (s > 0: zeros first) or advanced (s < 0: the first |s| samples dropped); same length."""
    s = int(s)
    n = x.shape[-1]
    if s == 0:
        return x
    out = np.zeros_like(x)
    if s > 0:
        if s < n:
            out[..., s:] = x[..., :n - s]
    elif -s < n:
        out[..., :n + s] = x[..., -s:]
    return out


def kick_env(audio, sr=44100, band=(40.0, 150.0)):
    """40-150 Hz band -> Hilbert envelope -> low-passed at 40 Hz -> zero-mean.
    Isolates kick drum transient pulses across clips."""
    mono = audio.mean(0) if audio.ndim > 1 else audio
    sos_bp = butter(4, band, "bandpass", fs=sr, output="sos")
    b = sosfiltfilt(sos_bp, mono)
    e = np.abs(hilbert(b))
    sos_lp = butter(2, 40.0, "low", fs=sr, output="sos")
    e = sosfiltfilt(sos_lp, e)
    return e - e.mean()


def phase_shift(a_seg, b_seg, beat_samples, sr=44100, penalty=0.05, span=0.25):
    """The delay s (samples) that, applied to B, maximises the normalised correlation of the kick envelopes of A and B
    over +-`span` of a beat (spec R0.3: 1/4), with a mild penalty on large shifts.
    s > 0 means B is EARLY and must be delayed: to apply it to a window START use  b_lo -= s  (the window then reads
    source[b_lo - s ...], so B's content appears s samples later). Returns (s, ncc_at_s, ncc_at_0).
    Vectorised: the normalisation uses cumulative sums, not a loop over slices."""
    a, b = kick_env(a_seg, sr=sr), kick_env(b_seg, sr=sr)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    m = max(1, int(round(beat_samples * span)))
    c = fftconvolve(a, b[::-1], mode="full")                 # c[n-1+s] = sum_j a[j] b[j-s]: b delayed by s lines up with a
    sa = np.concatenate([[0.0], np.cumsum(a * a)])
    sb = np.concatenate([[0.0], np.cumsum(b * b)])
    ss = np.arange(-m, m + 1)
    lo_a, lo_b = np.maximum(0, ss), np.maximum(0, -ss)
    ov = n - np.abs(ss)
    na = np.sqrt(sa[lo_a + ov] - sa[lo_a]) * np.sqrt(sb[lo_b + ov] - sb[lo_b])
    v = c[n - 1 + ss] / np.maximum(na, 1e-12)
    k = int(np.argmax(v - penalty * np.abs(ss) / m))
    return int(ss[k]), float(v[k]), float(v[m])


def kick_grid_shift(a_seg, b_seg, beat_samples, sr=44100, span=0.5):
    """Phase alignment from the kick ONSETS themselves (GHOST-NOTE 2026-10-13). phase_shift() correlates kick envelopes over
    +-1/4 beat; on 21 it returned exactly the 1/4-beat limit at NCC 0.26, i.e. it hit its edge instead of finding a peak,
    and B's kicks stayed ~60 ms off a perfectly clean A grid. Here: for every A kick the signed offset to the nearest B kick
    (grid_offsets_ms, wrapped to +-half an inter-onset interval, positive = B late); the shift is minus the median offset.
    Returns (s, n_kicks_used, spread_ms) with phase_shift's sign (s > 0: B is early, delay it; apply as b_lo -= s). s is
    clipped to +-`span` of a beat; spread_ms = median absolute deviation of the offsets about their median (small = one grid,
    large = the kicks do not form a common grid at any shift). Returns (0, 0, nan) with < 3 kicks in either clip."""
    ta, tb = kick_onsets(a_seg, sr), kick_onsets(b_seg, sr)
    ta, off = grid_offsets_ms(ta, tb)
    if len(off) < 3:
        return 0, 0, float("nan")
    med = float(np.median(off))
    spread = float(np.median(np.abs(off - med)))
    m = span * beat_samples
    s = int(round(np.clip(-med / 1000.0 * sr, -m, m)))
    return s, int(len(off)), spread


def plan_tempo(bpm_a, bpm_b, threshold=5.0, up_share=0.65, slew=0.5):
    """Shared-tempo plan for one transition (GHOST-NOTE 2026-10-13, from the owner's design). BOTH clips move, the slower one more
    (speeding up sounds better than slowing down): shared tempo t* = lo + up_share*gap. Smooth ramps (<= `slew` BPM/bar) in A's
    last half / B's first half, constant through the crossfade window. If gap > `threshold`, A's total bend is capped at its share
    of `threshold` (up_share*threshold if A is the slower clip, else (1-up_share)*threshold) and B takes the rest: B plays the
    window at t*, then bends SUDDENLY by (|dev_B| - threshold) at its first downbeat after the window and ramps slowly through the
    last `threshold` BPM to native. Returns dict(t_star, dev_a, dev_b, sudden_b, slow_a_bars, slow_b_bars, big_gap)."""
    gap = abs(bpm_a - bpm_b)
    lo = min(bpm_a, bpm_b)
    big = gap > threshold
    if not big:
        t = lo + up_share * gap
    else:
        a_slower = bpm_a < bpm_b
        da = (up_share if a_slower else 1.0 - up_share) * threshold
        t = bpm_a + da if a_slower else bpm_a - da
    dev_a, dev_b = t - bpm_a, t - bpm_b
    sudden = max(0.0, abs(dev_b) - threshold) if big else 0.0
    slow_b = abs(dev_b) - sudden
    return {"t_star": float(t), "dev_a": float(dev_a), "dev_b": float(dev_b), "sudden_b": float(sudden),
            "slow_a_bars": abs(dev_a) / slew, "slow_b_bars": slow_b / slew, "big_gap": bool(big)}


def fit_window(a_db, b_db, a_len, b_len, bar, w_max, w_min=4, step=2):
    """Largest even bar count w <= w_max (>= w_min) whose window fits BOTH clips, plus the (a_lo, b_lo) sample starts.
    GHOST-NOTE 2026-10-13: the owner heard B 'start out of the blue' -- the window was centred on the structural boundary, and for
    11 of 31 transitions that put B's window start before sample 0 of B (zero-padded, up to 7 s), so B began hard mid-window.
    a_db/b_db: snapped downbeats (samples) of A (stretched time base) and B; a_len/b_len: clip lengths (samples); bar: samples/bar.
    Both windows are shifted together by a whole number of bars (so both stay on downbeats) when one would leave its clip; if a
    shift would push the other out, w shrinks. Returns (w, a_lo, b_lo) or None."""
    for w in range(int(w_max), int(w_min) - 1, -int(step)):
        L = int(round(w * bar))
        a_lo, b_lo = int(a_db) - L // 2, int(b_db) - L // 2
        late = max(0, -b_lo, -a_lo)                              # one of them starts before sample 0
        early = max(0, a_lo + L - a_len, b_lo + L - b_len)       # one of them ends after the clip
        if late and early:
            continue
        s = int(np.ceil(late / bar)) * int(round(bar)) if late else -int(np.ceil(early / bar)) * int(round(bar))
        a2, b2 = a_lo + s, b_lo + s
        if min(a2, b2) >= 0 and a2 + L <= a_len and b2 + L <= b_len:
            return w, a2, b2
    return None


# ---------------------------------------------------------------------------------------------
# per-clip tempo curve (shared-tempo plan): ramps in quiet bars, constant through the windows
# ---------------------------------------------------------------------------------------------

def bar_energy(x, db, sr=44100):
    """Mean-square energy of (C, N) or (N,) audio in each bar between consecutive downbeats `db` (s). len(db)-1 values."""
    m = np.asarray(x, dtype=np.float64)
    m = m.mean(0) if m.ndim == 2 else m
    e = []
    for a, b in zip(db[:-1], db[1:]):
        seg = m[int(a * sr):int(b * sr)]
        e.append(float((seg ** 2).mean()) if len(seg) else 0.0)
    return np.array(e)


def quiet_run(energy, lo, hi, n):
    """First bar of the n-bar run inside bars [lo, hi) with the lowest mean energy. A zone shorter than n returns lo (the caller
    then ramps faster than the slew limit and says so)."""
    lo, hi = max(0, int(lo)), min(len(energy), int(hi))
    if hi - lo <= n:
        return lo
    c = np.convolve(energy[lo:hi], np.ones(n) / n, mode="valid")
    return lo + int(np.argmin(c))


def build_tempo_curve(native, db, energy, in_plan=None, out_plan=None, w_bars=8, margin=2, slew=0.5, i_in=None, i_out=None, bounded=True):
    """Breakpoints [(source s, bpm)] for ONE clip. native: its tempo; db: downbeats (s); energy: per-bar energy (len(db)-1).
    out_plan / in_plan: plan_tempo() results for the transition where this clip is A / B (None for the first / last clip).
    i_out / i_in: downbeat index of the window centre for those transitions. Rules (the owner's design): constant at the
    shared tempo through each window (+margin bars); A's ramp native -> t* in the QUIETEST bars of the clip's last half, ending
    before the window; B's ramp t* -> native in the quietest bars of the first half, starting after the window; when B's
    deviation exceeds the threshold, a sudden one-bar bend of plan['sudden_b'] at the first downbeat after the window precedes
    the slow ramp. Returns (breakpoints, notes) with notes = {'a_ramp': (start_bar, n), 'b_ramp': ..., 'compressed': bool}."""
    nb = len(db) - 1
    half = w_bars // 2
    pts = [(float(db[0]), native)]
    notes = {"compressed": False}
    b_end = None
    if in_plan is not None and i_in is not None:
        t_in = in_plan["t_star"]
        b_end = min(nb - 1, (i_in + w_bars if bounded else max(i_in, half) + half) + margin)   # first bar after the window's constant zone
        pts = [(float(db[0]), t_in), (float(db[b_end]), t_in)]
        cur, dev = t_in, in_plan["dev_b"]
        if in_plan["sudden_b"] > 0:
            cur = t_in - np.sign(dev) * in_plan["sudden_b"]
            pts.append((float(db[min(b_end + 1, nb)]), cur))
            b_end = min(b_end + 1, nb)
        n = max(1, int(np.ceil(abs(cur - native) / slew)))
        hi = max(b_end + 1, nb // 2)
        j = quiet_run(energy, b_end, hi, n)
        if hi - b_end < n:
            notes["compressed"] = True
        j2 = max(j + 1, min(nb, j + n))
        if j > b_end:
            pts.append((float(db[j]), cur))
        pts.append((float(db[j2]), native))
        notes["b_ramp"] = (j, j2 - j)
    if out_plan is not None and i_out is not None:
        t_out = out_plan["t_star"]
        a_start = max(0, i_out - (w_bars if bounded else half) - margin)   # the constant zone starts here
        n = max(1, int(np.ceil(abs(t_out - native) / slew)))
        last_bar = int(np.searchsorted(db, pts[-1][0])) if pts[-1][0] > db[0] else 0   # after any ramp already placed (B role)
        lo = max(nb // 2, last_bar)
        if a_start - lo >= n:
            j = quiet_run(energy, lo, a_start, n)
        else:                                   # no room in the last half: use the bars just before the window, back to the B ramp
            notes["compressed"] = True
            j = max(last_bar, a_start - n)
        j2 = max(j + 1, min(nb, j + n))
        notes["a_in_window_bars"] = int(max(0, j2 - a_start))   # ramp bars that overlap the constant zone: the clip is too short
        if pts[-1][0] < db[j]:
            pts.append((float(db[j]), native))
        pts.append((float(db[j2]), t_out))
        pts.append((float(db[-1]) + 600.0, t_out))                    # held to the end of the clip
        notes["a_ramp"] = (j, j2 - j)
    else:
        pts.append((float(db[-1]) + 600.0, pts[-1][1]))
    return pts, notes


def curve_to_plan(points, native, n_src_sec):
    """Source-time tempo breakpoints -> the plan dict of tv_stretch_plan (times/speeds over OUTPUT time for
    bungee_stretch_schedule, and the realised monotone src<->out map at 1 ms). speed = bpm / native; linear in source time
    between breakpoints, constant before the first and after the last."""
    s = np.array([p[0] for p in points], float)
    v = np.array([p[1] for p in points], float) / native
    grid_s = np.arange(0.0, n_src_sec + 1.0, 0.001)
    vs = np.interp(grid_s, s, v)
    out = np.concatenate([[0.0], np.cumsum(np.diff(grid_s) / vs[:-1])])              # output time of each source instant
    ks = np.unique(np.round(np.linspace(0, len(grid_s) - 1, 400)).astype(int))
    times, speeds = out[ks].tolist(), vs[ks].tolist()
    # realised map on an output grid, consistent with how bungee_stretch_schedule reads the speed (linear over OUTPUT time)
    og = np.arange(0.0, out[-1] + 1.0, 0.001)
    sp = np.interp(og, times, speeds)
    src = np.concatenate([[0.0], np.cumsum(sp[:-1] * np.diff(og))])
    return {"times": times, "speeds": speeds, "src": src, "out": og, "n_kicks": 0,
            "v_min": float(vs.min()), "v_max": float(vs.max())}


def fit_window_bounded(a_end, b_start, a_len, b_len, bar, w_max, w_min=4, step=2):
    """Window placement without centring: A's window ENDS at its end bound (downbeat-snapped, samples), B's window STARTS at its
    start bound, so each clip contributes only music it is allowed to use and nothing is zero-padded (the centred layout needed
    L/2 of B before its start, which most clips do not have). Largest even w <= w_max that fits; returns (w, a_lo, b_lo) or None."""
    for w in range(int(w_max), int(w_min) - 1, -int(step)):
        L = int(round(w * bar))
        a_lo, b_lo = int(a_end) - L, int(b_start)
        if a_lo >= 0 and b_lo + L <= b_len and int(a_end) <= a_len:
            return w, a_lo, b_lo
    return None
