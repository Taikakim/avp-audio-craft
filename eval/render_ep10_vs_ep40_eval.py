#!/usr/bin/env python3
"""render_ep10_vs_ep40_eval.py -- renders comparison clips for the new 40-epoch head
(ep40 online/final and ep40_ema0.25) vs historical ep10 across 6 representative choice models.
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
import soundfile as sf
import torch.nn.utils.parametrize as P

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stable-audio-3"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
sys.path.insert(0, str(ROOT / "control"))

from stable_audio_3 import StableAudioModel
from harmonic import same_chroma as sc
import chroma_steer_render as CSR
from sa3_control.audio_io import save_audio

HEAD_EP40 = "/run/media/kim/Mantu/latch_sweep/chroma_retrain_best_40ep_20261030/C3_best_lr8e-4_b64_cos40/latch_sa3_same_chroma_ep40.pt"
HEAD_EMA = "/run/media/kim/Mantu/latch_sweep/chroma_retrain_best_40ep_20261030/C3_best_lr8e-4_b64_cos40/latch_sa3_same_chroma_ep40_ema0.25.pt"

OUT_WAV_DIR = Path("/run/media/kim/Mantu/sa3_control_runs/ep10_vs_ep40_chroma")
OUT_AAC_DIR = Path("/home/kim/evals_aac/ep10_vs_ep40_chroma")
OUT_WAV_DIR.mkdir(parents=True, exist_ok=True)
OUT_AAC_DIR.mkdir(parents=True, exist_ok=True)

ALIENS_MP3 = "/run/media/kim/Mantu/goa_archive_extracted/Goa.PsyTrance.Collection.1994/VA_-_Order_Odonata_1-(HQ)-(BFLCD13)-1994-ZAiK_iNT/03-total_eclipse_-_aliens.mp3"
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

def build_targets():
    target_c = CSR.build_target_raw(384, {"kind": "static", "chord": "C"}, LATENT_FRAMES)
    target_eb = CSR.build_target_raw(384, {"kind": "static", "chord": "Eb"}, LATENT_FRAMES)
    
    audio, sr = sf.read(ALIENS_MP3, start=ALIENS_START, stop=ALIENS_START + TOTAL_SAMPLES, always_2d=True)
    ch = sc.compute_same_chroma(audio, sr, align_to_latent=False)
    raw = torch.from_numpy(ch).float().view(384, -1).unsqueeze(0)
    target_aliens = torch.nn.functional.interpolate(raw, size=LATENT_FRAMES, mode='linear', align_corners=False).squeeze(0).numpy()
    
    return {
        "C": target_c,
        "Eb": target_eb,
        "Aliens": target_aliens
    }

def main():
    items_file = Path("/home/kim/.gemini/antigravity/brain/62fc5213-e94b-4c13-86bf-69147f02f03c/scratch/render_plan_items.json")
    with open(items_file) as f:
        all_items = json.load(f)

    selected_rows = [2, 5, 7, 11, 22, 28]
    items = [it for it in all_items if it['idx'] in selected_rows]

    targets = build_targets()
    print(f"Precomputed targets for {LATENT_FRAMES} frames: C, Eb, Aliens")

    # Evaluate ep40 and ep40_ema0.25
    heads = [
        ("ep40", HEAD_EP40),
        ("ep40_ema0.25", HEAD_EMA),
    ]

    conditions = [
        ("C_g1024", targets["C"], 1024.0),
        ("C_g2048", targets["C"], 2048.0),
        ("Eb_g1024", targets["Eb"], 1024.0),
        ("Eb_g2048", targets["Eb"], 2048.0),
        ("Aliens_g1024", targets["Aliens"], 1024.0),
        ("Aliens_g2048", targets["Aliens"], 2048.0),
    ]

    total_tasks = len(items) * len(heads) * len(conditions)
    task_idx = 0

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

        # Determine which tasks actually need rendering
        needed_tasks = []
        for head_tag, head_ckpt in heads:
            for cond_name, tgt, weight in conditions:
                base_stem = f"ep10vs40_row{row_idx:02d}__{model_name}__{item['ckpt_tag']}__{head_tag}__{cond_name}__s{seed}"
                wav_path = OUT_WAV_DIR / f"{base_stem}.wav"
                aac_path = OUT_AAC_DIR / f"{base_stem}.m4a"
                if not (wav_path.exists() and aac_path.exists()):
                    needed_tasks.append((head_tag, head_ckpt, cond_name, tgt, weight, wav_path, aac_path))

        if not needed_tasks:
            print(f"Row {row_idx:02d} ({label}) already fully rendered. Skipping.")
            continue

        print(f"\n=======================================================")
        print(f"Row {row_idx:02d}: {label} | Tasks needed: {len(needed_tasks)}")
        print(f"=======================================================")

        model = StableAudioModel.from_pretrained("medium-base", device="cuda")
        decode_dtype = next(model.same.parameters()).dtype

        if is_fullft and ckpt_path:
            ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
            sd_raw = ck.get("state_dict", ck)
            tgt_keys = set(dict(model.model.model.named_parameters())) | set(dict(model.model.model.named_buffers()))
            prefixes = ("diffusion.model.", "model.")
            sd = max(
                ({(k[len(pfx):] if k.startswith(pfx) else k): v for k, v in sd_raw.items()}
                 for pfx in prefixes),
                key=lambda d: sum(1 for k in d if k in tgt_keys)
            )
            model.model.model.load_state_dict(sd, strict=False)
            print(f"Loaded full-FT DiT weights from {ckpt_path}.")
        elif not is_fullft and ckpt_path:
            model.load_lora([str(ckpt_path)])
            model.set_lora_strength(strength)
            n_m = merge_adapters(model.model)
            print(f"Loaded adapter from {ckpt_path} (strength={strength}) and merged {n_m} parametrizations.")

        for head_tag, head_ckpt, cond_name, tgt, weight, wav_path, aac_path in needed_tasks:
            task_idx += 1
            t0 = time.time()
            print(f"[{task_idx}/{total_tasks}] Rendering {head_tag} {cond_name} -> {aac_path.name} ...", flush=True)

            latch_configs = [{
                "model_path": head_ckpt,
                "target_raw": tgt,
                "weight": weight,
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
                print(f"WARNING: Non-finite latent in {wav_path.name}! Skipping.", flush=True)
                continue

            with torch.no_grad():
                audio = model.same.decode(z0.to(decode_dtype))
            audio = audio.to(torch.float32)[:, :, :int(DURATION * SAMPLE_RATE)]
            save_audio(str(wav_path), audio[0].cpu(), SAMPLE_RATE, normalize=True)
            transcode_to_aac(wav_path, aac_path)
            print(f"  -> Done in {time.time() - t0:.1f}s: {aac_path.name}", flush=True)

        del model
        torch.cuda.empty_cache()

    print("\nAll evaluation renders complete!")

if __name__ == "__main__":
    main()
