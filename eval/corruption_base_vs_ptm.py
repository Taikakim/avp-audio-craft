#!/usr/bin/env python
"""corruption_base_vs_ptm.py — Kim 2026-09-17: for each of a set of clips already found
corrupted (audio_corruption_scan.py) in the random 3000-clip model_matrix sample, re-render
the SAME checkpoint/prompt/seed/strength under BOTH native configs -- medium-base at its
native cfg7/24steps, and post-trained medium (ptm) at its native cfg1/8steps -- to test
whether the corruption follows the SAMPLER (ptm's native ping-pong at 8 steps vs base's
euler at 24) or the WEIGHTS (would then show up in both configs alike). Motivated by the
broad-sample finding that ptm clips corrupt at ~5x the rate of base clips (35.7% vs 7.3% at
n_bad>=30) -- this is the direct causal test of that correlation.

Saves z0 next to every render (matches the project's standing "z0 next to every render"
convention) so the latent-side analysis can run without a second pass.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import json
import sys
from pathlib import Path

import numpy as np
import torch
from stable_audio_3 import StableAudioModel

sys.path.insert(0, "/home/kim/Projects/SAO/control")
from sa3_control.audio_io import save_audio  # noqa: E402

FPS = 44100 / 4096


def render_one(model, sr, ckpt_path, prompt, seed, strength, duration, steps, cfg, out_path, z0_path):
    frames = round(duration * FPS)
    sample_size = frames * 4096
    model.set_lora_strength(strength)

    sink = []
    out = model.generate(prompt=prompt, duration=duration, steps=steps, cfg_scale=cfg,
                          seed=seed, batch_size=1, sample_size=sample_size, latents_sink=sink)
    save_audio(str(out_path), out[0].float().cpu(), sr)
    if sink:
        np.save(str(z0_path), sink[0].float().cpu().numpy().astype(np.float16))


def main():
    jobs = json.loads(Path(sys.argv[1]).read_text())
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    # LoRA rank swap gotcha (stable-audio-3/CLAUDE.md): load_lora() on an already-loaded
    # model cannot switch to a DIFFERENT RANK (rank16 onto existing rank128 layers ->
    # size-mismatch RuntimeError). This job list spans many different ranks (dora16/64/128
    # etc.), so each checkpoint gets a FRESH from_pretrained() rather than reusing one
    # model object across the whole batch -- costs a few seconds per job, correctness over
    # marginal speed.
    #
    # ⚠ FIXED (2026-09-17, real crash): the original version kept BOTH base_model and
    # ptm_model resident simultaneously for the whole batch (each only reloaded when ITS
    # OWN checkpoint changed, never freed while the other type was in use) -- two 1.4B-param
    # models + LoRA + activations does not fit in 16GB, and it OOM'd ~17 jobs in with a
    # `torch.OutOfMemoryError` (14.21 GiB allocated, 60 MiB free). Fixed by running two full
    # PASSES instead of interleaving: all base renders first (only base_model ever resident),
    # then all ptm renders (base_model freed first, only ptm_model resident).
    print("=== PASS 1: base (medium-base, cfg7/24steps) ===", flush=True)
    base_model = None
    current_base_ckpt = None
    for j in jobs:
        tag = Path(j["orig_file"]).stem
        base_out = out_dir / f"{tag}__BASE_cfg7.wav"
        if base_out.exists():
            continue
        if current_base_ckpt != j["ckpt_path"]:
            print(f"[load-fresh base] {j['ckpt_path']}", flush=True)
            if base_model is not None:
                del base_model
                torch.cuda.empty_cache()
            base_model = StableAudioModel.from_pretrained("medium-base", device="cuda")
            base_model.load_lora([j["ckpt_path"]])
            current_base_ckpt = j["ckpt_path"]
        print(f"[gen base] {tag}", flush=True)
        render_one(base_model, base_model.model.sample_rate, j["ckpt_path"], j["prompt_text"],
                   j["seed"], j["strength"], j["duration"], 24, 7.0, base_out,
                   out_dir / f"{tag}__BASE_cfg7.z0.npy")
    del base_model
    torch.cuda.empty_cache()

    print("=== PASS 2: ptm (medium, cfg1/8steps) ===", flush=True)
    ptm_model = None
    current_ptm_ckpt = None
    for j in jobs:
        tag = Path(j["orig_file"]).stem
        ptm_out = out_dir / f"{tag}__PTM_cfg1.wav"
        if ptm_out.exists():
            continue
        if current_ptm_ckpt != j["ckpt_path"]:
            print(f"[load-fresh ptm] {j['ckpt_path']}", flush=True)
            if ptm_model is not None:
                del ptm_model
                torch.cuda.empty_cache()
            ptm_model = StableAudioModel.from_pretrained("medium", device="cuda")
            ptm_model.load_lora([j["ckpt_path"]])
            current_ptm_ckpt = j["ckpt_path"]
        print(f"[gen ptm] {tag}", flush=True)
        render_one(ptm_model, ptm_model.model.sample_rate, j["ckpt_path"], j["prompt_text"],
                   j["seed"], j["strength"], j["duration"], 8, 1.0, ptm_out,
                   out_dir / f"{tag}__PTM_cfg1.z0.npy")

    print("[all done]", flush=True)


if __name__ == "__main__":
    main()
