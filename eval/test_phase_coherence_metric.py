#!/usr/bin/env python3
"""test_phase_coherence_metric.py — validate the HF phase-coherence metric before we trust
the numbers it produces (the 0.045 ceiling, and the #64 regression-ceiling diagnostic).

The metric (from eval/treble_phase_diagnosis.py:hf_metrics) is the magnitude-weighted
circular mean of the recon-vs-orig STFT phase difference above HF_HZ:
    phase_coh = | sum_k w_k exp(i (angle(Sr_k) - angle(So_k))) | ,  w_k = |So_k| / sum|So|
This test pins its behaviour on synthetic signals with KNOWN phase relationships so a wrong
reading later is a real finding, not a metric artifact. TDD: written to fail if the metric
misbehaves.

Run: /home/kim/Projects/SAO/.venv/bin/python eval/test_phase_coherence_metric.py
"""
import numpy as np
from scipy.signal import stft

SR = 44100
HF_HZ = 8000


def phase_coh(orig, recon, sr=SR):
    """The metric under test — copied verbatim from treble_phase_diagnosis.hf_metrics."""
    f, _, So = stft(orig, fs=sr, nperseg=2048, noverlap=1536)
    _, _, Sr = stft(recon, fs=sr, nperseg=2048, noverlap=1536)
    n = min(So.shape[1], Sr.shape[1])
    So, Sr = So[:, :n], Sr[:, :n]
    hf = f > HF_HZ
    mag_o = np.abs(So[hf])
    dphi = np.angle(Sr[hf]) - np.angle(So[hf])
    w = mag_o / (mag_o.sum() + 1e-9)
    return float(np.abs((w * np.exp(1j * dphi)).sum()))


def broadband(seed=0, n=SR):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n).astype(np.float64)
    # give it real HF energy so the >8kHz bins aren't just noise floor
    return x


def randomize_phase_hf(x, sr=SR, seed=1):
    """Return a signal identical in magnitude but with randomized phase above HF_HZ."""
    f, t, S = stft(x, fs=sr, nperseg=2048, noverlap=1536)
    rng = np.random.default_rng(seed)
    hf = f > HF_HZ
    S2 = S.copy()
    ph = rng.uniform(-np.pi, np.pi, size=S2[hf].shape)
    S2[hf] = np.abs(S2[hf]) * np.exp(1j * ph)
    from scipy.signal import istft
    _, y = istft(S2, fs=sr, nperseg=2048, noverlap=1536)
    return y[: len(x)]


def check(name, got, lo, hi):
    ok = lo <= got <= hi
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {got:.4f} (expect {lo:.2f}..{hi:.2f})")
    return ok


def main():
    x = broadband()
    allok = True

    # 1. identical signal -> coherence 1.0
    allok &= check("identical recon", phase_coh(x, x), 0.999, 1.0001)

    # 2. randomized HF phase (magnitude preserved) -> ~0 (this is our 0.045 regime)
    xr = randomize_phase_hf(x)
    allok &= check("randomized HF phase", phase_coh(x, xr), 0.0, 0.20)

    # 3. GLOBAL constant phase offset -> metric is INVARIANT (=1). This is the crux of the
    #    global-phase-invariance discussion: a constant dphi factors out of |sum w e^{i dphi}|.
    #    (Confirms the metric measures RELATIVE phase structure, not absolute offset.)
    Xf = np.fft.rfft(x)
    x_rot = np.fft.irfft(Xf * np.exp(1j * 0.7), n=len(x))
    allok &= check("global phase offset (should stay ~1)", phase_coh(x, x_rot), 0.95, 1.0001)

    # 4. sub-sample time shift = frequency-dependent (linear) phase = group delay -> drops.
    #    A pure delay multiplies bin k by e^{-i w_k tau}; the mag-weighted circular sum of a
    #    frequency-ramped phase partially cancels -> coherence < 1 (dispersion), > random.
    shift = 7  # samples
    x_del = np.roll(x, shift)
    allok &= check("7-sample delay (group delay, <1)", phase_coh(x, x_del), 0.0, 0.95)

    # 5. small phase jitter -> high but below 1 (monotone sanity)
    f, t, S = stft(x, fs=SR, nperseg=2048, noverlap=1536)
    rng = np.random.default_rng(3)
    hf = f > HF_HZ
    S2 = S.copy()
    S2[hf] = np.abs(S2[hf]) * np.exp(1j * (np.angle(S2[hf]) + rng.normal(0, 0.3, S2[hf].shape)))
    from scipy.signal import istft
    _, xj = istft(S2, fs=SR, nperseg=2048, noverlap=1536)
    cj = phase_coh(x, xj[: len(x)])
    allok &= check("small jitter sigma=0.3 (high, <1)", cj, 0.80, 0.999)

    print(f"\n{'ALL PASS — metric trustworthy' if allok else 'FAILURES — do not trust the metric'}")
    raise SystemExit(0 if allok else 1)


if __name__ == "__main__":
    main()
