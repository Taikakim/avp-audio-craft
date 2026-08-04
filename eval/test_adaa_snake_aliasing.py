#!/usr/bin/env python3
"""test_adaa_snake_aliasing.py — de-risk Track A's ADAA-SnakeBeta arm (task #62) on CPU.

The clarity plan replaces the HF-repair net's RAW Snake (x + (1/a) sin^2(a x)) with an
anti-derivative-anti-aliased (ADAA) Snake at 2x oversampling. The report (Aliasing-Free
Neural Audio Synthesis, 2512.20211) claims ADAA@2x matches RAW@4x aliasing suppression at a
quarter of the compute. Before wiring ADAA into the ~2.5M post-net, verify the DSP claim
directly: pass a strong tone through each variant, measure folded-back aliasing energy
against a near-alias-free 16x-oversampled reference.

Snake:            f(x)  = x + (1/a) sin^2(a x)
Anti-derivative:  F(x)  = x^2/2 + x/(2a) - sin(2 a x)/(4 a^2)
1st-order ADAA:   f_ADAA(x_n) = (F(x_n) - F(x_{n-1})) / (x_n - x_{n-1})   [avg of f over the
                  step -> band-limits the nonlinearity], midpoint fallback when |dx| tiny.

Run: /home/kim/Projects/SAO/.venv/bin/python eval/test_adaa_snake_aliasing.py
"""
import numpy as np
from scipy.signal import resample_poly

A = 1.0            # Snake alpha (learnable per-channel freq param; fix for the test)
AMP = 2.5          # input amplitude: large enough that sin^2(a*A) makes strong harmonics
SR = 44100
F0 = 7000.0        # tone; harmonics 2f0=14k (ok), 4f0=28k, 6f0=42k -> fold below Nyquist
DUR = 0.25


def snake(x, a=A):
    return x + (1.0 / a) * np.sin(a * x) ** 2


def snake_antideriv(x, a=A):
    return x * x / 2.0 + x / (2.0 * a) - np.sin(2.0 * a * x) / (4.0 * a * a)


def snake_adaa(x, a=A):
    """1st-order anti-derivative anti-aliasing of Snake (applied at whatever rate x is at)."""
    xm1 = np.concatenate([x[:1], x[:-1]])
    dx = x - xm1
    F = snake_antideriv(x, a)
    Fm1 = snake_antideriv(xm1, a)
    out = np.where(np.abs(dx) > 1e-6, (F - Fm1) / np.where(dx == 0, 1.0, dx),
                   snake((x + xm1) / 2.0, a))    # midpoint fallback
    return out


def process_os(x, factor, fn):
    """Oversample by `factor`, apply fn, decimate back (polyphase anti-alias filtering)."""
    if factor == 1:
        return fn(x)
    up = resample_poly(x, factor, 1)
    y = fn(up)
    return resample_poly(y, 1, factor)


def alias_energy(y, ref):
    """Energy in y at frequency bins where the alias-free reference is silent, over total."""
    n = min(len(y), len(ref))
    Y = np.abs(np.fft.rfft(y[:n]))
    R = np.abs(np.fft.rfft(ref[:n]))
    # reference "signal" bins = where R is meaningfully above its own floor
    sig = R > (0.001 * R.max())
    total = (Y ** 2).sum() + 1e-20
    aliased = (Y[~sig] ** 2).sum()
    return float(aliased / total)


def main():
    t = np.arange(int(SR * DUR)) / SR
    x = AMP * np.sin(2 * np.pi * F0 * t)

    # near-alias-free reference: raw Snake at 16x oversampling
    ref = process_os(x, 16, snake)

    variants = [
        ("raw Snake @1x   ", process_os(x, 1, snake)),
        ("raw Snake @2x   ", process_os(x, 2, snake)),
        ("raw Snake @4x   ", process_os(x, 4, snake)),
        ("ADAA Snake @1x  ", process_os(x, 1, snake_adaa)),
        ("ADAA Snake @2x  ", process_os(x, 2, snake_adaa)),
    ]
    print(f"input: {F0:.0f} Hz tone, amp {AMP}, alpha {A}, SR {SR}")
    print(f"aliasing energy fraction (lower=better; ref=raw@16x):\n")
    res = {}
    for name, y in variants:
        ae = alias_energy(y, ref)
        res[name.strip()] = ae
        print(f"  {name}: {ae:.3e}   ({10*np.log10(ae+1e-20):.1f} dB)")

    raw1 = res["raw Snake @1x"]
    raw4 = res["raw Snake @4x"]
    adaa2 = res["ADAA Snake @2x"]
    print("\n=== claims under test ===")
    c1 = adaa2 < 0.5 * raw1
    c2 = adaa2 <= raw4 * 3.0        # "ADAA@2x ~ raw@4x" (within 3x, generous for 1st-order)
    print(f"  [{'PASS' if c1 else 'FAIL'}] ADAA@2x beats raw@1x   : "
          f"{raw1/max(adaa2,1e-20):.1f}x less aliasing")
    print(f"  [{'PASS' if c2 else 'FAIL'}] ADAA@2x ~ raw@4x       : "
          f"ADAA@2x {adaa2:.2e} vs raw@4x {raw4:.2e}")
    print(f"\n{'BOTH PASS — ADAA@2x is the right cheap anti-alias for the post-net' if (c1 and c2) else 'CHECK — inspect above'}")
    raise SystemExit(0 if (c1 and c2) else 1)


if __name__ == "__main__":
    main()
