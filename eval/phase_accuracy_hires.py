#!/usr/bin/env python
"""phase_accuracy_hires.py — 1000-point phase-accuracy vs frequency curve (Kim 2026-08-01,
high-res follow-up to the 8-point octave ladder).

Metric per stimulus frequency f: how cleanly do the 256 latent channels' sample-shift
trajectories oscillate AT f? Measured by LOCK-IN (matched-filter) coherence, so cost is
~constant per frequency instead of the fixed 4411-shift FFT sweep:
  adaptive shift grid: ~40 shift-samples/period x ~6 periods (step & span tuned to f, so
  Nyquist for f is always satisfied and ~6 periods are always spanned -> ~150 encodes/f);
  per channel c: a = traj_c - mean; coh_c = |Σ a·e^{-i2πfδ/SR}| / Σ|a|  (0..~π/4);
  phase_accuracy(f) = mean_c(coh_c) / (π/4)  [pure sinusoid -> 1, noise -> ~0].
Also records, per channel, the frequency of its MAX coherence (characteristic freq) so
HF-specific channels can be identified (fixes treble_phase_diagnosis Test B).

1000 log-spaced freqs 40 Hz .. 20 kHz. ~1-2 h. Arrays saved (coh matrix [1000,256]).

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/phase_accuracy_hires.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import json
import time
from pathlib import Path

import numpy as np
import torch

from stable_audio_3 import StableAudioModel

OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/phase_accuracy_hires")
SR = 44100
CLIP_S = 6.0
N_FREQS = 1000
FMIN, FMAX = 40.0, 20000.0
BATCH = 48
CENTER = (18, 48)          # analysis frames of ~64
QUARTER = np.pi / 4        # pure-sinusoid coherence normalizer


def grid_for(f):
    step = max(1, int(round(SR / (f * 40))))       # ~40 shift-samples per period
    n = int(np.clip(round(6 * SR / f / step), 32, 192))
    return np.arange(n) * step                     # shift offsets (samples)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    freqs = np.logspace(np.log10(FMIN), np.log10(FMAX), N_FREQS)
    n_clip = int(SR * CLIP_S)
    max_shift = int(grid_for(FMIN)[-1]) + 1
    t = np.arange(n_clip + max_shift + 1) / SR

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype
    c0, c1 = CENTER

    coh = np.zeros((N_FREQS, 256), dtype=np.float32)   # per (freq, channel) coherence
    t0 = time.time()
    for fi, f in enumerate(freqs):
        y = (0.5 * np.sin(2 * np.pi * f * t)).astype(np.float32)
        shifts = grid_for(f)
        Z = []
        for s0 in range(0, len(shifts), BATCH):
            sh = shifts[s0:s0 + BATCH]
            batch = np.stack([y[d:d + n_clip] for d in sh])
            x = torch.tensor(batch[:, None, :]).repeat(1, 2, 1)
            with torch.no_grad():
                z = cdm.pretransform.encode(x.to(device, mdtype))
            Z.append(z.float().cpu().numpy())
        Z = np.concatenate(Z)                          # [nshift, 256, F]
        traj = Z[:, :, c0:c1].mean(2)                  # [nshift, 256]
        a = traj - traj.mean(0)
        w = np.exp(-2j * np.pi * f * shifts / SR)      # [nshift]
        proj = np.abs(a.T @ w)                         # [256]
        denom = np.abs(a).sum(0) + 1e-9
        coh[fi] = np.clip((proj / denom) / QUARTER, 0, 1)
        if (fi + 1) % 50 == 0:
            el = time.time() - t0
            print(f"[{fi+1}/{N_FREQS}] f={f:.0f}Hz acc={coh[fi].mean():.3f} "
                  f"({el:.0f}s, eta {el/(fi+1)*(N_FREQS-fi-1):.0f}s)", flush=True)

    accuracy = coh.mean(1)                              # the curve
    char_freq = freqs[coh.argmax(0)]                   # per-channel characteristic freq
    np.savez_compressed(OUT / "curve.npz", freqs=freqs, accuracy=accuracy,
                        coh=coh.astype(np.float16), char_freq=char_freq)
    # summary knee-finder: last freq above 0.5, and above 0.8
    def last_above(th):
        idx = np.where(accuracy >= th)[0]
        return float(freqs[idx[-1]]) if len(idx) else None
    summary = {"n_freqs": N_FREQS, "f_range": [FMIN, FMAX],
               "acc_at": {f"{int(fr)}Hz": round(float(accuracy[np.argmin(np.abs(freqs-fr))]), 3)
                          for fr in (100, 500, 1000, 2000, 4000, 7000, 10000, 14000, 18000)},
               "last_freq_acc>=0.8": last_above(0.8), "last_freq_acc>=0.5": last_above(0.5),
               "hf_channels_char>7kHz": int((char_freq > 7000).sum()),
               "method": "adaptive-grid lock-in coherence, normalized to pure-sinusoid",
               "result": None, "kim_feedback": None}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print("SUMMARY:", json.dumps(summary["acc_at"]))
    print(f"knees: acc>=0.8 to {summary['last_freq_acc>=0.8']}, "
          f">=0.5 to {summary['last_freq_acc>=0.5']} Hz; "
          f"{summary['hf_channels_char>7kHz']} channels peak >7kHz")
    print(f"[done] {time.time()-t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
