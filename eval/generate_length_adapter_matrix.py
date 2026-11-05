#!/usr/bin/env python3
"""
generate_length_adapter_matrix.py — Sequence Length x Adapter Weight x Prompt Matrix

Matrix:
- Sequence Lengths: 128, 256, 512, 1024, 2048, 4096 frames (11.9s to 380.5s / 6.3m)
- Adapter Weights: 0.75 (hot), 0.30 (mild), 0.00 (backbone only)
- Prompts:
  - acid_145: "early 2000s goa trance, melodic dark mood, 145 bpm, driving acid lead, energetic mood, F minor, steady 145 bpm"
  - melodic_151: "mid 90s goa trance, melodic mood, 151 bpm, Roland JD-800 sparkling crystal lead, Korg Prophecy eastern microtonal lead riff, acid squelch, soaring euphoric dual-lead harmony, frantic 16th-note arpeggios"
- CFG: 6.0
- Seed: 1391676905
Total: 36 clips.
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

OUT_DIR = "/run/media/kim/Mantu/sa3_lora_runs/length_adapter_matrix"
WAV_DIR = os.path.join(OUT_DIR, "wav")
AAC_DIR = os.path.expanduser("~/evals_aac/length_adapter_matrix")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.jsonl")

LENGTHS = [128, 256, 512, 1024, 2048, 4096]
ADAPTER_WEIGHTS = [0.75, 0.30, 0.00]
PROMPTS = {
    "acid145": {
        "text": "early 2000s goa trance, melodic dark mood, 145 bpm, driving acid lead, energetic mood, F minor, steady 145 bpm",
        "bpm": 145.0,
        "label": "Acid Driving (145 BPM, Fm)"
    },
    "melodic151": {
        "text": "mid 90s goa trance, melodic mood, 151 bpm, Roland JD-800 sparkling crystal lead, Korg Prophecy eastern microtonal lead riff, acid squelch, soaring euphoric dual-lead harmony, frantic 16th-note arpeggios",
        "bpm": 151.0,
        "label": "Melodic Dual-Lead (151 BPM)"
    }
}
CFG = 6.0
SEED = 1391676905
STEPS = 24

def convert_to_aac(wav_path, aac_path):
    cmd = [
        "ffmpeg", "-y", "-i", wav_path,
        "-c:a", "aac", "-b:a", "192k",
        aac_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def load_existing_manifest(path):
    done = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        done.add(data["clip_id"])
                    except Exception:
                        pass
    return done

def build_tasks():
    tasks = []
    # Baseline matrix: lengths 128 to 4096 at CFG 6.0
    for p_key in PROMPTS:
        for w in ADAPTER_WEIGHTS:
            for f in LENGTHS:
                w_str = f"w{int(round(w * 100)):03d}"
                tasks.append({
                    "prompt_key": p_key,
                    "weight": w,
                    "frames": f,
                    "cfg": 6.0,
                    "clip_id": f"matrix_{p_key}_{w_str}_len{f:04d}"
                })

    # High-CFG matrix for long lengths 2048 & 4096 at CFG 12.0 and 16.0
    for p_key in PROMPTS:
        for w in ADAPTER_WEIGHTS:
            for f in [2048, 4096]:
                for cfg in [12.0, 16.0]:
                    w_str = f"w{int(round(w * 100)):03d}"
                    tasks.append({
                        "prompt_key": p_key,
                        "weight": w,
                        "frames": f,
                        "cfg": cfg,
                        "clip_id": f"matrix_{p_key}_{w_str}_len{f:04d}_cfg{int(cfg):02d}"
                    })
    return tasks

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", type=str, default=DEFAULT_CKPT)
    parser.add_argument("--adapter", type=str, default=DEFAULT_ADAPTER)
    parser.add_argument("--steps", type=int, default=STEPS)
    parser.add_argument("--dry_run", action="store_true")
    args = parser.parse_args()

    os.makedirs(WAV_DIR, exist_ok=True)
    os.makedirs(AAC_DIR, exist_ok=True)

    completed = load_existing_manifest(MANIFEST_PATH)
    all_tasks = build_tasks()
    total_tasks = len(all_tasks)

    print(f"=== Length x Adapter Matrix Generator (with High CFG 12 & 16) ===")
    print(f"Total tasks: {total_tasks}")
    print(f"Already completed: {len(completed)}")

    if args.dry_run:
        print("[dry-run] Exiting.")
        return

    print("Loading base model...")
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    print(f"Loading Full-FT backbone: {args.ckpt}...")
    load_fullft(model, args.ckpt, weights="online")

    print(f"Loading LoRA adapter: {args.adapter}...")
    model.load_lora([args.adapter])

    current_weight = None

    with open(MANIFEST_PATH, "a", encoding="utf-8") as manifest_file:
        for current_idx, t in enumerate(all_tasks, 1):
            p_key = t["prompt_key"]
            p_info = PROMPTS[p_key]
            prompt_text = p_info["text"]
            bpm = p_info["bpm"]
            w = t["weight"]
            f = t["frames"]
            cfg = t["cfg"]
            clip_id = t["clip_id"]

            wav_file = os.path.join(WAV_DIR, f"{clip_id}.wav")
            aac_file = os.path.join(AAC_DIR, f"{clip_id}.m4a")

            if clip_id in completed and os.path.exists(wav_file) and os.path.exists(aac_file):
                print(f"[{current_idx}/{total_tasks}] SKIP {clip_id} (already exists)")
                continue

            if current_weight != w:
                model.set_lora_strength(w)
                current_weight = w

            dur_sec = (f * DOWNSAMPLING_RATIO) / SR
            bars = (dur_sec / (60.0 / bpm)) / 4.0

            print(f"[{current_idx}/{total_tasks}] Generating {clip_id}: {p_key}, weight {w}, {f} frames ({dur_sec:.2f}s / {bars:.1f} bars), CFG {cfg}...", flush=True)
            torch.cuda.reset_peak_memory_stats()
            t0 = time.time()

            out = model.generate(
                prompt=prompt_text,
                duration=dur_sec,
                steps=args.steps,
                cfg_scale=cfg,
                seed=SEED,
                batch_size=1
            )
            gen_elapsed = time.time() - t0
            peak_vram = torch.cuda.max_memory_allocated() / 1e9

            audio = out[0].squeeze(0).cpu().numpy()
            if audio.ndim == 2:
                audio = audio.T
            sf.write(wav_file, audio, SR, subtype="PCM_16")

            convert_to_aac(wav_file, aac_file)

            meta = {
                "clip_id": clip_id,
                "prompt_key": p_key,
                "prompt_label": p_info["label"],
                "prompt": prompt_text,
                "adapter_weight": w,
                "frames": f,
                "dur": round(dur_sec, 2),
                "bars": round(bars, 1),
                "cfg": cfg,
                "seed": SEED,
                "gen_time_s": round(gen_elapsed, 2),
                "peak_vram_gb": round(peak_vram, 2),
                "wav_path": wav_file,
                "aac_path": aac_file,
                "m4a_rel": f"length_adapter_matrix/{clip_id}.m4a"
            }
            manifest_file.write(json.dumps(meta) + "\n")
            manifest_file.flush()

            print(f"   -> Done in {gen_elapsed:.1f}s (peak VRAM: {peak_vram:.2f} GB)")

    print(f"\nAll {total_tasks} clips generated successfully!")
    os._exit(0)

if __name__ == "__main__":
    main()
