#!/usr/bin/env python3
"""
Generate Sequence Length Matrix Evaluation for p07_islands_v2_direct_bridge.
- Lengths: 256 to 4096 frames in increments of 256 (16 lengths).
- CFG: 6.0 and 12.0.
- Seeds: 1391676905 and 1391676906.
- Model Stack: Full-FT backbone (fullft_avp_t256_ep80) at w=1.0 + AVP subloss adapter (subloss_k24) at w=0.75.
- Steps: 24.
- Output: WAV + 192k AAC + manifest.jsonl with auto-resume.
"""

import os
import sys
import time
import json
import argparse
import subprocess
import torch
import soundfile as sf
import numpy as np

# ROCm environment defaults
for k, v in {
    "FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE",
    "PYTORCH_TUNABLEOP_ENABLED": "0",
    "MIOPEN_FIND_MODE": "2"
}.items():
    os.environ.setdefault(k, v)

sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
sys.path.insert(0, "/home/kim/Projects/SAO/eval")

from forge.fullft import load_fullft
from stable_audio_3 import StableAudioModel

SR = 44100
DOWNSAMPLING_RATIO = 4096

DEFAULT_CKPT = "/run/media/kim/Mantu/sa3_lora_runs/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt"
DEFAULT_ADAPTER = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_avpaug_t512_bf16_s1/epoch=63-step=2368.ckpt"

OUT_DIR = "/run/media/kim/Mantu/sa3_lora_runs/length_matrix_p07"
WAV_DIR = os.path.join(OUT_DIR, "wav")
AAC_DIR = os.path.expanduser("~/evals_aac/length_matrix_p07")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.jsonl")

PROMPT = "early 2000s goa trance, melodic dark mood, 145 bpm, driving acid lead, energetic mood, F minor, steady 145 bpm"
LENGTHS = [256 * i for i in range(1, 17)] # 256 to 4096 in steps of 256
CFGS = [6.0, 12.0]
SEEDS = [1391676905, 1391676906]
STEPS = 24

def encode_aac(src, dst):
    cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", src, "-c:a", "aac", "-b:a", "192k", dst]
    subprocess.run(cmd, check=True)

def load_existing_manifest(path):
    existing = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        existing.add(obj["id"])
                    except Exception:
                        pass
    return existing

def main():
    parser = argparse.ArgumentParser(description="Generate Length Matrix for p07 Goa Trance")
    parser.add_argument("--ckpt", type=str, default=DEFAULT_CKPT)
    parser.add_argument("--adapter", type=str, default=DEFAULT_ADAPTER)
    parser.add_argument("--fullft_w", type=float, default=1.0)
    parser.add_argument("--adapter_w", type=float, default=0.75)
    parser.add_argument("--steps", type=int, default=STEPS)
    parser.add_argument("--dry_run", action="store_true")
    args = parser.parse_args()

    os.makedirs(WAV_DIR, exist_ok=True)
    os.makedirs(AAC_DIR, exist_ok=True)

    completed = load_existing_manifest(MANIFEST_PATH)
    print(f"=== Length Matrix Generator ===")
    print(f"Prompt: {PROMPT}")
    print(f"Lengths: {LENGTHS}")
    print(f"CFGs: {CFGS}")
    print(f"Seeds: {SEEDS}")
    print(f"Total combinations: {len(LENGTHS) * len(CFGS) * len(SEEDS)}")
    print(f"Already completed: {len(completed)}")

    if args.dry_run:
        print("[dry-run] Exiting without model load.")
        return

    print("Loading base model...")
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    print(f"Loading Full-FT backbone: {args.ckpt}...")
    load_fullft(model, args.ckpt, weights="online")

    if args.adapter and args.adapter_w > 0:
        print(f"Loading LoRA adapter: {args.adapter} at strength {args.adapter_w}...")
        model.load_lora([args.adapter])
        model.set_lora_strength(args.adapter_w)

    total_tasks = len(LENGTHS) * len(CFGS) * len(SEEDS)
    current_idx = 0

    with open(MANIFEST_PATH, "a", encoding="utf-8") as manifest_file:
        for f in LENGTHS:
            dur_sec = (f * DOWNSAMPLING_RATIO) / SR
            bars = (dur_sec / (60.0 / 145.0)) / 4.0

            for cfg in CFGS:
                for seed in SEEDS:
                    current_idx += 1
                    clip_id = f"p07_len{f:04d}_cfg{int(cfg):02d}_s{seed}"
                    wav_file = os.path.join(WAV_DIR, f"{clip_id}.wav")
                    aac_file = os.path.join(AAC_DIR, f"{clip_id}.m4a")

                    if clip_id in completed and os.path.exists(wav_file) and os.path.exists(aac_file):
                        print(f"[{current_idx}/{total_tasks}] SKIP {clip_id} (already exists)")
                        continue

                    print(f"[{current_idx}/{total_tasks}] Generating {clip_id}: {f} frames ({dur_sec:.2f}s / {bars:.1f} bars), CFG {cfg}, Seed {seed}...", flush=True)
                    torch.cuda.reset_peak_memory_stats()
                    t0 = time.time()

                    out = model.generate(
                        prompt=PROMPT,
                        duration=dur_sec,
                        steps=args.steps,
                        cfg_scale=cfg,
                        seed=seed,
                        batch_size=1
                    )
                    gen_elapsed = time.time() - t0
                    peak_vram = torch.cuda.max_memory_allocated() / 1e9

                    # Save WAV
                    wav_data = out[0].float().cpu().numpy()
                    sf.write(wav_file, wav_data.T, SR, subtype="PCM_24")

                    # Encode AAC
                    encode_aac(wav_file, aac_file)

                    entry = {
                        "id": clip_id,
                        "pid": "p07",
                        "frames": f,
                        "dur": round(dur_sec, 2),
                        "bars": round(bars, 2),
                        "cfg": cfg,
                        "seed": seed,
                        "steps": args.steps,
                        "bpm": 145.0,
                        "key": "F minor",
                        "prompt": PROMPT,
                        "fullft_w": args.fullft_w,
                        "adapter_w": args.adapter_w,
                        "wav_path": wav_file,
                        "aac_path": f"length_matrix_p07/{clip_id}.m4a",
                        "gen_time_s": round(gen_elapsed, 2),
                        "vram_gb": round(peak_vram, 2)
                    }

                    manifest_file.write(json.dumps(entry) + "\n")
                    manifest_file.flush()
                    completed.add(clip_id)

                    print(f"  -> Generated in {gen_elapsed:.2f}s (peak VRAM: {peak_vram:.2f} GB), saved {clip_id}.m4a", flush=True)
                    torch.cuda.empty_cache()

    print("All tasks completed successfully!")
    os._exit(0)

if __name__ == "__main__":
    main()
