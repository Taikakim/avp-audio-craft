#!/usr/bin/env python
"""phase_shift_sweep.py — G2b: sub-frame phase coding in SAME (Kim's design 2026-07-31:
"sweep through a clip sample by sample... one sample forward at a time, at least for
100ms or the frame length").

G2 (band-envelope readout) closed the SLOW-MODULATION-readout question. THIS probe asks
the finer, encoder-level question: how does the code move under sub-frame time shifts?
For shift delta = 0..4409 samples (1-sample steps; frame = 4096 samples = 93 ms):
encode audio[delta:] and track z(delta).

Discriminators:
  (1) DRIFT: mean per-frame cosine z(delta) vs z(0) over center frames — smooth monotone
      = envelope-style interpolation; structure = something richer.
  (2) CLOSURE: z(4096) frame-shifted-by-1 vs z(0) — the codec should return to (nearly)
      the same code one frame later; deviation measures boundary pathology.
  (3) delta-FFT per channel: sampling along delta at 44.1 kHz resolves oscillations up
      to 22 kHz. A channel that linearly carries a partial's PHASE must oscillate at that
      partial's frequency (440 Hz tone -> 440 Hz sinusoid in the channel trajectory).
      Peaks at stimulus partials = literal sample-level phase coding; their absence =
      phase discarded below the frame scale (decoder's job), settling G2b.
  (4) trajectory geometry (tone stimulus): PCA dim + circularity of one frame-vector's
      path over delta — rotational structure = phase-as-rotation coding (the Cl(2)+ /
      eigenplane-SO(2) connection from G3).

Stimuli: pure tone 440 Hz, three-partial chord (220/330/495), and 2 real corpus segments.
Batched encodes (49 shifts/forward). Arrays saved for reanalysis.

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/phase_shift_sweep.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from stable_audio_3 import StableAudioModel

OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/phase_shift_sweep")
CORPUS = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")
SR = 44100
CLIP_S = 10.0
MAX_SHIFT = 4410          # ~100 ms, > one 4096-sample frame
BATCH = 49
CENTER = (30, 80)         # analysis frames (of ~107)


def stimuli():
    t = np.arange(int(SR * CLIP_S) + MAX_SHIFT + 1) / SR
    if os.environ.get("PHASE_LADDER") == "1":
        # frequency-ceiling ladder (Kim's question 2026-08-01): pure tones, octave steps
        return {f"ladder_{f}hz": 0.5 * np.sin(2 * np.pi * f * t)
                for f in (110, 220, 440, 880, 1760, 3520, 7040, 14080)}
    out = {
        "tone440": 0.5 * np.sin(2 * np.pi * 440 * t),
        "chord": (0.3 * np.sin(2 * np.pi * 220 * t) + 0.3 * np.sin(2 * np.pi * 330 * t)
                  + 0.3 * np.sin(2 * np.pi * 495 * t)),
    }
    reals = [d for d in sorted(CORPUS.iterdir()) if (d / "full_mix.flac").exists()][:2]
    for d in reals:
        a, sr = sf.read(d / "full_mix.flac", dtype="float32", always_2d=True)
        seg = a[int(60 * sr): int(60 * sr) + len(t)].mean(1)
        out[f"real_{d.name[:16].replace(' ', '_')}"] = seg
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype
    n_clip = int(SR * CLIP_S)

    results = {}
    for name, y in stimuli().items():
        y = y.astype(np.float32)
        Zs = []
        for s0 in range(0, MAX_SHIFT + 1, BATCH):
            shifts = list(range(s0, min(s0 + BATCH, MAX_SHIFT + 1)))
            batch = np.stack([y[d:d + n_clip] for d in shifts])
            x = torch.tensor(batch[:, None, :]).repeat(1, 2, 1)   # stereo-dup mono
            with torch.no_grad():
                z = cdm.pretransform.encode(x.to(device, mdtype))
            Zs.append(z.float().cpu().numpy())
        Z = np.concatenate(Zs)                     # [4411, 256, F]
        F = Z.shape[-1]
        c0, c1 = CENTER
        Zc = Z[:, :, c0:c1]                        # [D, 256, Fc]

        # (1) drift
        z0 = Zc[0]
        num = (Zc * z0).sum(1)
        den = np.linalg.norm(Zc, axis=1) * np.linalg.norm(z0, axis=0) + 1e-9
        drift = (num / den).mean(1)                # [D]
        # (2) closure at one frame
        z_shift = Z[4096, :, c0 - 1:c1 - 1]
        cl_num = (z_shift * z0).sum(0)
        cl = float((cl_num / (np.linalg.norm(z_shift, axis=0) *
                              np.linalg.norm(z0, axis=0) + 1e-9)).mean())
        # (3) delta-FFT per channel (mean traj over center frames, detrended)
        traj = Zc.mean(2)                          # [D, 256]
        traj = traj - traj.mean(0)
        spec = np.abs(np.fft.rfft(traj, axis=0))   # [D/2+1, 256]
        freqs = np.fft.rfftfreq(traj.shape[0], d=1 / SR)
        band = freqs > 50
        peak_bin = spec[band].argmax(0)
        peak_freq = freqs[band][peak_bin]          # [256] per-channel dominant freq
        peak_power = spec[band].max(0)
        floor = np.median(spec[band], axis=0) + 1e-9
        osc_score = peak_power / floor             # [256] oscillation prominence
        top = np.argsort(osc_score)[::-1][:8]
        # (4) trajectory geometry on the mean vector path
        U, S, _ = np.linalg.svd(traj, full_matrices=False)
        dim90 = int(np.searchsorted(np.cumsum(S**2) / (S**2).sum(), 0.9) + 1)

        results[name] = {
            "drift_at": {str(d): round(float(drift[d]), 4)
                         for d in (1, 8, 64, 512, 1024, 2048, 3072, 4096)},
            "closure_1frame": round(cl, 4),
            "traj_dim90": dim90,
            "top_osc_channels": [
                {"ch": int(c), "freq_hz": round(float(peak_freq[c]), 1),
                 "prominence": round(float(osc_score[c]), 1)} for c in top],
        }
        np.savez_compressed(OUT / f"sweep_{name}.npz",
                            drift=drift, traj=traj.astype(np.float16),
                            osc_score=osc_score, peak_freq=peak_freq)
        print(f"[{name}] drift@1={drift[1]:.4f} @2048={drift[2048]:.4f} "
              f"@4096={drift[4096]:.4f} closure={cl:.4f} dim90={dim90}")
        print(f"  top osc: " + ", ".join(
            f"ch{c['ch']}@{c['freq_hz']}Hz(x{c['prominence']:.0f})"
            for c in results[name]["top_osc_channels"][:5]), flush=True)

    (OUT / "results.json").write_text(json.dumps(
        {"results": results, "max_shift": MAX_SHIFT, "clip_s": CLIP_S,
         "design": "Kim 2026-07-31: 1-sample shift sweep over one frame length",
         "verdict_rule": "stimulus-partial peaks in channel delta-FFTs (tone440 -> 440Hz "
                         "etc.) = sample-level phase coding exists; absence + smooth "
                         "drift = phase fully sub-frame-discarded (decoder territory), "
                         "G2b closes consistent with G2.",
         "result": None, "kim_feedback": None}, indent=2))
    print(f"[done] -> {OUT}/results.json")


if __name__ == "__main__":
    main()
