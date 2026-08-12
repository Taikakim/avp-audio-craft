#!/usr/bin/env python
"""direct_encode.py — encode one audio file -> SAME-L latent, bypassing LocalDataset
(SAO/.venv torchaudio can't load FLAC: needs torchcodec). soundfile read + functional resample."""
import argparse, os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
import numpy as np, torch, soundfile as sf
import torchaudio.functional as AF
from stable_audio_3 import AutoencoderModel

ap = argparse.ArgumentParser()
ap.add_argument("--flac", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--model", default="same-l"); ap.add_argument("--seconds", type=float, default=380.0)
ap.add_argument("--fp16", action="store_true")
a = ap.parse_args()

ae = AutoencoderModel.from_pretrained(a.model, device="cuda")
sr_t = ae.sample_rate
print("model sr", sr_t, flush=True)
x, sr = sf.read(a.flac, dtype="float32")            # (N,) or (N,C)
if x.ndim == 1:
    x = x[:, None]
wav = torch.tensor(x.T)                              # (C, N)
if wav.shape[0] == 1:
    wav = wav.repeat(2, 1)                           # SAME expects stereo
wav = AF.resample(wav, sr, sr_t)                     # sinc SR conversion (not pitch/time; bungee rule N/A)
n = int(a.seconds * sr_t)
wav = wav[:, :n]
audio = wav[None].to("cuda")                         # (1, C, N)
if a.fp16:
    ae.autoencoder = ae.autoencoder.half(); audio = audio.half()
print("audio", tuple(audio.shape), "-> encoding %.0fs" % (wav.shape[1] / sr_t), flush=True)
with torch.no_grad():
    z = ae.encode(audio, sr_t)
z = z.float().cpu().numpy()
np.save(a.out, z)
print("SAVED", a.out, "shape", z.shape, "-> %.0f frames = %.0f s"
      % (z.shape[-1], z.shape[-1] * 4096 / 44100), flush=True)
