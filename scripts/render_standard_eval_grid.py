#!/usr/bin/env python3
"""render_standard_eval_grid.py -- Renders the canonical 12 standard evaluation clips
across CFG scales (7.0, 16.0) and LoRA adapter weights (1.0, 1.5, 2.0) = 72 clips total.

Hardware & Execution Guards:
- Avoids AMD GFX1201 attention instruction traps by disabling Triton flash attention.
- Uses PyTorch SDPA in bfloat16 for the DiT diffusion sampling.
- Uses the native float16 precision for pretransform autoencoder decode OUTSIDE autocast
  (preventing DAC / autoencoder activation overflow NaNs).
- Saves both 44.1kHz 16-bit .wav and pre-decode .z0.npy latents.
- Resumable: skips cells whose .wav and .z0.npy already exist on disk.
- Automatically calculates discontinuity jumps and DSP timbral metrics across the grid.
"""

import os
import sys
import time
import argparse
import json
from pathlib import Path

# Environment setup
os.environ["FLASH_ATTENTION_TRITON_AMD_ENABLE"] = "FALSE"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["MIOPEN_FIND_MODE"] = "2"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

# Prevent torchcodec namespace package resolution crash in Python 3.13
import transformers.utils.import_utils as _iu
_iu.is_torchcodec_available = lambda: False

import torch
import numpy as np
import soundfile as sf
import scipy.signal

# Attention routing
import stable_audio_3.models.transformer as T
T.flash_attn_func = None
T.flash_attn_varlen_func = None

from stable_audio_3 import StableAudioModel

# The Canonical 12 Standard Prompts from eval/model_matrix_gen.py::build_prompts(3, 3)
STANDARD_PROMPTS = [
    {
        "id": "rb_common_0",
        "seed": 786795416,
        "text": "2020s goa trance, melodic mood, 148 bpm",
    },
    {
        "id": "rb_common_1",
        "seed": 225176290,
        "text": "mid 90s goa trance, melodic space mood, 140 bpm",
    },
    {
        "id": "rb_common_2",
        "seed": 544354203,
        "text": "mid 90s goa trance, 148 bpm",
    },
    {
        "id": "rb_mid_3",
        "seed": 92101475,
        "text": "2010s techno, tech trance, space mood, 142 bpm",
    },
    {
        "id": "rb_mid_4",
        "seed": 1331736365,
        "text": "mid 90s psy-trance, goa trance, 142 bpm",
    },
    {
        "id": "rb_mid_5",
        "seed": 232172918,
        "text": "2020s goa trance, melodic space mood, 144 bpm",
    },
    {
        "id": "rb_rare_6",
        "seed": 564875484,
        "text": "mid 90s techno, house, 130 bpm",
    },
    {
        "id": "rb_rare_7",
        "seed": 16488276,
        "text": "2010s psy-trance, progressive trance, 136 bpm",
    },
    {
        "id": "rb_rare_8",
        "seed": 278158216,
        "text": "mid 90s goa trance, techno, space dark mood, 140 bpm",
    },
    {
        "id": "kl_0",
        "seed": 1000,
        "text": (
            "This track is an instrumental Psytrance piece that blends classic Goa-style melodic "
            "arpeggios with modern, high-fidelity production. It sits at 150 BPM in 4/4 time and is "
            "rooted in F minor, though the harmonic content is intentionally sparse, focusing instead "
            "on evolving textures and driving rhythmic momentum."
        ),
    },
    {
        "id": "kl_1",
        "seed": 1001,
        "text": (
            "This track is an instrumental jazz-fusion piece that blends funk-driven grooves with a "
            "subtle disco-house aesthetic. It sits at 125 BPM in C major, and its polished, high-fidelity "
            "production emphasizes a wide stereo image and clean separation of each instrument."
        ),
    },
    {
        "id": "kl_2",
        "seed": 1002,
        "text": (
            "This track is an intense Psytrance piece, rooted in the Goa Trance sub-genre and blending "
            "classic psychedelic trance aesthetics with a modern, high-energy production style. "
            "It runs at ≈142.86 BPM in a 4/4 time signature and is centered in F minor."
        ),
    },
]


def compute_dsp_metrics(mono: np.ndarray, sr: int):
    """Compute key DSP audio features."""
    peak = float(np.abs(mono).max())
    rms = float(np.sqrt(np.mean(mono**2)))
    crest = float(peak / (rms + 1e-12))
    
    # Spectral metrics via Welch PSD
    freqs, psd = scipy.signal.welch(mono, fs=sr, nperseg=2048)
    psd_sum = np.sum(psd)
    centroid = float(np.sum(freqs * psd) / (psd_sum + 1e-12))
    
    # Spectral flatness (geometric mean / arithmetic mean)
    geo_mean = np.exp(np.mean(np.log(psd + 1e-12)))
    arith_mean = np.mean(psd)
    flatness = float(geo_mean / (arith_mean + 1e-12))
    
    # Discontinuity jumps
    diffs = np.abs(np.diff(mono))
    jumps_06 = int((diffs > 0.6).sum())
    jumps_04 = int((diffs > 0.4).sum())
    max_jump = float(diffs.max()) if len(diffs) > 0 else 0.0

    return {
        "peak": round(peak, 4),
        "rms": round(rms, 4),
        "crest_factor": round(crest, 2),
        "spectral_centroid_hz": round(centroid, 1),
        "spectral_flatness": round(flatness, 6),
        "max_jump": round(max_jump, 4),
        "jumps_06": jumps_06,
        "jumps_04": jumps_04,
    }


def main():
    parser = argparse.ArgumentParser(description="Render 72-clip standard eval grid")
    parser.add_argument(
        "--ckpt",
        type=str,
        default="/run/media/kim/Mantu/sa3_lora_runs/modular_opt_cubic5_sf_ev_20ep_13500s_2026-09-21_0148/step=13500.ckpt",
        help="Path to checkpoint",
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        default="/run/media/kim/Mantu/sa3_lora_runs/modular_opt_cubic5_sf_ev_20ep_13500s_2026-09-21_0148/standard_grid",
        help="Output directory",
    )
    parser.add_argument(
        "--cfgs",
        type=float,
        nargs="+",
        default=[7.0, 16.0],
        help="CFG scales",
    )
    parser.add_argument(
        "--weights",
        type=float,
        nargs="+",
        default=[1.0, 1.5, 2.0],
        help="LoRA adapter weights (strengths)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=20.0,
        help="Duration in seconds",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=24,
        help="Number of diffusion steps",
    )
    parser.add_argument(
        "--skip_existing",
        action="store_true",
        default=True,
        help="Skip clips that already exist",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=================================================================")
    print("SA3 LoRA Standard Evaluation Grid Renderer")
    print(f"Checkpoint:       {args.ckpt}")
    print(f"Output Directory: {out_dir}")
    print(f"Prompts:          {len(STANDARD_PROMPTS)} canonical standard prompts")
    print(f"CFG Scales:       {args.cfgs}")
    print(f"LoRA Weights:     {args.weights}")
    print(f"Duration:         {args.duration}s ({args.steps} steps)")
    total_clips = len(STANDARD_PROMPTS) * len(args.cfgs) * len(args.weights)
    print(f"Total Clips:      {total_clips}")
    print("=================================================================\n", flush=True)

    # Load Base Model
    print("[1/3] Loading StableAudioModel ('medium-base') onto CUDA...")
    t0 = time.time()
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    print(f"      Base model loaded in {time.time() - t0:.2f}s\n", flush=True)

    # Load LoRA Checkpoint
    print(f"[2/3] Loading LoRA checkpoint from {Path(args.ckpt).name}...")
    t0 = time.time()
    model.load_lora([args.ckpt])
    print(f"      LoRA loaded and applied in {time.time() - t0:.2f}s\n", flush=True)

    sr = model.model.sample_rate
    pt = model.same
    decode_dtype = next(pt.parameters()).dtype

    print(f"[3/3] Commencing Grid Generation ({total_clips} cells)...")
    clip_idx = 0
    grid_records = []

    for w in args.weights:
        model.set_lora_strength(w)
        print(f"\n>>> Switched LoRA Strength w = {w:.1f} <<<", flush=True)

        for cfg in args.cfgs:
            for p in STANDARD_PROMPTS:
                clip_idx += 1
                pid = p["id"]
                seed = p["seed"]
                ptext = p["text"]

                wav_name = f"step13500__cfg{cfg:.1f}_w{w:.1f}__{pid}.wav"
                z0_name = f"step13500__cfg{cfg:.1f}_w{w:.1f}__{pid}.z0.npy"
                wav_path = out_dir / wav_name
                z0_path = out_dir / z0_name

                if args.skip_existing and wav_path.exists() and z0_path.exists():
                    print(f"[{clip_idx:2d}/{total_clips}] [SKIP-EXISTING] {wav_name}", flush=True)
                    # Load existing for catalog
                    au, _ = sf.read(str(wav_path), always_2d=True)
                    mono = au.mean(axis=1)
                    dsp = compute_dsp_metrics(mono, sr)
                    z0 = np.load(str(z0_path))
                    grid_records.append({
                        "file": wav_name,
                        "cfg": cfg,
                        "weight": w,
                        "prompt_id": pid,
                        "seed": seed,
                        "latent_std": round(float(z0.std()), 4),
                        **dsp
                    })
                    continue

                t_gen0 = time.time()
                # 1. Diffusion Sampling in bfloat16
                with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                    z0 = model.generate(
                        prompt=ptext,
                        duration=args.duration,
                        steps=args.steps,
                        cfg_scale=float(cfg),
                        seed=seed,
                        return_latents=True,
                    )

                if not torch.all(torch.isfinite(z0)):
                    print(f"[{clip_idx:2d}/{total_clips}] !! ERROR: Non-finite latents for {wav_name}! Skipping.")
                    continue

                z0_np = z0.detach().to(torch.float16).cpu().numpy()
                np.save(str(z0_path), z0_np)
                z0_std = float(z0_np.std())

                # 2. Pretransform Decode OUTSIDE autocast in native decode_dtype
                with torch.no_grad():
                    audio = pt.decode(z0.to(decode_dtype))

                # Truncate to duration and peak-normalize to 0.988
                audio = audio.to(torch.float32)[:, :, :int(args.duration * sr)]
                audio_np = audio[0].cpu().numpy().T
                peak = np.abs(audio_np).max()
                if peak > 1e-6:
                    audio_norm = (audio_np / peak) * 0.988
                else:
                    audio_norm = audio_np

                sf.write(str(wav_path), audio_norm, sr, subtype="PCM_16")
                gen_sec = time.time() - t_gen0

                mono = audio_norm.mean(axis=1)
                dsp = compute_dsp_metrics(mono, sr)

                print(f"[{clip_idx:2d}/{total_clips}] cfg={cfg:4.1f} w={w:3.1f} | {pid:11s} | "
                      f"{gen_sec:4.1f}s | RMS={dsp['rms']:.3f} | peak={dsp['peak']:.3f} | "
                      f"z0_std={z0_std:.3f} | jumps={dsp['jumps_06']}", flush=True)

                grid_records.append({
                    "file": wav_name,
                    "cfg": cfg,
                    "weight": w,
                    "prompt_id": pid,
                    "seed": seed,
                    "latent_std": round(z0_std, 4),
                    **dsp
                })

    # Save Catalog
    catalog_path = out_dir / "grid_metrics.json"
    with open(catalog_path, "w") as f:
        json.dump(grid_records, f, indent=2)
    print(f"\n[COMPLETE] Saved grid metrics to {catalog_path}")

    # Print Summary Grid Table
    print("\n" + "=" * 90)
    print(f"{'EVALUATION GRID SUMMARY: step=13500 across CFG & LoRA Strength':^90}")
    print("=" * 90)
    print(f"{'Condition':<18} | {'Mean RMS':<9} | {'Crest':<7} | {'Centroid':<11} | {'Flatness':<10} | {'Latent Std':<11} | {'Jumps>0.6':<9}")
    print("-" * 90)

    for cfg in args.cfgs:
        for w in args.weights:
            cells = [r for r in grid_records if r["cfg"] == cfg and r["weight"] == w]
            if not cells:
                continue
            mean_rms = np.mean([c["rms"] for c in cells])
            mean_crest = np.mean([c["crest_factor"] for c in cells])
            mean_centroid = np.mean([c["spectral_centroid_hz"] for c in cells])
            mean_flatness = np.mean([c["spectral_flatness"] for c in cells])
            mean_std = np.mean([c["latent_std"] for c in cells])
            total_jumps = sum(c["jumps_06"] for c in cells)

            cond_str = f"cfg={cfg:.1f}, w={w:.1f}"
            print(f"{cond_str:<18} | {mean_rms:<9.4f} | {mean_crest:<7.2f} | {mean_centroid:<9.1f}Hz | {mean_flatness:<10.6f} | {mean_std:<11.4f} | {total_jumps:<9d}")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    main()
