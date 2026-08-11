#!/usr/bin/env python3
"""predict_head.py -- Stage A of the same_chroma readout/ceiling test.

Forwards the trained `same_chroma` LatCH head on clean z0 latents (t=0, the
rectified-flow "clean" convention) for every pair in the two synthetic
MIDI-latent corpora, and writes the predicted 384-d chroma (reshaped
band-major to (3,128,T), matching compute_same_chroma's output layout --
see stable-audio-3/scripts/latch/extract_same_chroma_targets.py and
eval/explorer_render_server.py's `compute_same_chroma(...).reshape(384,-1)`)
to a scratch cache dir as float32 .npy.

Venv: SAO/.venv (torch). CPU-only by design -- the head is ~5-7M params and
this is a readout test, not steering; no need to contend for the GPU.

Run:
  /home/kim/Projects/SAO/.venv/bin/python predict_head.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")

import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
from stable_audio_3.models.latch import load_latch_from_checkpoint  # noqa: E402

CKPT = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_same_chroma_best.pt"

PAIR_SETS = {
    "gm_timbre_pitch": Path("/home/kim/Projects/SAO/eval/musicology/gm_timbre_pitch/latents"),
    "test_midis_v2": Path("/home/kim/Projects/SAO/eval/musicology/test_midis_v2/latents"),
}

OUT_DIR = Path("/tmp/claude-1000/-home-kim-Projects-SAO/49cd5391-27e7-4545-8295-a1053db2a077/scratchpad/same_chroma_readout/predicted")


def main():
    torch.set_num_threads(4)
    head = load_latch_from_checkpoint(CKPT, device="cpu")
    meta = head.metadata
    print(f"[head] in={head.in_channels} out={head.out_channels} dim={head.dim} "
          f"depth={head.depth} t_injection={head.t_injection} feature_name={meta.get('feature_name')} "
          f"loss_type={meta.get('loss_type')} standardized={meta.get('standardized')} "
          f"noise_schedule={meta.get('noise_schedule')}", flush=True)
    assert meta.get("feature_name") == "same_chroma"
    assert head.out_channels == 384 and head.in_channels == 256

    t0_all = time.time()
    total = 0
    for set_name, lat_dir in PAIR_SETS.items():
        out_dir = OUT_DIR / set_name
        out_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(lat_dir.glob("*.z0.npy"))
        print(f"[{set_name}] {len(files)} latent files", flush=True)
        t0 = time.time()
        for i, p in enumerate(files):
            stem = p.stem[: -len(".z0")] if p.stem.endswith(".z0") else p.stem
            dst = out_dir / f"{stem}.npy"
            if dst.exists():
                continue
            lat = np.load(p).astype(np.float32)
            if lat.ndim == 3:
                lat = lat[0]
            assert lat.shape[0] == 256, f"unexpected latent shape {lat.shape} for {p}"
            x = torch.from_numpy(lat).unsqueeze(0)  # (1,256,T)
            t = torch.zeros(1)
            with torch.no_grad():
                out = head(x, t)  # (1,384,T)
            pred = out.squeeze(0).numpy().astype(np.float32).reshape(3, 128, -1)
            np.save(dst, pred)
            total += 1
            if (i + 1) % 100 == 0:
                dt = time.time() - t0
                print(f"[{set_name}] {i+1}/{len(files)} ({dt:.1f}s, {dt/(i+1)*1000:.0f} ms/file)", flush=True)
        print(f"[{set_name}] done in {time.time()-t0:.1f}s", flush=True)

    print(f"[predict_head] TOTAL new: {total}, wall {time.time()-t0_all:.1f}s -> {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
