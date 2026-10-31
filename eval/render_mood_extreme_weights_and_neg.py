#!/usr/bin/env python3
"""render_mood_extreme_weights_and_neg.py -- Extreme weights (2x-4x) and negative guidance for LatCH mood steering.

Addresses Kim's feedback:
1. Melodic and Aliens 2x-4x weight ladder: g in [4096, 6144, 8192, 12288]
2. Negative Space (anti-reverb / upfront punch): g in [-1024, -2048, -4096] on Space target
3. Negative Dark (anti-drone / clarity / bright Goa): g in [-1024, -2048, -4096] on Dark target
4. Evaluated on Medium Base and Goa LoRA r128 ep63.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import sys, time, json, subprocess
from pathlib import Path
import numpy as np
import torch
import torch.nn.utils.parametrize as P

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stable-audio-3"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "control"))

from stable_audio_3 import StableAudioModel
from sa3_control.audio_io import save_audio

HEAD_CKPT = "/run/media/kim/Mantu/latch_sweep/mood_56d_best_40ep_20261031/C3_mood_lr8e-4_b64_cos40/latch_sa3_effnet_moodtheme_ep40.pt"

OUT_WAV_DIR = Path("/run/media/kim/Mantu/sa3_control_runs/mood_finegrained_20261031")
OUT_AAC_DIR = Path("/home/kim/evals_aac/mood_finegrained")
OUT_WAV_DIR.mkdir(parents=True, exist_ok=True)
OUT_AAC_DIR.mkdir(parents=True, exist_ok=True)

ALIENS_TIMESERIES = Path("/run/media/kim/Kosmos/timeseries/Total Eclipse - Aliens.TIMESERIES.npz")
ALIENS_START = 6073122
LATENT_FRAMES = 280
DURATION = 20.0
STEPS = 24
SAMPLE_RATE = 44100
PROMPT = "2020s goa trance, melodic mood, 148 bpm"
SEED = 1102008041
CFG = 7.0

CKPT_GOA = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/dorlor_ab/dorlor_goa_lora_fusion_r128a45_t256_bf16_bs128_s1/epoch=63-step=2688.weights.ckpt"

MODELS = [
    {
        "id": "base",
        "name": "Medium Base",
        "type": "base",
        "loras": []
    },
    {
        "id": "goa",
        "name": "Goa LoRA r128 ep63",
        "type": "lora",
        "loras": [(CKPT_GOA, 1.0)]
    }
]

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

def merge_adapters(wrapper) -> int:
    n = 0
    for mod in list(wrapper.model.modules()) + list(wrapper.conditioner.modules()):
        if P.is_parametrized(mod):
            for name in list(mod.parametrizations.keys()):
                with torch.no_grad():
                    P.remove_parametrizations(mod, name, leave_parametrized=True)
                n += 1
    return n

def build_mood_targets():
    target_space = np.zeros((56, LATENT_FRAMES), dtype=np.float32)
    target_space[49, :] = 1.0  # space
    target_space[48, :] = 0.3  # soundscape
    target_space[16, :] = 0.3  # dream

    target_dark = np.zeros((56, LATENT_FRAMES), dtype=np.float32)
    target_dark[11, :] = 1.0  # dark
    target_dark[27, :] = 0.4  # heavy
    target_dark[12, :] = 0.3  # deep

    target_melodic = np.zeros((56, LATENT_FRAMES), dtype=np.float32)
    target_melodic[34, :] = 1.0  # melodic
    target_melodic[55, :] = 0.4  # uplifting
    target_melodic[26, :] = 0.3  # happy

    data = np.load(ALIENS_TIMESERIES, allow_pickle=True)
    mood_ts = data['effnet_moodtheme_ts']
    meta = json.loads(str(data['__meta__']))
    rate = meta['field_rates']['effnet_moodtheme_ts']
    start_s = ALIENS_START / 44100.0
    dur_s = 26.006
    f0 = int(round(start_s * rate))
    f1 = int(round((start_s + dur_s) * rate))
    slice_mood = mood_ts[f0:f1]
    raw_t = torch.from_numpy(slice_mood).float().transpose(0, 1).unsqueeze(0)
    target_aliens = torch.nn.functional.interpolate(raw_t, size=LATENT_FRAMES, mode='linear', align_corners=False).squeeze(0).numpy()

    return {
        "Space": target_space,
        "Dark": target_dark,
        "Melodic": target_melodic,
        "Aliens": target_aliens
    }

def main():
    targets = build_mood_targets()

    # 1. High weights for Melodic & Aliens (2x to 4x)
    high_weights = [4096.0, 6144.0, 8192.0, 12288.0]
    # 2. Negative guidance for Space & Dark
    neg_weights = [-1024.0, -2048.0, -4096.0]

    conditions = []
    # High weight ladder for Melodic and Aliens
    for w in high_weights:
        conditions.append((f"Melodic_g{int(w)}", targets["Melodic"], w))
    for w in high_weights:
        conditions.append((f"Aliens_g{int(w)}", targets["Aliens"], w))

    # Negative Space ladder
    for w in neg_weights:
        conditions.append((f"NegSpace_g{abs(int(w))}", targets["Space"], w))

    # Negative Dark ladder
    for w in neg_weights:
        conditions.append((f"NegDark_g{abs(int(w))}", targets["Dark"], w))

    print(f"Total conditions per model: {len(conditions)}")

    # Acquire GPU lock
    ret = subprocess.run([str(ROOT / "Misc/gpu_guard.sh"), "acquire", "ANTIGRAVITY", str(os.getpid())])
    if ret.returncode != 0:
        print("Error: Could not acquire GPU guard.")
        sys.exit(1)

    try:
        for m_cfg in MODELS:
            m_id = m_cfg["id"]
            m_name = m_cfg["name"]

            print(f"\n=======================================================")
            print(f"[{m_id}] {m_name}")
            print(f"=======================================================")

            needed = []
            for cond_name, tgt, weight in conditions:
                stem = f"fine_{m_id}__{cond_name}__s{SEED}"
                wav_path = OUT_WAV_DIR / f"{stem}.wav"
                aac_path = OUT_AAC_DIR / f"{stem}.m4a"
                if not (wav_path.exists() and aac_path.exists()):
                    needed.append((cond_name, tgt, weight, wav_path, aac_path))

            if not needed:
                print(f"All renders for {m_id} already exist! Skipping.")
                continue

            print(f"Loading model onto cuda:0 for {len(needed)} renders...")
            model = StableAudioModel.from_pretrained("medium-base", device="cuda:0")

            if m_cfg["loras"]:
                paths = [p for p, _ in m_cfg["loras"]]
                print(f"  Applying LoRA: {paths}")
                model.load_lora(paths)
                for idx, (_, strength) in enumerate(m_cfg["loras"]):
                    model.set_lora_strength(float(strength), lora_index=idx)
                n_merged = merge_adapters(model.model)
                print(f"  Merged {n_merged} parametrized modules.")

            decode_dtype = next(model.same.parameters()).dtype

            for idx, (cond_name, tgt, weight, wav_path, aac_path) in enumerate(needed, 1):
                t0 = time.time()
                print(f"[{idx}/{len(needed)}] Rendering {m_id} {cond_name} (weight={weight}) ...", flush=True)

                latch_configs = [{
                    "model_path": HEAD_CKPT,
                    "target_raw": tgt,
                    "weight": float(weight),
                    "loss_type": "cosine",
                    "start_pct": 0.0,
                    "end_pct": 1.0,
                }]
                latch_hparams = {"n_iter": 4, "gamma": 0.3}

                z0 = model.generate(
                    prompt=PROMPT,
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
                    print(f"WARNING: Non-finite latents in {wav_path.name}! Skipping.", flush=True)
                    continue

                with torch.no_grad():
                    audio = model.same.decode(z0.to(decode_dtype))
                audio = audio.to(torch.float32)[:, :, :int(DURATION * SAMPLE_RATE)]
                save_audio(str(wav_path), audio[0].cpu(), SAMPLE_RATE, normalize=True)
                transcode_to_aac(wav_path, aac_path)
                print(f"  -> Done in {time.time() - t0:.1f}s: {aac_path.name}", flush=True)

            del model
            torch.cuda.empty_cache()

    finally:
        subprocess.run([str(ROOT / "Misc/gpu_guard.sh"), "release", "ANTIGRAVITY"])
        print("GPU guard released.")

    print("\nAll extreme weight and negative renders complete!")

if __name__ == "__main__":
    main()
