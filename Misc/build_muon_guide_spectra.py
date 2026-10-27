#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-27)
"""Spectra of the two air-head clips in the Muon guide (section 9) -> blog/assets/muon-survival-guide/air_spectra.png and
air_spectrogram_diff.png.

Whole 48 s renders (the guide plays an 18 s excerpt, 4-22 s). STFT as asked in the review of 2026-10-26: 2048-sample Hann
windows, 50% overlap (hop 1024), FFT zero-padded 2x (4096 points). Channels are averaged in power. The difference is
epoch 12 minus epoch 3 in dB, per bin. Source paths are internal and are not printed into the figures.
Run (CPU): /home/kim/Projects/mir/mir/bin/python /home/kim/Projects/SAO/Misc/build_muon_guide_spectra.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from scipy.signal import stft  # noqa: E402

OUT = Path("/home/kim/Projects/SAO/blog/assets/muon-survival-guide")
SRC = Path("/run/media/kim/Mantu/latch_sweep/air_head_2026-10-15_overnight/epoch_sweep/clips")
CLIPS = {"epoch 3": SRC / "O5_ep03.wav", "epoch 12": SRC / "O5_ep12.wav"}
WIN, HOP, NFFT = 2048, 1024, 4096
EXCERPT = (4.0, 22.0)          # the excerpt the guide plays
EVENT = 13.0                   # the reverse-cymbal-like sound, 0:09 in the excerpt
FLOOR = 1e-12
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 130})


def power_spectrogram(path):
    x, sr = sf.read(path, always_2d=True)
    f, t, Z = stft(x.T, fs=sr, window="hann", nperseg=WIN, noverlap=WIN - HOP, nfft=NFFT, boundary=None, padded=False)
    return f, t, (np.abs(Z) ** 2).mean(axis=0)          # mean power over channels: [freq, time]


def db(p):
    return 10 * np.log10(np.maximum(p, FLOOR))


def main():
    specs = {k: power_spectrogram(p) for k, p in CLIPS.items()}
    f, t, _ = specs["epoch 3"]
    p3, p12 = specs["epoch 3"][2], specs["epoch 12"][2]
    assert p3.shape == p12.shape, "the two renders must have the same length"
    keep = f >= 20

    # 1. Whole-track average spectra and their difference.
    fig, (a, b) = plt.subplots(2, 1, figsize=(8, 6), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    l3, l12 = db(p3.mean(axis=1)), db(p12.mean(axis=1))
    a.semilogx(f[keep], l3[keep], color="#3b6ea8", lw=1, label="epoch 3")
    a.semilogx(f[keep], l12[keep], color="#c0504d", lw=1, label="epoch 12")
    a.set_ylabel("average power (dB)")
    a.legend(frameon=False)
    a.set_title("Whole 48 s render, steered by the air head from two epochs (same seed and gain)")
    b.semilogx(f[keep], (l12 - l3)[keep], color="#444", lw=1)
    b.axhline(0, color="#999", lw=0.8)
    b.set_ylabel("epoch 12 − epoch 3 (dB)")
    b.set_xlabel("frequency (Hz)")
    b.set_xlim(20, f[-1])
    fig.tight_layout()
    fig.savefig(OUT / "air_spectra.png", bbox_inches="tight")
    plt.close(fig)

    # 2. Spectrograms of both and the per-bin difference over time.
    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    vmax = max(db(p3).max(), db(p12).max())
    for ax, (name, p) in zip(axes[:2], [("epoch 3", p3), ("epoch 12", p12)]):
        im = ax.pcolormesh(t, f[keep], db(p)[keep], shading="auto", cmap="magma", vmin=vmax - 90, vmax=vmax)
        ax.set_yscale("log")
        ax.set_ylabel("Hz")
        ax.set_title(name)
        fig.colorbar(im, ax=ax, label="dB")
    d = db(p12) - db(p3)
    im = axes[2].pcolormesh(t, f[keep], d[keep], shading="auto", cmap="RdBu_r", vmin=-12, vmax=12)
    axes[2].set_yscale("log")
    axes[2].set_ylabel("Hz")
    axes[2].set_title("epoch 12 − epoch 3 (dB, clipped at ±12; red: louder at epoch 12)")
    fig.colorbar(im, ax=axes[2], label="dB")
    for ax in axes:
        ax.axvspan(*EXCERPT, color="none", ec="#888", ls="--", lw=0.8)
        ax.axvline(EVENT, color="#0a0", lw=0.8, ls=":")
    axes[2].set_xlabel("time (s); dashed box: the excerpt in the guide; dotted line: the cymbal-like event")
    fig.tight_layout()
    fig.savefig(OUT / "air_spectrogram_diff.png", bbox_inches="tight")
    plt.close(fig)

    # Numbers for the text: band averages of the difference.
    for lo, hi in [(20, 200), (200, 2000), (2000, 8000), (8000, 16000), (16000, 22050)]:
        m = (f >= lo) & (f < hi)
        print(f"{lo}-{hi} Hz: {float((l12 - l3)[m].mean()):+.2f} dB")
    print("wrote", OUT / "air_spectra.png", OUT / "air_spectrogram_diff.png", "frames", len(t), "bins", len(f))


if __name__ == "__main__":
    main()
