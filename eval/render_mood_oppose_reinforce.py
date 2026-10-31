#!/usr/bin/env python3
"""render_mood_oppose_reinforce.py -- Symmetrical prompt mood reinforcement & opposition study.

Tests:
1. Prompt A (Melodic Goa): "2020s goa trance, melodic mood, 148 bpm"
   - Base unguided (g=0)
   - Reinforce: +Melodic (g=1024, 2048)
   - Oppose: +Dark (g=1024, 2048)
   - Oppose: -Melodic (g=-1024, -2048)
   - Orthogonal: +Space (g=1024)

2. Prompt B (Dark Psytrance): "2020s dark psytrance, dark mood, heavy bass, 148 bpm"
   - Base unguided (g=0)
   - Reinforce: +Dark (g=1024, 2048)
   - Oppose: +Melodic (g=1024, 2048)
   - Oppose: -Dark (g=-1024)

Outputs saved to /run/media/kim/Mantu/sa3_control_runs/mood_oppose and /home/kim/evals_aac/mood_oppose.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import sys, time, json, subprocess, shutil
from pathlib import Path
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stable-audio-3"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "control"))

from stable_audio_3 import StableAudioModel
from sa3_control.audio_io import save_audio

HEAD_CKPT = "/run/media/kim/Mantu/latch_sweep/mood_56d_best_40ep_20261031/C3_mood_lr8e-4_b64_cos40/latch_sa3_effnet_moodtheme_ep40.pt"

OUT_WAV_DIR = Path("/run/media/kim/Mantu/sa3_control_runs/mood_oppose")
OUT_AAC_DIR = Path("/home/kim/evals_aac/mood_oppose")
OUT_WAV_DIR.mkdir(parents=True, exist_ok=True)
OUT_AAC_DIR.mkdir(parents=True, exist_ok=True)

LATENT_FRAMES = 280
DURATION = 20.0
STEPS = 24
SAMPLE_RATE = 44100
SEED = 1102008041
CFG = 7.0

PROMPT_A = "2020s goa trance, melodic mood, 148 bpm"
PROMPT_B = "2020s dark psytrance, dark mood, heavy bass, 148 bpm"

EXISTING_AAC_DIR = Path("/home/kim/evals_aac/mood_finegrained")
EXISTING_WAV_DIR = Path("/run/media/kim/Mantu/sa3_control_runs/mood_finegrained_20261031")

def transcode_to_aac(wav_path: Path, aac_path: Path):
    if aac_path.exists() and aac_path.stat().st_size > 0:
        return
    cmd = [
        "ffmpeg", "-y", "-nostdin", "-loglevel", "error",
        "-i", str(wav_path),
        "-c:a", "aac", "-b:a", "256k",
        str(aac_path)
    ]
    subprocess.run(cmd, check=True)

def build_targets():
    target_melodic = np.zeros((56, LATENT_FRAMES), dtype=np.float32)
    target_melodic[34, :] = 1.0  # melodic
    target_melodic[55, :] = 0.4  # uplifting
    target_melodic[26, :] = 0.3  # happy

    target_dark = np.zeros((56, LATENT_FRAMES), dtype=np.float32)
    target_dark[11, :] = 1.0  # dark
    target_dark[27, :] = 0.4  # heavy
    target_dark[12, :] = 0.3  # deep

    target_space = np.zeros((56, LATENT_FRAMES), dtype=np.float32)
    target_space[49, :] = 1.0  # space
    target_space[48, :] = 0.3  # soundscape
    target_space[16, :] = 0.3  # dream

    return {
        "Melodic": target_melodic,
        "Dark": target_dark,
        "Space": target_space
    }

def get_conditions():
    targets = build_targets()
    conds = []

    # Prompt A conditions
    conds.append({
        "prompt_id": "prompt_melodic",
        "prompt_text": PROMPT_A,
        "cond_id": "base",
        "action": "Baseline (Unguided)",
        "tgt": None,
        "weight": 0.0,
        "reuse_stem": "fine_base__base__s1102008041"
    })
    conds.append({
        "prompt_id": "prompt_melodic",
        "prompt_text": PROMPT_A,
        "cond_id": "reinforce_melodic_g1024",
        "action": "Reinforce: +Melodic (g=1024)",
        "tgt": targets["Melodic"],
        "weight": 1024.0,
        "reuse_stem": "fine_base__Melodic_g1024__s1102008041"
    })
    conds.append({
        "prompt_id": "prompt_melodic",
        "prompt_text": PROMPT_A,
        "cond_id": "reinforce_melodic_g2048",
        "action": "Reinforce: +Melodic (g=2048)",
        "tgt": targets["Melodic"],
        "weight": 2048.0,
        "reuse_stem": "fine_base__Melodic_g2048__s1102008041"
    })
    conds.append({
        "prompt_id": "prompt_melodic",
        "prompt_text": PROMPT_A,
        "cond_id": "oppose_dark_g1024",
        "action": "Oppose: +Dark (g=1024)",
        "tgt": targets["Dark"],
        "weight": 1024.0,
        "reuse_stem": "fine_base__Dark_g1024__s1102008041"
    })
    conds.append({
        "prompt_id": "prompt_melodic",
        "prompt_text": PROMPT_A,
        "cond_id": "oppose_dark_g2048",
        "action": "Oppose: +Dark (g=2048)",
        "tgt": targets["Dark"],
        "weight": 2048.0,
        "reuse_stem": "fine_base__Dark_g2048__s1102008041"
    })
    conds.append({
        "prompt_id": "prompt_melodic",
        "prompt_text": PROMPT_A,
        "cond_id": "oppose_neg_melodic_g1024",
        "action": "Oppose: -Melodic (g=-1024)",
        "tgt": targets["Melodic"],
        "weight": -1024.0,
        "reuse_stem": None
    })
    conds.append({
        "prompt_id": "prompt_melodic",
        "prompt_text": PROMPT_A,
        "cond_id": "oppose_neg_melodic_g2048",
        "action": "Oppose: -Melodic (g=-2048)",
        "tgt": targets["Melodic"],
        "weight": -2048.0,
        "reuse_stem": None
    })
    conds.append({
        "prompt_id": "prompt_melodic",
        "prompt_text": PROMPT_A,
        "cond_id": "space_g1024",
        "action": "Orthogonal: +Space (g=1024)",
        "tgt": targets["Space"],
        "weight": 1024.0,
        "reuse_stem": "fine_base__Space_g1024__s1102008041"
    })

    # Prompt B conditions (Dark prompt)
    conds.append({
        "prompt_id": "prompt_dark",
        "prompt_text": PROMPT_B,
        "cond_id": "base",
        "action": "Baseline (Unguided)",
        "tgt": None,
        "weight": 0.0,
        "reuse_stem": None
    })
    conds.append({
        "prompt_id": "prompt_dark",
        "prompt_text": PROMPT_B,
        "cond_id": "reinforce_dark_g1024",
        "action": "Reinforce: +Dark (g=1024)",
        "tgt": targets["Dark"],
        "weight": 1024.0,
        "reuse_stem": None
    })
    conds.append({
        "prompt_id": "prompt_dark",
        "prompt_text": PROMPT_B,
        "cond_id": "reinforce_dark_g2048",
        "action": "Reinforce: +Dark (g=2048)",
        "tgt": targets["Dark"],
        "weight": 2048.0,
        "reuse_stem": None
    })
    conds.append({
        "prompt_id": "prompt_dark",
        "prompt_text": PROMPT_B,
        "cond_id": "oppose_melodic_g1024",
        "action": "Oppose: +Melodic (g=1024)",
        "tgt": targets["Melodic"],
        "weight": 1024.0,
        "reuse_stem": None
    })
    conds.append({
        "prompt_id": "prompt_dark",
        "prompt_text": PROMPT_B,
        "cond_id": "oppose_melodic_g2048",
        "action": "Oppose: +Melodic (g=2048)",
        "tgt": targets["Melodic"],
        "weight": 2048.0,
        "reuse_stem": None
    })
    conds.append({
        "prompt_id": "prompt_dark",
        "prompt_text": PROMPT_B,
        "cond_id": "oppose_neg_dark_g1024",
        "action": "Oppose: -Dark (g=-1024)",
        "tgt": targets["Dark"],
        "weight": -1024.0,
        "reuse_stem": None
    })

    return conds

def main():
    conds = get_conditions()
    needed = []

    for c in conds:
        stem = f"{c['prompt_id']}__{c['cond_id']}"
        wav_path = OUT_WAV_DIR / f"{stem}.wav"
        aac_path = OUT_AAC_DIR / f"{stem}.m4a"
        c["stem"] = stem
        c["wav_path"] = wav_path
        c["aac_path"] = aac_path

        # Check if already rendered or can be reused
        if aac_path.exists() and aac_path.stat().st_size > 0:
            continue

        if c["reuse_stem"]:
            exist_aac = EXISTING_AAC_DIR / f"{c['reuse_stem']}.m4a"
            exist_wav = EXISTING_WAV_DIR / f"{c['reuse_stem']}.wav"
            if exist_aac.exists() and exist_wav.exists():
                print(f"Reusing existing render {c['reuse_stem']} -> {stem}")
                shutil.copy(str(exist_wav), str(wav_path))
                shutil.copy(str(exist_aac), str(aac_path))
                continue

        needed.append(c)

    print(f"Total conditions in suite: {len(conds)}")
    print(f"Conditions needing render on GPU: {len(needed)}")

    if not needed:
        print("All clips ready!")
        return

    # Acquire GPU guard
    ret = subprocess.run([str(ROOT / "Misc/gpu_guard.sh"), "acquire", "ANTIGRAVITY", str(os.getpid())])
    if ret.returncode != 0:
        print("Error: Could not acquire GPU guard.")
        sys.exit(1)

    try:
        print("Loading StableAudioModel (medium-base)...")
        model = StableAudioModel.from_pretrained("medium-base", device="cuda:0")
        decode_dtype = next(model.same.parameters()).dtype

        for idx, c in enumerate(needed, 1):
            t0 = time.time()
            print(f"[{idx}/{len(needed)}] Rendering {c['stem']} ({c['action']})...", flush=True)

            if c["weight"] == 0.0 or c["tgt"] is None:
                latch_configs = None
                latch_hparams = None
            else:
                latch_configs = [{
                    "model_path": HEAD_CKPT,
                    "target_raw": c["tgt"],
                    "weight": float(c["weight"]),
                    "loss_type": "cosine",
                    "start_pct": 0.0,
                    "end_pct": 1.0,
                }]
                latch_hparams = {"n_iter": 4, "gamma": 0.3}

            z0 = model.generate(
                prompt=c["prompt_text"],
                duration=DURATION,
                steps=STEPS,
                cfg_scale=CFG,
                seed=SEED,
                batch_size=1,
                return_latents=True,
                latch_configs=latch_configs,
                latch_hparams=latch_hparams,
            )

            if not torch.isfinite(z0).all():
                print(f"WARNING: Non-finite latents in {c['stem']}!")
                continue

            with torch.no_grad():
                audio = model.same.decode(z0.to(decode_dtype))
            audio = audio.to(torch.float32)[:, :, :int(DURATION * SAMPLE_RATE)]
            save_audio(str(c["wav_path"]), audio[0].cpu(), SAMPLE_RATE, normalize=True)
            transcode_to_aac(c["wav_path"], c["aac_path"])
            print(f"  -> Finished in {time.time() - t0:.1f}s: {c['aac_path'].name}", flush=True)

    finally:
        subprocess.run([str(ROOT / "Misc/gpu_guard.sh"), "release", "ANTIGRAVITY"])
        print("GPU guard released.")

    # Save manifest
    manifest_data = [{
        "prompt_id": c["prompt_id"],
        "prompt_text": c["prompt_text"],
        "cond_id": c["cond_id"],
        "action": c["action"],
        "weight": c["weight"],
        "aac_file": c["aac_path"].name,
        "wav_file": c["wav_path"].name
    } for c in conds]
    with open(OUT_AAC_DIR / "manifest.json", "w") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"Manifest written to {OUT_AAC_DIR / 'manifest.json'}")

if __name__ == "__main__":
    main()
