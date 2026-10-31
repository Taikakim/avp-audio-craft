#!/usr/bin/env python3
"""render_choice_clips_mood.py -- renders curated choice clips under 56-dim Mood LatCH guidance:
1. Base (gain 0)
2. Space (gain 1024, 2048)
3. Dark (gain 1024, 2048)
4. Melodic (gain 1024, 2048)
5. Aliens HQ excerpt (gain 1024, 2048)

Across our retrained best 40-epoch mood head (ep40) and fast EMA iterate (ep40_ema0.25).
Uses 20.0s (280 latent frames), 24-step flow-matching Euler, native seeds & prompts.
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

HEAD_DIR = Path("/run/media/kim/Mantu/latch_sweep/mood_56d_best_40ep_20261031/C3_mood_lr8e-4_b64_cos40")
HEAD_EP40 = HEAD_DIR / "latch_sa3_effnet_moodtheme_ep40.pt"
HEAD_EMA = HEAD_DIR / "latch_sa3_effnet_moodtheme_ep40_ema0.25.pt"

OUT_WAV_DIR = Path("/run/media/kim/Mantu/sa3_control_runs/choice_clips_mood_20261031")
OUT_AAC_DIR = Path("/home/kim/evals_aac/choice_clips_mood")
OUT_WAV_DIR.mkdir(parents=True, exist_ok=True)
OUT_AAC_DIR.mkdir(parents=True, exist_ok=True)

ALIENS_TIMESERIES = Path("/run/media/kim/Kosmos/timeseries/Total Eclipse - Aliens.TIMESERIES.npz")
ALIENS_START = 6073122
LATENT_FRAMES = 280
TOTAL_SAMPLES = LATENT_FRAMES * 4096
DURATION = 20.0
STEPS = 24
SAMPLE_RATE = 44100

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
    # 1. Space target (idx 49 dominant)
    target_space = np.zeros((56, LATENT_FRAMES), dtype=np.float32)
    target_space[49, :] = 1.0  # space
    target_space[48, :] = 0.3  # soundscape
    target_space[16, :] = 0.3  # dream
    
    # 2. Dark target (idx 11 dominant)
    target_dark = np.zeros((56, LATENT_FRAMES), dtype=np.float32)
    target_dark[11, :] = 1.0  # dark
    target_dark[27, :] = 0.4  # heavy
    target_dark[12, :] = 0.3  # deep
    
    # 3. Melodic target (idx 34 dominant)
    target_melodic = np.zeros((56, LATENT_FRAMES), dtype=np.float32)
    target_melodic[34, :] = 1.0  # melodic
    target_melodic[55, :] = 0.4  # uplifting
    target_melodic[26, :] = 0.3  # happy
    
    # 4. Aliens HQ excerpt target
    data = np.load(ALIENS_TIMESERIES, allow_pickle=True)
    mood_ts = data['effnet_moodtheme_ts']
    meta = json.loads(str(data['__meta__']))
    rate = meta['field_rates']['effnet_moodtheme_ts']
    start_s = ALIENS_START / 44100.0
    dur_s = 26.006
    f0 = int(round(start_s * rate))
    f1 = int(round((start_s + dur_s) * rate))
    slice_mood = mood_ts[f0:f1] # shape (T_slice, 56)
    raw_t = torch.from_numpy(slice_mood).float().transpose(0, 1).unsqueeze(0) # (1, 56, T_slice)
    target_aliens = torch.nn.functional.interpolate(raw_t, size=LATENT_FRAMES, mode='linear', align_corners=False).squeeze(0).numpy()
    
    return {
        "Space": target_space,
        "Dark": target_dark,
        "Melodic": target_melodic,
        "Aliens": target_aliens
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", default="2,5,7,11,22,28", help="comma-separated row indices or 'all'")
    ap.add_argument("--heads", default="ep40,ep40_ema0.25", help="comma-separated head keys")
    ap.add_argument("--device", default="cuda:0")
    args = ap.parse_args()

    items_file = Path("/home/kim/.gemini/antigravity/brain/62fc5213-e94b-4c13-86bf-69147f02f03c/scratch/render_plan_items.json")
    with open(items_file) as f:
        all_items = json.load(f)

    if args.rows == "all":
        items = all_items
    else:
        row_indices = [int(x.strip()) for x in args.rows.split(",") if x.strip()]
        items = [it for it in all_items if it['idx'] in row_indices]

    targets = build_mood_targets()
    print(f"Precomputed 56-dim mood targets for {LATENT_FRAMES} frames: Space, Dark, Melodic, Aliens")

    available_heads = {
        "ep40": HEAD_EP40,
        "ep40_ema0.25": HEAD_EMA,
    }
    selected_heads = [(h, available_heads[h]) for h in args.heads.split(",") if h in available_heads]

    conditions = [
        ("Space_g1024", targets["Space"], 1024.0),
        ("Space_g2048", targets["Space"], 2048.0),
        ("Dark_g1024", targets["Dark"], 1024.0),
        ("Dark_g2048", targets["Dark"], 2048.0),
        ("Melodic_g1024", targets["Melodic"], 1024.0),
        ("Melodic_g2048", targets["Melodic"], 2048.0),
        ("Aliens_g1024", targets["Aliens"], 1024.0),
        ("Aliens_g2048", targets["Aliens"], 2048.0),
    ]

    total_tasks = len(items) * (1 + len(selected_heads) * len(conditions))
    task_idx = 0

    print(f"Total rows to render: {len(items)}, Heads: {[h[0] for h in selected_heads]}, Conditions: {len(conditions)} (+ base)")

    for item in items:
        row_idx = item['idx']
        label = item['label']
        model_name = item['model']
        is_fullft = item['is_fullft']
        ckpt_path = item['ckpt_path']
        seed = item['seed']
        cfg = item['cfg']
        strength = item['strength']
        prompt = item['prompt_text']

        print(f"\n=======================================================")
        print(f"[Row {row_idx:02d}] {label}")
        print(f"Model: {model_name} | Ckpt: {item['ckpt_tag']} | CFG: {cfg} | Seed: {seed}")
        print(f"Prompt: {prompt}")
        print(f"=======================================================")

        # Check if tasks are needed for this model
        needed = []
        # 1. Base unguided
        base_wav = OUT_WAV_DIR / f"mood_row{row_idx:02d}__{model_name}__{item['ckpt_tag']}__base__s{seed}.wav"
        base_aac = OUT_AAC_DIR / f"mood_row{row_idx:02d}__{model_name}__{item['ckpt_tag']}__base__s{seed}.m4a"
        if not (base_wav.exists() and base_aac.exists()):
            chroma_base = Path(f"/run/media/kim/Mantu/sa3_control_runs/choice_clips_chroma_20261030/choice_{row_idx:02d}__{model_name}__{item['ckpt_tag']}__base__s{seed}.wav")
            chroma_aac = Path(f"/home/kim/evals_aac/choice_clips_chroma/choice_{row_idx:02d}__{model_name}__{item['ckpt_tag']}__base__s{seed}.m4a")
            if chroma_base.exists() and chroma_aac.exists():
                import shutil
                shutil.copy2(chroma_base, base_wav)
                shutil.copy2(chroma_aac, base_aac)
                print(f"  [cached base] Reused existing unguided render from choice_clips_chroma")
            else:
                needed.append(("base", None, None, 0.0, base_wav, base_aac))

        # 2. Guided conditions
        for head_tag, head_ckpt in selected_heads:
            for cond_name, tgt, weight in conditions:
                wav_path = OUT_WAV_DIR / f"mood_row{row_idx:02d}__{model_name}__{item['ckpt_tag']}__{head_tag}__{cond_name}__s{seed}.wav"
                aac_path = OUT_AAC_DIR / f"mood_row{row_idx:02d}__{model_name}__{item['ckpt_tag']}__{head_tag}__{cond_name}__s{seed}.m4a"
                if not (wav_path.exists() and aac_path.exists()):
                    needed.append((head_tag, head_ckpt, tgt, weight, wav_path, aac_path))

        if not needed:
            print(f"All renders for Row {row_idx:02d} already exist! Skipping model load.")
            continue

        print(f"Loading base model onto {args.device} for {len(needed)} clips...")
        model = StableAudioModel.from_pretrained("medium-base", device=args.device)

        if not is_fullft and ckpt_path:
            print(f"  Applying LoRA adapter: {ckpt_path} (strength {strength})")
            model.load_lora([str(ckpt_path)])
            if strength != 1.0:
                model.set_lora_strength(float(strength))
            n_merged = merge_adapters(model.model)
            print(f"  Merged {n_merged} parametrized modules.")

        decode_dtype = next(model.same.parameters()).dtype

        for head_tag, head_ckpt, tgt, weight, wav_path, aac_path in needed:
            task_idx += 1
            t0 = time.time()
            desc = "base" if head_tag == "base" else f"{head_tag} {wav_path.name.split('__')[-2]}"
            print(f"[{task_idx}] Rendering {desc} -> {wav_path.name} ...", flush=True)

            if head_tag == "base":
                latch_configs = None
                latch_hparams = None
            else:
                latch_configs = [{
                    "model_path": str(head_ckpt),
                    "target_raw": tgt,
                    "weight": float(weight),
                    "loss_type": "cosine",
                    "start_pct": 0.0,
                    "end_pct": 1.0,
                }]
                latch_hparams = {"n_iter": 4, "gamma": 0.3}

            z0 = model.generate(
                prompt=prompt,
                duration=DURATION,
                steps=STEPS,
                cfg_scale=float(cfg),
                seed=int(seed),
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

    print("\nAll renders complete!")

if __name__ == "__main__":
    main()
