#!/usr/bin/env python3
"""render_mood_finegrained_matrix.py -- fine-grained weight matrix and model combinations
on the canonical benchmark prompt rb_bracket_0 ("2020s goa trance, melodic mood, 148 bpm", s1102008041, cfg 7).

Evaluates 56-dim Mood LatCH (ep40) across:
- Fine-grained weight ladder: g in [0, 256, 512, 1024, 1536, 2048, 3072]
- 4 Mood targets: Space, Dark, Melodic, Aliens HQ
- 8 Model arms & combinations:
    1. Base: medium-base (unadapted)
    2. AdamW: adamw_avp_t512_bs4_lr5e5 ep5
    3. Fusion LoRA: dorlor_avpaug_lora_fusion_r128a45_t256_bf16_bs128_s2 ep159
    4. Goa LoRA: dorlor_goa_lora_fusion_r128a45_t256_bf16_bs128_s1 ep63
    5. Combo AdamW + Fusion: 50% AdamW + 50% Fusion LoRA (w=0.5, 0.5)
    6. Combo AdamW + Goa: 50% AdamW + 50% Goa LoRA (w=0.5, 0.5)
    7. Combo Fusion + Goa: 50% Fusion + 50% Goa LoRA (w=0.5, 0.5)
    8. Full-FT: fullft_ladder_A_control ep39
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import sys, time, json, subprocess, argparse
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
TOTAL_SAMPLES = LATENT_FRAMES * 4096
DURATION = 20.0
STEPS = 24
SAMPLE_RATE = 44100
PROMPT = "2020s goa trance, melodic mood, 148 bpm"
SEED = 1102008041
CFG = 7.0

# Model configurations
CKPT_ADAMW = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/adamw_bf16_sweep/adamw_avp_t512_bs4_lr5e5/epoch=9-step=5980.ckpt"
CKPT_FUSION = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/dorlor_ab/dorlor_avpaug_lora_fusion_r128a45_t256_bf16_bs128_s2/epoch=159-step=2880.weights.ckpt"
CKPT_GOA = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/dorlor_ab/dorlor_goa_lora_fusion_r128a45_t256_bf16_bs128_s1/epoch=63-step=2688.weights.ckpt"
CKPT_FULLFT = "/run/media/kim/Mantu/sa3_lora_runs/fusion_autoscale_vs_adamw_2026-09-01/fullft_autoscale_2026-09-04/A_control/epoch=39-step=3000.ckpt"

MODELS = [
    {
        "id": "base",
        "name": "Medium Base",
        "type": "base",
        "loras": []
    },
    {
        "id": "adamw",
        "name": "AdamW ep5",
        "type": "lora",
        "loras": [(CKPT_ADAMW, 1.0)]
    },
    {
        "id": "fusion",
        "name": "Fusion LoRA r128 ep159",
        "type": "lora",
        "loras": [(CKPT_FUSION, 1.0)]
    },
    {
        "id": "goa",
        "name": "Goa LoRA r128 ep63",
        "type": "lora",
        "loras": [(CKPT_GOA, 1.0)]
    },
    {
        "id": "combo_adamw_fusion",
        "name": "Combo: AdamW + Fusion (50/50)",
        "type": "lora",
        "loras": [(CKPT_ADAMW, 0.5), (CKPT_FUSION, 0.5)]
    },
    {
        "id": "combo_adamw_goa",
        "name": "Combo: AdamW + Goa (50/50)",
        "type": "lora",
        "loras": [(CKPT_ADAMW, 0.5), (CKPT_GOA, 0.5)]
    },
    {
        "id": "combo_fusion_goa",
        "name": "Combo: Fusion + Goa (50/50)",
        "type": "lora",
        "loras": [(CKPT_FUSION, 0.5), (CKPT_GOA, 0.5)]
    },
    {
        "id": "fullft",
        "name": "Full Fine-Tune DiT ep39",
        "type": "fullft",
        "ckpt_path": CKPT_FULLFT,
        "loras": []
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--models", default="all", help="Comma-separated model IDs or 'all'")
    args = ap.parse_args()

    active_models = MODELS
    if args.models != "all":
        selected_ids = [s.strip() for s in args.models.split(",")]
        active_models = [m for m in MODELS if m["id"] in selected_ids]

    targets = build_mood_targets()
    weights = [256.0, 512.0, 1024.0, 1536.0, 2048.0, 3072.0]

    conditions = []
    # 1. Base unguided
    conditions.append(("base", None, 0.0))
    # 2. Fine-grained ladder for each target
    for tgt_name, tgt_arr in targets.items():
        for w in weights:
            conditions.append((f"{tgt_name}_g{int(w)}", tgt_arr, w))

    print(f"Total model configurations: {len(active_models)}")
    print(f"Total conditions per model: {len(conditions)} (1 base + 4 targets x 6 weights)")
    print(f"Grand total renders: {len(active_models) * len(conditions)}")

    task_idx = 0
    total_renders = len(active_models) * len(conditions)

    for m_cfg in active_models:
        m_id = m_cfg["id"]
        m_name = m_cfg["name"]
        m_type = m_cfg["type"]

        print(f"\n=======================================================")
        print(f"[{m_id}] {m_name}")
        print(f"=======================================================")

        # Check what needs rendering for this model
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

        print(f"Loading model onto {args.device} for {len(needed)} renders...")
        model = StableAudioModel.from_pretrained("medium-base", device=args.device)

        if m_type == "fullft" and m_cfg.get("ckpt_path"):
            ck = torch.load(m_cfg["ckpt_path"], map_location="cpu", weights_only=False)
            sd_raw = ck.get("state_dict", ck)
            tgt_keys = set(dict(model.model.model.named_parameters())) | set(dict(model.model.model.named_buffers()))
            prefixes = ("diffusion.model.", "model.")
            sd = max(
                ({(k[len(pfx):] if k.startswith(pfx) else k): v for k, v in sd_raw.items()}
                 for pfx in prefixes),
                key=lambda d: sum(1 for k in d if k in tgt_keys)
            )
            model.model.model.load_state_dict(sd, strict=False)
            print(f"Loaded full-FT DiT weights from {m_cfg['ckpt_path']}.")
        elif m_cfg["loras"]:
            paths = [p for p, _ in m_cfg["loras"]]
            print(f"  Applying {len(paths)} LoRA(s): {paths}")
            model.load_lora(paths)
            for idx, (_, strength) in enumerate(m_cfg["loras"]):
                model.set_lora_strength(float(strength), lora_index=idx)
            n_merged = merge_adapters(model.model)
            print(f"  Merged {n_merged} parametrized modules.")

        decode_dtype = next(model.same.parameters()).dtype

        for cond_name, tgt, weight, wav_path, aac_path in needed:
            task_idx += 1
            t0 = time.time()
            print(f"[{task_idx}/{total_renders}] Rendering {m_id} {cond_name} -> {wav_path.name} ...", flush=True)

            if weight == 0.0:
                latch_configs = None
                latch_hparams = None
            else:
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

    print("\nAll fine-grained renders complete!")

if __name__ == "__main__":
    main()
