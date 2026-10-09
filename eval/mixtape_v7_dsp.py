#!/usr/bin/env python
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
