#!/usr/bin/env python3
"""inmix_stage2_encode.py — in-mix interval floor test, STAGE 2 (SAME-encode + Δlatent).
SAME-encode the 4 arms from stage 1 and answer: does a +1-semitone melodic move on the
VOCAL, buried in a full dense mix, produce a Δlatent above the codec fidelity floor — and
does it land in the #59 melody subspace more than codec hiss does?

Δ_x = z(mix_x) - z(mix_orig), per SAME latent frame [256,T]. Reports per arm:
  frame_delta  = mean_t ||Δ[:,t]||           absolute per-frame latent move
  /fifth_calib = frame_delta / 5.6439         vs the isolated-note fifth calibration
  /fifth_inmix = frame_delta / (fifth arm)    vs THIS mix's own fifth (saturation check)
  melFrac      = mean_t ||B15 Δ[:,t]||^2/||Δ[:,t]||^2   share in the #59 melody subspace
Decision: min2 vs codecnoise. min2 >> codecnoise  => the semitone survives in-mix.

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/musicology/inmix_stage2_encode.py
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

D = Path("/home/kim/Projects/SAO/eval/musicology/inmix_floor_2026-08-06")
ROOT = Path("/home/kim/Projects/SAO")
B15 = np.load(ROOT / "lumi/melody_subspace15_v2.npz")["basis15"].astype(np.float64)  # [15,256]
MP3 = json.loads((Path("/run/media/kim/Mantu/sa3_control_runs/analysis/"
                       "mp3_latent_sensitivity_2026-08-04/results.json")).read_text())
FIFTH_CALIB = MP3["calibration"]["fifthjump_delta_norm_mean"]     # 5.6439 (isolated-note ref)
RANDOM_MEL = MP3["calibration"]["melody_random_frac_baseline"]    # 0.0586
CODEC_MEL_256 = MP3["by_bitrate"]["256"]["melody_frac_mean"]      # 0.0727 (real-mix mp3@256)
ARMS = ["orig", "min2", "fifth", "codecnoise"]


def encode(model, dev, dt, wav):
    a, sr = sf.read(wav, dtype="float32", always_2d=True)   # [N,2]
    seg = a.T                                                # [2,N]
    with torch.no_grad():
        z = model.model.pretransform.encode(torch.tensor(seg[None]).to(dev, dt))
    return z[0].float().cpu().numpy()                         # [256,T]


def frame_delta(dz):                      # dz [256,T]
    return float(np.linalg.norm(dz, axis=0).mean())


def mel_frac(dz):
    num = np.linalg.norm(B15 @ dz, axis=0) ** 2              # [T]
    den = np.linalg.norm(dz, axis=0) ** 2 + 1e-12
    return float(np.mean(num / den))


def main():
    m = StableAudioModel.from_pretrained("medium-base", device="cuda")
    dev = next(m.model.model.parameters()).device
    dt = next(m.model.model.parameters()).dtype
    Z = {a: encode(m, dev, dt, D / f"mix_{a}.wav") for a in ARMS}
    T = min(z.shape[1] for z in Z.values())
    Z = {a: z[:, :T] for a, z in Z.items()}
    z0 = Z["orig"]

    fifth_fd = frame_delta(Z["fifth"] - z0)
    rows = {}
    for a in ("min2", "fifth", "codecnoise"):
        dz = Z[a] - z0
        fd = frame_delta(dz)
        rows[a] = {"frame_delta": round(fd, 4),
                   "frac_of_fifth_calib": round(fd / FIFTH_CALIB, 4),
                   "frac_of_fifth_inmix": round(fd / (fifth_fd + 1e-9), 4),
                   "melFrac": round(mel_frac(dz), 4)}
    snr_mag = rows["min2"]["frame_delta"] / (rows["codecnoise"]["frame_delta"] + 1e-9)
    snr_mel = rows["min2"]["melFrac"] / (rows["codecnoise"]["melFrac"] + 1e-9)
    out = {"purpose": "in-mix semitone floor test (Kim 2026-08-06)",
           "source": "No Doubt - Don't Speak, 5 leaf stems (no bus), vocal=melody; window 86.0s +23.8s",
           "refs": {"fifth_calib_isolated": FIFTH_CALIB, "random_melFrac": RANDOM_MEL,
                    "codec_melFrac_mp3_256": CODEC_MEL_256, "T_frames": int(T)},
           "arms": rows,
           "verdict": {"min2_vs_codecnoise_magnitude_snr": round(snr_mag, 2),
                       "min2_vs_codecnoise_melFrac_snr": round(snr_mel, 2),
                       "inmix_saturation_min2_over_fifth": rows["min2"]["frac_of_fifth_inmix"]}}
    (D / "results.json").write_text(json.dumps(out, indent=2))

    print(f"\nfifth(isolated calib)={FIFTH_CALIB:.2f}  in-mix fifth frame_delta={fifth_fd:.3f}  "
          f"codec melFrac(mp3@256)={CODEC_MEL_256:.3f}  random melFrac={RANDOM_MEL:.3f}\n")
    print(f"{'arm':<12}{'frameΔ':>9}{'/fifthCal':>11}{'/fifthMix':>11}{'melFrac':>9}")
    for a in ("min2", "fifth", "codecnoise"):
        r = rows[a]
        print(f"{a:<12}{r['frame_delta']:>9.3f}{r['frac_of_fifth_calib']:>11.3f}"
              f"{r['frac_of_fifth_inmix']:>11.3f}{r['melFrac']:>9.4f}")
    print(f"\nVERDICT: semitone-in-mix vs codec noise  -> magnitude SNR {snr_mag:.2f}x, "
          f"melody-subspace SNR {snr_mel:.2f}x")
    print(f"         in-mix saturation (min2/fifth magnitude) = {rows['min2']['frac_of_fifth_inmix']:.2f}"
          f"  (atlas isolated-note was 0.94)")
    print(f"[done] -> {D}/results.json")


if __name__ == "__main__":
    main()
