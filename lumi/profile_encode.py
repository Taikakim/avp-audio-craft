#!/usr/bin/env python
"""profile_encode.py — pin the aug8 encode bottleneck before committing another long job.
Loads SAME-L once, encodes N already-augmented FLACs from aug_flac_all, prints per-crop
seconds. Read the pattern:
  * first crop slow (~compile), rest fast (~1-2s)   -> it was fine; the 12h wall was phase A
                                                        or just the 43k count. Fix = more wall
                                                        / more GCDs / fewer crops (aug3).
  * EVERY crop slow (~tens of s), uniform           -> per-crop cost (recompile or heavy
                                                        T=4096 encode). Fix = MIOpen cache and/
                                                        or batching and/or T=512 encode.
Also times a batched forward (stack of 4 same-shape crops) to show the batching headroom.
Run (interactive, ~5 min):
  srun --account=project_465003186 --partition=standard-g --gpus=1 --time=00:10:00 \
    singularity exec --env FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE --env HF_HUB_OFFLINE=1 \
    --env HF_HOME=/project/project_465003186/models \
    --bind /project/project_465003186,/scratch/project_465003186 \
    /project/project_465003186/containers/sa3.sif \
    python /project/project_465003186/code/lumi/profile_encode.py
"""
import glob
import os
import tempfile
import time

# MIOpen kernel DB -> a WRITABLE /tmp dir, set BEFORE torch/stable_audio_3 import (the ROCm
# inference profile otherwise points it at a read-only /home path on LUMI -> miopenStatusUnknownError).
# Persistent within this run (NOT wiped) so same-shape crops reuse compiled kernels — which is the
# whole point of the probe: does per-crop cost drop after the first once the cache works?
_mio = os.path.join(tempfile.gettempdir(), f"miopen-prof-{os.getpid()}")
os.makedirs(_mio, exist_ok=True)
os.environ["MIOPEN_USER_DB_PATH"] = _mio
os.environ["MIOPEN_CUSTOM_CACHE_DIR"] = _mio
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
# The on-disk SQLite kernel cache CANNOT be opened on LUMI (proven bug, MASTER §5) -> disable it,
# exactly as the real aug8 encode task does. In-memory (per-process) find-db still caches same-shape
# kernels after the first call, so this measures the TRUE per-crop cost the real run paid.
os.environ["MIOPEN_DISABLE_CACHE"] = "1"
# TunableOp OFF — same as the real aug8 task (sbatch sets it). Left on, it benchmarks every GEMM
# variant on first use and (with its results CSV on a read-only /home path) re-tunes for MINUTES.
os.environ["PYTORCH_TUNABLEOP_ENABLED"] = "0"

FLACDIR = "/scratch/project_465003186/latents_goa_aug8/aug_flac_all"
N = 16

import numpy as np
import soundfile as sf
import torch
from stable_audio_3 import AutoencoderModel

flacs = sorted(glob.glob(os.path.join(FLACDIR, "*.flac")))[:N]
print(f"[profile] {len(flacs)} flacs from {FLACDIR}", flush=True)
if not flacs:
    raise SystemExit("no flacs found — is the aug8 scratch dir mounted?")

t0 = time.time()
ae = AutoencoderModel.from_pretrained("same-l", device="cuda")
print(f"[profile] model loaded in {time.time()-t0:.1f}s", flush=True)


def load(p):
    audio, sr = sf.read(p, dtype="float32", always_2d=True)
    x = torch.from_numpy(audio.T).unsqueeze(0).to("cuda")
    if x.shape[1] == 1:
        x = x.repeat(1, 2, 1)
    return x, sr


# ── single-crop timing (the aug8 path) ──
times = []
shape = None
for i, p in enumerate(flacs):
    x, sr = load(p)
    torch.cuda.synchronize()
    t = time.time()
    with torch.no_grad():
        z = ae.encode(x, sr)
    torch.cuda.synchronize()
    dt = time.time() - t
    times.append(dt)
    shape = tuple(z.shape)
    print(f"  [{i+1}/{len(flacs)}] {os.path.basename(p)}  {dt:.2f}s  latent={shape}", flush=True)

print(f"[profile] single: first={times[0]:.2f}s  median={sorted(times)[len(times)//2]:.2f}s  "
      f"rest_mean={np.mean(times[1:]):.2f}s  (latent T={shape[-1]})", flush=True)

# ── batched timing (all same shape -> stackable). Warms up first. ──
try:
    B = 4
    xs, sr = [], None
    for p in flacs[:B]:
        x, sr = load(p)
        xs.append(x)
    # pad/trim to the min T so they stack cleanly
    Tmin = min(x.shape[-1] for x in xs)
    xb = torch.cat([x[..., :Tmin] for x in xs], dim=0)
    with torch.no_grad():
        ae.encode(xb, sr)  # warm
    torch.cuda.synchronize()
    t = time.time()
    with torch.no_grad():
        ae.encode(xb, sr)
    torch.cuda.synchronize()
    dtb = time.time() - t
    print(f"[profile] batch x{B}: {dtb:.2f}s total = {dtb/B:.2f}s/crop  "
          f"(vs single {np.mean(times[1:]):.2f}s/crop -> {np.mean(times[1:])/(dtb/B):.1f}x if batched)",
          flush=True)
except Exception as e:
    print(f"[profile] batch test skipped: {type(e).__name__}: {e}", flush=True)
