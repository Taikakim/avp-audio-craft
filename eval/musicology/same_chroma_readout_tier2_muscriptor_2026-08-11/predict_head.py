#!/usr/bin/env python3
"""predict_head.py -- Stage A of the Tier-2 same_chroma readout test (REAL goa music).

Forwards the trained `same_chroma` LatCH head (the exact checkpoint scored in Tier-1,
`same_chroma_readout_2026-08-11/`) on clean z0 latents (t=0, rectified-flow "clean"
convention) for every real goa track in `/home/kim/Projects/latents_sa3` that has a
matching MuScriptor transcription record (`{id}.stats.json` in muscriptor_full -- used
only to locate the source audio for Stage B's audio-GT; transcription QUALITY doesn't
gate this stage). Predicted 384-d chroma reshaped band-major to (3,128,T) -- same
convention as Tier-1's predict_head.py.

Venv: SAO/.venv (torch). CPU-only, SEQUENTIAL SINGLE PROCESS with batched forward
(all latents_sa3 crops are fixed T=4096, so batching is free -- amortizes attention
cost, ~0.78s/file at batch=16/threads=8 vs ~1.2s/file unbatched). Deliberately NOT
multiprocess: an earlier attempt with a ProcessPoolExecutor pool thrashed badly (each
worker's `import stable_audio_3` triggers rocm_env.apply_profile, and N processes
racing that/HIP-adjacent init serialized to near-total-stall -- killed after 9 CPU-min
of near-zero progress on 12 files). One process, one head load, loop.

Run:
  export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
  /home/kim/Projects/SAO/.venv/bin/python predict_head.py [--batch-size 16] [--limit N]
"""
import argparse
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
LATENT_DIR = Path("/home/kim/Projects/latents_sa3")
MUSCRIPTOR_DIR = Path("/run/media/kim/Kosmos/muscriptor_full")
OUT_DIR = Path("/tmp/claude-1000/-home-kim-Projects-SAO/49cd5391-27e7-4545-8295-a1053db2a077/scratchpad/tier2_predicted")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    torch.set_num_threads(args.threads)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    lat_ids = {p.stem for p in LATENT_DIR.glob("*.npy")}
    mus_ids = {p.stem[: -len(".stats")] for p in MUSCRIPTOR_DIR.glob("*.stats.json")}
    ids = sorted(lat_ids & mus_ids)
    todo = [fid for fid in ids if not (OUT_DIR / f"{fid}.npy").exists()]
    if args.limit:
        todo = todo[: args.limit]
    print(f"[predict] {len(lat_ids)} latents, {len(mus_ids)} muscriptor stats, "
          f"{len(ids)} in intersection, {len(todo)} to do (skipping done)", flush=True)

    head = load_latch_from_checkpoint(CKPT, device="cpu")
    meta = head.metadata
    print(f"[head] in={head.in_channels} out={head.out_channels} dim={head.dim} "
          f"depth={head.depth} t_injection={head.t_injection} feature_name={meta.get('feature_name')}",
          flush=True)
    assert meta.get("feature_name") == "same_chroma"
    assert head.out_channels == 384 and head.in_channels == 256

    t0_all = time.time()
    n_ok = n_bad = 0
    bs = args.batch_size
    for bstart in range(0, len(todo), bs):
        batch_ids = todo[bstart: bstart + bs]
        lats, ok_ids = [], []
        for fid in batch_ids:
            try:
                lat = np.load(LATENT_DIR / f"{fid}.npy").astype(np.float32)
                if lat.ndim == 3:
                    lat = lat[0]
                if lat.shape != (256, 4096):
                    print(f"[predict] {fid}: bad shape {lat.shape}, skip", flush=True)
                    n_bad += 1
                    continue
                lats.append(lat)
                ok_ids.append(fid)
            except Exception as e:
                print(f"[predict] {fid}: load error {e}", flush=True)
                n_bad += 1
        if not lats:
            continue
        x = torch.from_numpy(np.stack(lats, 0))
        t = torch.zeros(x.shape[0])
        with torch.no_grad():
            out = head(x, t)  # (B,384,4096)
        pred = out.numpy().astype(np.float32).reshape(len(ok_ids), 3, 128, -1)
        for fid, p in zip(ok_ids, pred):
            np.save(OUT_DIR / f"{fid}.npy", p)
        n_ok += len(ok_ids)
        if (bstart // bs + 1) % 10 == 0 or bstart + bs >= len(todo):
            dt = time.time() - t0_all
            done = bstart + len(batch_ids)
            print(f"[predict] {done}/{len(todo)} ({dt:.1f}s, {dt/max(1,done):.3f}s/file, "
                  f"ok={n_ok} bad={n_bad})", flush=True)

    print(f"[predict] DONE ok={n_ok} bad={n_bad} wall={time.time()-t0_all:.1f}s -> {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
