#!/usr/bin/env python3
"""render_choice_clips_chroma.py -- renders the 29 curated choice clips under 4 conditions:
1. Base (gain 0)
2. C major triad (gain 2048)
3. Eb major triad (gain 2048)
4. Total Eclipse - Aliens HQ excerpt (gain 2048)

Uses 20.0s (280 latent frames), 24-step flow-matching Euler, native seeds & prompts,
and latch_sa3_same_chroma_ep10.pt (same_chroma_e13).
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

LATCH_CKPT = "/run/media/kim/Mantu/latch_sweep/chroma_retrain_2026-10-16/C3_chroma_d512_lr1e-3/latch_sa3_same_chroma_ep10.pt"
OUT_WAV_DIR = Path("/run/media/kim/Mantu/sa3_control_runs/choice_clips_chroma_20261030")
OUT_AAC_DIR = Path("/home/kim/evals_aac/choice_clips_chroma")
OUT_WAV_DIR.mkdir(parents=True, exist_ok=True)
OUT_AAC_DIR.mkdir(parents=True, exist_ok=True)

ALIENS_MP3 = "/run/media/kim/Mantu/goa_archive_extracted/Goa.PsyTrance.Collection.1994/VA_-_Order_Odonata_1-(HQ)-(BFLCD13)-1994-ZAiK_iNT/03-total_eclipse_-_aliens.mp3"
ALIENS_START = 6073122
LATENT_FRAMES = 280
TOTAL_SAMPLES = LATENT_FRAMES * 4096  # 1146880 samples at 44100 Hz = 26.006s window adapted for 20s clip
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
    # 1. C major target
    target_c = CSR.build_target_raw(384, {"kind": "static", "chord": "C"}, LATENT_FRAMES)
    
    # 2. Eb major target
    target_eb = CSR.build_target_raw(384, {"kind": "static", "chord": "Eb"}, LATENT_FRAMES)
    
    # 3. HQ Aliens excerpt target
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
    with open("/home/kim/.gemini/antigravity/brain/62fc5213-e94b-4c13-86bf-69147f02f03c/scratch/render_plan_items.json") as f:
        items = json.load(f)

    targets = build_targets()
    print(f"Precomputed targets for 280 frames: C {targets['C'].shape}, Eb {targets['Eb'].shape}, Aliens {targets['Aliens'].shape}")

    conditions = [
        ("base", None, 0.0),
        ("C", targets["C"], 2048.0),
        ("Eb", targets["Eb"], 2048.0),
        ("Aliens", targets["Aliens"], 2048.0),
        ("C_g1024", targets["C"], 1024.0),
        ("C_g3072", targets["C"], 3072.0),
        ("Eb_g1024", targets["Eb"], 1024.0),
        ("Eb_g3072", targets["Eb"], 3072.0),
        ("Aliens_g1024", targets["Aliens"], 1024.0),
        ("Aliens_g3072", targets["Aliens"], 3072.0),
    ]

    manifest_entries = []
    total_renders = len(items) * len(conditions)
    render_idx = 0

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
        z0_orig_path = item['z0_path']

        print(f"\n=======================================================")
        print(f"[{row_idx:02d}/29] {label}")
        print(f"Model: {model_name} | Ckpt: {item['ckpt_tag']} ({ckpt_path}) | FullFT: {is_fullft} | CFG: {cfg} | w: {strength}")
        print(f"=======================================================")

        # Check which conditions need rendering
        needed_conds = []
        for cond_name, tgt, weight in conditions:
            base_filename = f"choice_{row_idx:02d}__{model_name}__{item['ckpt_tag']}__{cond_name}__s{seed}"
            wav_path = OUT_WAV_DIR / f"{base_filename}.wav"
            aac_path = OUT_AAC_DIR / f"{base_filename}.m4a"
            if not (wav_path.exists() and aac_path.exists()):
                needed_conds.append((cond_name, tgt, weight, wav_path, aac_path))
            else:
                manifest_entries.append({
                    "row_idx": row_idx,
                    "cond": cond_name,
                    "label": label,
                    "model": model_name,
                    "ckpt": item['ckpt_tag'],
                    "file": f"{base_filename}.m4a",
                    "seed": seed,
                    "cfg": cfg,
                    "strength": strength,
                    "prompt": prompt
                })

        if not needed_conds:
            print(f"All 4 conditions already rendered for row {row_idx}. Skipping.")
            continue

        # Load model
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

        for cond_name, tgt, weight, wav_path, aac_path in needed_conds:
            render_idx += 1
            t0 = time.time()
            print(f"Rendering [{render_idx}/{total_renders}] {wav_path.name} ...", flush=True)

            if weight == 0.0:
                # Base unguided render: if original z0 exists and matches, we can decode it directly or generate fresh
                latch_configs = None
                latch_hparams = None
            else:
                latch_configs = [{
                    "model_path": LATCH_CKPT,
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

            manifest_entries.append({
                "row_idx": row_idx,
                "cond": cond_name,
                "label": label,
                "model": model_name,
                "ckpt": item['ckpt_tag'],
                "file": aac_path.name,
                "seed": seed,
                "cfg": cfg,
                "strength": strength,
                "prompt": prompt
            })

        del model
        torch.cuda.empty_cache()

    manifest_file = OUT_AAC_DIR / "choice_clips_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest_entries, f, indent=2)
    print(f"\nAll renders complete. Wrote manifest to {manifest_file}.")
    os._exit(0)

if __name__ == "__main__":
    main()
