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
import numpy as np
from scipy.signal import butter, sosfilt


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
    low + high matches the input in magnitude but not in phase (it is not bit-exact)."""
    low = sosfilt(lr4_sos(fc, "low", sr), audio, axis=-1)
    high = sosfilt(lr4_sos(fc, "high", sr), audio, axis=-1)
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


def drums_crossfade(a, b, sr, fc=150.0):
    """Kick (< fc, spec: drums low-passed at 150 Hz) crossfades LINEARLY, because the kicks
    sit on the shared grid and add coherently; percussion (> fc) crossfades EQUAL-POWER,
    because it is uncorrelated between clips. This is the only reason to split the drums:
    with one ramp for both bands the split does nothing."""
    al, ah = lr4_split(a, fc, sr)
    bl, bh = lr4_split(b, fc, sr)
    n = a.shape[-1]
    lin_dn, lin_up = linear_ramps(n)
    ep_dn, ep_up = equal_power_ramps(n)
    return al * lin_dn + bl * lin_up + ah * ep_dn + bh * ep_up


def crossfade(a, b, kind="equal_power"):
    """Plain crossfade of two same-shape windows (vocals, fallback `other`)."""
    n = a.shape[-1]
    dn, up = equal_power_ramps(n) if kind == "equal_power" else linear_ramps(n)
    return a * dn + b * up


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

MIR_BUNGEE_PY = "/home/kim/Projects/mir/pitch_venv/bin/python"


def bungee_stretch(audio, speed, sr=44100):
    """Time-stretch audio (C, N) using Bungee (in pitch_venv).
    speed > 1.0 speeds up (shortens duration, raises tempo).
    """
    import subprocess
    import tempfile

    if abs(float(speed) - 1.0) < 0.001:
        return audio

    with tempfile.TemporaryDirectory() as td:
        src, dst = f"{td}/in.npy", f"{td}/out.npy"
        np.save(src, audio.T)
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
        subprocess.run([MIR_BUNGEE_PY, "-c", code], check=True, capture_output=True)
        return np.load(dst).T


def kick_env(audio, sr=44100, band=(40.0, 150.0)):
    """40-150 Hz band -> Hilbert envelope -> low-passed at 40 Hz -> zero-mean.
    Isolates kick drum transient pulses across clips."""
    from scipy.signal import hilbert, sosfiltfilt
    mono = audio.mean(0) if audio.ndim > 1 else audio
    sos_bp = butter(4, band, "bandpass", fs=sr, output="sos")
    b = sosfiltfilt(sos_bp, mono)
    e = np.abs(hilbert(b))
    sos_lp = butter(2, 40.0, "low", fs=sr, output="sos")
    e = sosfiltfilt(sos_lp, e)
    return e - e.mean()


def phase_shift(a_seg, b_seg, beat_samples, sr=44100, penalty=0.05):
    """B delayed by s samples (s>0) maximises normalised correlation of kick envelopes
    over +-1/4 beat. Returns (shift_samples, ncc_best, ncc_zero)."""
    from scipy.signal import fftconvolve
    a, b = kick_env(a_seg, sr=sr), kick_env(b_seg, sr=sr)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    m = int(round(beat_samples / 4))
    c = fftconvolve(a, b[::-1], mode="full")
    best, best_score, ncc = 0, -np.inf, {}
    for s in range(-m, m + 1):
        ov = n - abs(s)
        lo_a, lo_b = max(0, s), max(0, -s)
        na = np.sqrt((a[lo_a:lo_a + ov] ** 2).sum()) * np.sqrt((b[lo_b:lo_b + ov] ** 2).sum())
        v = float(c[n - 1 + s] / max(na, 1e-12))
        ncc[s] = v
        score = v - penalty * abs(s) / m
        if score > best_score:
            best, best_score = s, score
    return best, ncc.get(best, 0.0), ncc.get(0, 0.0)

