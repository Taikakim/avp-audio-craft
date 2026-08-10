#!/usr/bin/env python
"""same_encode_cost_bench.py -- local SAME-encode cost benchmark (GHOST-NOTE, 2026-08-10,
docs/cost-log.md's source tool): SAME encode price at T512 vs T4096 (single + batched) +
live-encode vs pre-encoded VRAM/time deltas. Adapted from lumi/profile_encode.py's proven
MIOpen/TunableOp env pattern, for the LOCAL fast venv (SAO/.venv, ROCm 7.14) -- LUMI's per-
GCD hardware differs, re-run there directly before trusting absolute numbers on that side.

Run: /home/kim/Projects/SAO/.venv/bin/python lumi/same_encode_cost_bench.py
     [--audio-src <flac/wav, needs >=380s>] [--npy-src <a latents_sa3-style T4096 .npy>]
Results feed docs/cost-log.md by hand (append a dated entry, this script doesn't write it).
"""
import argparse
import os
import tempfile
import time

os.environ["FLASH_ATTENTION_TRITON_AMD_ENABLE"] = "FALSE"  # before torch import
_mio = os.path.join(tempfile.gettempdir(), f"miopen-bench-{os.getpid()}")
os.makedirs(_mio, exist_ok=True)
os.environ["MIOPEN_USER_DB_PATH"] = _mio
os.environ["MIOPEN_CUSTOM_CACHE_DIR"] = _mio
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ["PYTORCH_TUNABLEOP_ENABLED"] = "0"

import numpy as np
import soundfile as sf
import torch
from stable_audio_3 import AutoencoderModel

ap = argparse.ArgumentParser()
ap.add_argument("--audio-src", default="/home/kim/Projects/latents_sa3/000000.json",
                 help="any real audio file >=380s; default resolves the T4096 corpus's own "
                      "crop-0 source track via its sidecar JSON's source_path")
ap.add_argument("--npy-src", default="/home/kim/Projects/latents_sa3/000000.npy")
args = ap.parse_args()

if args.audio_src.endswith(".json"):
    import json
    SRC = json.load(open(args.audio_src))["source_path"]
else:
    SRC = args.audio_src

FPS = 44100 / 4096  # 10.7666 Hz canonical SA3-medium latent frame rate
SR = 44100
DUR_T512 = 512 / FPS   # 47.55s
DUR_T4096 = 4096 / FPS  # 380.44s
NPY_T4096 = args.npy_src


def vram_mb():
    return torch.cuda.memory_allocated() / 1e6


def load_slice(path, seconds):
    audio, sr = sf.read(path, dtype="float32", always_2d=True, frames=int(seconds * SR))
    x = torch.from_numpy(audio.T).unsqueeze(0).to("cuda")
    if x.shape[1] == 1:
        x = x.repeat(1, 2, 1)
    return x, sr


print("=== baseline VRAM (before model load) ===", flush=True)
torch.cuda.reset_peak_memory_stats()
print(f"  allocated={vram_mb():.1f} MB", flush=True)

t0 = time.time()
ae = AutoencoderModel.from_pretrained("same-l", device="cuda")
torch.cuda.synchronize()
print(f"[bench] SAME-L loaded in {time.time()-t0:.1f}s, resident VRAM after load: {vram_mb():.1f} MB "
      f"(peak during load: {torch.cuda.max_memory_allocated()/1e6:.1f} MB)", flush=True)
RESIDENT_MODEL_MB = vram_mb()

for label, dur in [("T512", DUR_T512), ("T4096", DUR_T4096)]:
    print(f"\n=== {label} ({dur:.2f}s) single-crop encode ===", flush=True)
    times = []
    for i in range(4):
        x, sr = load_slice(SRC, dur)
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        t = time.time()
        with torch.no_grad():
            z = ae.encode(x, sr)
        torch.cuda.synchronize()
        dt = time.time() - t
        times.append(dt)
        peak = torch.cuda.max_memory_allocated() / 1e6
        print(f"  [{i+1}/4] {dt:.3f}s  latent={tuple(z.shape)}  peak_alloc_during_call={peak:.1f}MB", flush=True)
    print(f"[bench] {label} single: first={times[0]:.3f}s  warmed_mean={np.mean(times[1:]):.3f}s", flush=True)

    # batched (bs=4, matches the reg A/B's --batch_size 4) -- guarded: T4096 x bs4 may OOM a
    # 16GB card outright, which is itself a real finding for the live-encode VRAM question.
    B = 4
    try:
        xs = [load_slice(SRC, dur)[0] for _ in range(B)]
        Tmin = min(x.shape[-1] for x in xs)
        xb = torch.cat([x[..., :Tmin] for x in xs], dim=0)
        with torch.no_grad():
            ae.encode(xb, sr)  # warm
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        t = time.time()
        with torch.no_grad():
            ae.encode(xb, sr)
        torch.cuda.synchronize()
        dtb = time.time() - t
        peak_batch = torch.cuda.max_memory_allocated() / 1e6
        print(f"[bench] {label} batch x{B}: {dtb:.3f}s total = {dtb/B:.3f}s/crop  "
              f"peak_alloc_during_call={peak_batch:.1f}MB "
              f"(total resident incl. model ~{RESIDENT_MODEL_MB + peak_batch:.1f}MB)", flush=True)
    except torch.OutOfMemoryError as e:
        print(f"[bench] {label} batch x{B}: OOM on this 16GB card -- "
              f"'{str(e).splitlines()[0]}'", flush=True)
        torch.cuda.empty_cache()

print("\n=== pre-encoded .npy read cost (T4096, the format latents_sa3 uses) ===", flush=True)
for i in range(4):
    t = time.time()
    z = np.load(NPY_T4096)
    dt = time.time() - t
    print(f"  [{i+1}/4] {dt*1000:.2f}ms  shape={z.shape}", flush=True)

print("\n=== raw audio disk read+decode cost (T512-equivalent slice, no encode) ===", flush=True)
for i in range(4):
    t = time.time()
    audio, sr = sf.read(SRC, dtype="float32", always_2d=True, frames=int(DUR_T512 * SR))
    dt = time.time() - t
    print(f"  [{i+1}/4] {dt*1000:.2f}ms", flush=True)

print("\n[bench] DONE.", flush=True)
