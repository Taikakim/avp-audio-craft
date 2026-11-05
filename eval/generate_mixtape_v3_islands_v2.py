#!/usr/bin/env python3
"""generate_mixtape_v3_islands_v2.py -- Upgraded Mixtape V3 Island + 20s Div4 Bridge Architecture.

Key Improvements over V1:
1. Long Compositional Bridge:
   - Middle in-paint section is guaranteed >= 20 seconds and divisible by 4 bars (12 or 16 bars).
   - Island A is 8 bars (~13s), Bridge is 12-16 bars (~20-26s), Island B is 8 bars (~13s).
   - Bridge occupies 43-50% of the duration, creating a genuine structural transition.
2. Moderate A2A Denoising (0.50):
   - Reduced from 0.60 to 0.50 to preserve harmonic anchor, BPM, and scale while restyling texture.
   - Enriched grounding prompts explicitly anchor key, tempo, and signature instruments.
3. Dual Destination Islands:
   - Island B1 (A2A seed + 88)
   - Island B2 (A2A seed + 89)
   - Produces distinct destination targets with their own inpaint bridges.
4. Active Transitional Prompting for Mode A:
   - Distinct inpaint seed and bridge prompt so non-noised pair generates a dynamic build/break.
5. Model Scaling & DoRA Stacking:
   - Supports --fullft_w (e.g. 1.0, 1.25, 1.50) via norm-preserving extrapolation blend_param.
   - Supports --dora_ckpt and --dora_w (e.g. dora128adj or subloss_k24 at 0.2 - 1.2).
"""
import os
import sys
import time
import json
import argparse
import subprocess
import torch
import numpy as np
import soundfile as sf

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
from forge.fullft import load_fullft, _state_dict, ema_info
from sa3_control.audio_io import save_audio
from stable_audio_3 import StableAudioModel
from dj_beatmatch import madmom_downbeats
sys.path.insert(0, "/home/kim/Projects/mir/src")
from tools.create_training_crops import find_zero_crossing_backwards

SR = 44100
DEFAULT_OUT_DIR = "/run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_v3_islands_v2"
DEFAULT_AAC_DIR = os.path.expanduser("~/evals_aac/mixtape_trackpool_v3_islands_v2")
DEFAULT_FULLFT_CKPT = "/run/media/kim/Mantu/sa3_lora_runs/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt"
DEFAULT_DORA_CKPT = "/run/media/kim/Mantu/sa3_lora_runs/__finetunes/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt"

CFG_DEFAULT = 10.0
STEPS_DEFAULT = 24

TRACKS = [
    {
        "pid": "p00",
        "seed": 1321560844,
        "bpm": 143.0,
        "key": "G minor",
        "prompt_core": "2020s goa trance, space retro mood, 143 bpm",
        "prompt_ext": "2020s goa trance, space retro mood, 143 bpm, G minor, Roland SH-101 lead, euphoric mood, steady 143 bpm, tight groove, high fidelity",
        "prompt_bridge": "2020s goa trance, 143 bpm, atmospheric breakdown, soaring filter sweep, cosmic resonance, steady tempo"
    },
    {
        "pid": "p01",
        "seed": 1382257276,
        "bpm": 136.0,
        "key": "F# minor",
        "prompt_core": "psychedelic trance, 136 bpm, bubbling acid line, pulsating sub bass, tight kick and hi-hats, mystical",
        "prompt_ext": "psychedelic trance, 136 bpm, bubbling acid line, pulsating sub bass, tight kick and hi-hats, mystical, goa trance, TB-303 resonance, F# minor, steady 136 bpm",
        "prompt_bridge": "psychedelic trance, 136 bpm, bubbling 303 acid line build-up, resonant filter modulation, rising tension, steady groove"
    },
    {
        "pid": "p02",
        "seed": 729796532,
        "bpm": 125.0,
        "key": "Eb major",
        "prompt_core": "high-energy psytrance, driving classic goa trance, polished production, 125 bpm, E-flat major, lush jazzy lift",
        "prompt_ext": "high-energy psytrance, driving classic goa trance, polished production, 125 bpm, E-flat major, analog lead, cosmic mood, steady 125 bpm",
        "prompt_bridge": "driving classic goa trance, 125 bpm, Eb major, lush jazzy lift, euphoric arpeggio sweep, transitional bridge, steady tempo"
    },
    {
        "pid": "p03",
        "seed": 158725066,
        "bpm": 132.0,
        "key": "A minor",
        "prompt_core": "2020s tech trance, trance, space mood, 132 bpm",
        "prompt_ext": "2020s tech trance, trance, space mood, 132 bpm, goa trance, euphoric mood, A minor, steady 132 bpm, metallic pluck texture",
        "prompt_bridge": "2020s tech trance, 132 bpm, space mood, rising arpeggiator, industrial percussion build, transitional sweep"
    },
    {
        "pid": "p04",
        "seed": 782949196,
        "bpm": 151.0,
        "key": "D minor",
        "prompt_core": "mid 90s goa trance, melodic mood, 151 bpm",
        "prompt_ext": "mid 90s goa trance, melodic mood, 151 bpm, hypnotic arpeggio, uplifting mood, D minor, steady 151 bpm, soaring harmony",
        "prompt_bridge": "mid 90s goa trance, 151 bpm, melodic mood, soaring dual-lead harmony, frantic 16th-note arpeggios, atmospheric build"
    },
    {
        "pid": "p05",
        "seed": 1262357892,
        "bpm": 110.0,
        "key": "C minor",
        "prompt_core": "mid 90s goa trance, ambient, space soundscape mood, 110 bpm",
        "prompt_ext": "mid 90s goa trance, ambient, space soundscape mood, 110 bpm, mystical pads, deep meditation, C minor, steady 110 bpm",
        "prompt_bridge": "mid 90s goa trance ambient, 110 bpm, Polivoks psychedelic sfx, dirty analog tape delay, atmospheric drone sweep"
    },
    {
        "pid": "p06",
        "seed": 451991434,
        "bpm": 102.0,
        "key": "E minor",
        "prompt_core": "early 90s downtempo, ambient, meditative soundscape mood, 102 bpm",
        "prompt_ext": "early 90s downtempo, ambient, meditative soundscape mood, 102 bpm, goa trance, lush synth, E minor, steady 102 bpm",
        "prompt_bridge": "early 90s downtempo ambient, 102 bpm, Buchla generative blips, warm Rhodes chords, deep warm sub bass build"
    },
    {
        "pid": "p07",
        "seed": 1391676905,
        "bpm": 145.0,
        "key": "F minor",
        "prompt_core": "early 2000s goa trance, melodic dark mood, 145 bpm",
        "prompt_ext": "early 2000s goa trance, melodic dark mood, 145 bpm, driving acid lead, energetic mood, F minor, steady 145 bpm",
        "prompt_bridge": "early 2000s goa trance, 145 bpm, dark minor 9th bittersweet arpeggios, screaming resonance, sinister space drone build"
    },
    {
        "pid": "p08",
        "seed": 1126148435,
        "bpm": 150.0,
        "key": "G# minor",
        "prompt_core": "hi-tech psytrance, 150 bpm, soaring synth lead, rolling bassline, intricate percussion patterns, dark and hypnotic",
        "prompt_ext": "hi-tech psytrance, 150 bpm, soaring synth lead, rolling bassline, intricate percussion patterns, dark and hypnotic, goa trance, psychedelic mood, steady 150 bpm",
        "prompt_bridge": "hi-tech psytrance, 150 bpm, razor-fast FM zaps, rolling bassline transition, granular glitch sfx, rising tension"
    },
    {
        "pid": "p09",
        "seed": 1403519739,
        "bpm": 147.0,
        "key": "B minor",
        "prompt_core": "late 90s goa trance, 147 bpm",
        "prompt_ext": "late 90s goa trance, 147 bpm, melodic lead, euphoric mood, B minor, steady 147 bpm, TB-303 resonance",
        "prompt_bridge": "late 90s goa trance, 147 bpm, dual 303 acid battle, resonant bandpass filter sweeps, punchy 909 snare rolls build"
    }
]

def slerp_tensor(v0: torch.Tensor, v1: torch.Tensor, t: float) -> torch.Tensor:
    norm_v0, norm_v1 = torch.norm(v0), torch.norm(v1)
    if norm_v0 < 1e-8 or norm_v1 < 1e-8:
        return (1.0 - t) * v0 + t * v1
    u0, u1 = v0 / norm_v0, v1 / norm_v1
    dot = torch.clamp(torch.sum(u0 * u1), -1.0, 1.0)
    if torch.abs(dot) > 0.9995:
        res = (1.0 - t) * u0 + t * u1
    else:
        theta = torch.acos(dot)
        res = (torch.sin((1.0 - t) * theta) * u0 + torch.sin(t * theta) * u1) / torch.sin(theta)
    return res * ((1.0 - t) * norm_v0 + t * norm_v1)

def blend_param(p_base: torch.Tensor, p_ft: torch.Tensor, w: float) -> torch.Tensor:
    if w == 1.0:
        return p_ft.clone()
    elif w < 1.0:
        return slerp_tensor(p_base, p_ft, w)
    else:
        norm_ft = torch.norm(p_ft)
        v = p_base + w * (p_ft - p_base)
        norm_v = torch.norm(v)
        if norm_v < 1e-8:
            return v
        return (v / norm_v) * norm_ft

def find_div4_crop(audio, sr, min_start_sec, target_bars=8, bpm=145.0):
    mono = audio.mean(axis=0)
    db = np.array(madmom_downbeats(audio, sr))
    
    valid_starts = [t for t in db if t >= min_start_sec]
    start_t = valid_starts[0] if valid_starts else db[0]
    start_idx = np.where(db == start_t)[0][0]
    
    target_idx = start_idx + target_bars
    if target_idx < len(db):
        end_t = db[target_idx]
    else:
        sec_per_bar = (60.0 / bpm) * 4.0
        end_t = start_t + target_bars * sec_per_bar
        
    s_samp = find_zero_crossing_backwards(mono, int(start_t * sr), search_window=int(0.05 * sr))
    e_samp = find_zero_crossing_backwards(mono, int(end_t * sr), search_window=int(0.05 * sr))
    
    crop = audio[:, s_samp:e_samp]
    dur = (e_samp - s_samp) / sr
    return crop, dur, s_samp / sr, e_samp / sr

def encode_aac(src, dst):
    cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", src, "-c:a", "aac", "-b:a", "192k", dst]
    subprocess.run(cmd, check=True)

def main():
    parser = argparse.ArgumentParser(description="Generate Mixtape V3 Islands V2 (20s Bridge, 0.50 Denoising, Dual Island B)")
    parser.add_argument("--track", type=str, default=None, help="Process single track pid, e.g. p00 (default: all)")
    parser.add_argument("--fullft_w", type=float, default=1.0, help="Full-FT weight scale (e.g. 1.0, 1.25, 1.50)")
    parser.add_argument("--dora_ckpt", type=str, default=None, help="Optional DoRA checkpoint path")
    parser.add_argument("--dora_w", type=float, default=0.0, help="DoRA strength (0.2 to 1.2)")
    parser.add_argument("--a2a_noise", type=float, default=0.50, help="A2A denoising strength (default: 0.50)")
    parser.add_argument("--min_bridge_sec", type=float, default=20.0, help="Minimum bridge length in seconds (default: 20.0)")
    parser.add_argument("--out_dir", type=str, default=DEFAULT_OUT_DIR, help="Output directory")
    args = parser.parse_args()

    out_dir = args.out_dir
    aac_dir = os.path.join(out_dir, "aac")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(aac_dir, exist_ok=True)

    print(f"=== Initializing Mixtape Islands V2 Generator ===")
    print(f"  Full-FT Weight: {args.fullft_w}")
    print(f"  DoRA: {args.dora_ckpt} (w={args.dora_w})")
    print(f"  A2A Denoising: {args.a2a_noise}")
    print(f"  Min Bridge Sec: {args.min_bridge_sec}s")
    print(f"  Output Dir: {out_dir}")

    # Load Base Model
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    tgt = model.model.model

    # Full-FT Load and Blend
    base_params = {k: v.detach().cpu().clone() for k, v in tgt.named_parameters()}
    sd = _state_dict(DEFAULT_FULLFT_CKPT)
    ei = ema_info(sd)
    use_ema = bool(ei and ei["converged"])
    load_fullft(model, DEFAULT_FULLFT_CKPT, weights="ema" if use_ema else "online", sd=sd)
    ft_params = {k: v.detach().cpu().clone() for k, v in tgt.named_parameters()}
    del sd

    if args.fullft_w != 1.0:
        print(f"  Extrapolating Full-FT weights to w={args.fullft_w} via blend_param...", flush=True)
        with torch.no_grad():
            for k, p in tgt.named_parameters():
                blended = blend_param(base_params[k], ft_params[k], args.fullft_w)
                p.copy_(blended.to(device="cuda", dtype=p.dtype))

    # DoRA Stack if requested
    if args.dora_ckpt and args.dora_w > 0:
        print(f"  Stacking DoRA {args.dora_ckpt} at strength {args.dora_w}...", flush=True)
        model.load_lora([args.dora_ckpt])
        model.set_lora_strength(args.dora_w)

    manifest_path = os.path.join(out_dir, "cells_islands_v2.jsonl")
    manifest_entries = []

    tracks_to_process = [t for t in TRACKS if args.track is None or t["pid"] == args.track]

    for idx, trk in enumerate(tracks_to_process):
        pid = trk["pid"]
        seed = trk["seed"]
        bpm = trk["bpm"]
        p_core = trk["prompt_core"]
        p_ext = trk["prompt_ext"]
        p_brg = trk["prompt_bridge"]
        t_track_start = time.time()

        print(f"\n[{idx+1}/{len(tracks_to_process)}] Processing {pid} (BPM={bpm}, Seed={seed})...", flush=True)

        # 1. 90-Second Parent Render (or reuse existing if w=1.0)
        # Note: If w != 1.0 or DoRA active, we tag the parent with suffix
        suffix_model = f"_w{int(args.fullft_w*100)}"
        if args.dora_w > 0:
            suffix_model += f"_dora{int(args.dora_w*100)}"

        path_parent = f"{DEFAULT_OUT_DIR}/{pid}_parent_90s{suffix_model}.wav"
        # Fallback to base parent if w=1.0 and no dora
        if args.fullft_w == 1.0 and args.dora_w == 0.0:
            legacy_parent = f"/run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_v3/{pid}_parent_90s.wav"
            if os.path.exists(legacy_parent):
                path_parent = legacy_parent

        if not os.path.exists(path_parent):
            t0 = time.time()
            out_90 = model.generate(prompt=p_core, duration=90.0, steps=STEPS_DEFAULT, cfg_scale=CFG_DEFAULT, seed=seed, batch_size=1)
            raw_90 = out_90[0].float().cpu().numpy()
            save_audio(path_parent, torch.tensor(raw_90), SR)
            print(f"  Rendered 90s parent in {time.time() - t0:.1f}s", flush=True)
        else:
            raw_90, _ = sf.read(path_parent)
            raw_90 = raw_90.T if raw_90.ndim == 2 and raw_90.shape[0] > raw_90.shape[1] else raw_90
            print(f"  Loaded existing 90s parent: {path_parent}", flush=True)

        # 2. Extract Islands A and B (8 bars each = div4)
        crop_a, dur_a, s_a, e_a = find_div4_crop(raw_90, SR, min_start_sec=2.0, target_bars=8, bpm=bpm)
        crop_b, dur_b, s_b, e_b = find_div4_crop(raw_90, SR, min_start_sec=50.0, target_bars=8, bpm=bpm)

        path_core = f"{out_dir}/{pid}_core.wav"
        save_audio(path_core, torch.tensor(crop_a), SR)

        # 3. Calculate Bridge Bars >= 20.0s and Divisible by 4
        sec_per_bar = 4.0 * (60.0 / bpm)
        min_bars = int(np.ceil(args.min_bridge_sec / sec_per_bar))
        bridge_bars = ((min_bars + 3) // 4) * 4 # Round up to multiple of 4 bars (12 or 16 bars)
        gap_sec = bridge_bars * sec_per_bar
        n_gap = int(round(gap_sec * SR))
        n_a = crop_a.shape[-1]
        n_b = crop_b.shape[-1]
        total_samples = n_a + n_gap + n_b
        total_dur = total_samples / SR
        gap_start = n_a / SR
        gap_end = (n_a + n_gap) / SR

        print(f"  Architecture: Island A ({dur_a:.2f}s, 8b) + Bridge ({gap_sec:.2f}s, {bridge_bars}b, >=20s) + Island B ({dur_b:.2f}s, 8b) = Total {total_dur:.2f}s", flush=True)

        # ------------------------------------------------------------------
        # Mode A: Direct 20s+ Div4 Inpaint Bridge
        # ------------------------------------------------------------------
        id_mode_a = f"{pid}_islands_v2_direct_bridge"
        path_mode_a = f"{out_dir}/{id_mode_a}.wav"
        if not os.path.exists(path_mode_a):
            t0 = time.time()
            canvas_a = np.zeros((crop_a.shape[0], total_samples), dtype=np.float32)
            canvas_a[:, :n_a] = crop_a
            canvas_a[:, n_a + n_gap : n_a + n_gap + crop_b.shape[-1]] = crop_b

            out_bridge_a = model.generate(
                prompt=p_brg, duration=total_dur, steps=STEPS_DEFAULT, cfg_scale=CFG_DEFAULT, seed=seed + 77,
                inpaint_audio=(SR, torch.tensor(canvas_a)),
                inpaint_mask_start_seconds=gap_start,
                inpaint_mask_end_seconds=gap_end,
                batch_size=1
            )
            wav_bridge_a = out_bridge_a[0].float().cpu().numpy()
            save_audio(path_mode_a, torch.tensor(wav_bridge_a), SR)
            print(f"  Mode A (Direct 20s Bridge) rendered in {time.time() - t0:.1f}s", flush=True)
        else:
            print(f"  Mode A already exists: {path_mode_a}", flush=True)

        # ------------------------------------------------------------------
        # Mode B1: Island B1 (A2A 0.50, seed+88) + 20s+ Bridge
        # ------------------------------------------------------------------
        id_mode_b1 = f"{pid}_islands_v2_a2a_b1_bridge"
        path_mode_b1 = f"{out_dir}/{id_mode_b1}.wav"
        if not os.path.exists(path_mode_b1):
            t0 = time.time()
            # Step 1: A2A restyle of Island B at noise 0.50 (Seed + 88)
            out_a2a_b1 = model.generate(
                prompt=p_ext, duration=dur_b, steps=STEPS_DEFAULT, cfg_scale=CFG_DEFAULT, seed=seed + 88,
                init_audio=(SR, torch.tensor(crop_b)),
                init_noise_level=args.a2a_noise,
                batch_size=1
            )
            crop_b1_a2a = out_a2a_b1[0].float().cpu().numpy()[:, :n_b]

            # Step 2: Inpaint bridge between Island A and A2A Island B1
            canvas_b1 = np.zeros((crop_a.shape[0], total_samples), dtype=np.float32)
            canvas_b1[:, :n_a] = crop_a
            n_b1_actual = min(crop_b1_a2a.shape[-1], n_b)
            canvas_b1[:, n_a + n_gap : n_a + n_gap + n_b1_actual] = crop_b1_a2a[:, :n_b1_actual]

            out_bridge_b1 = model.generate(
                prompt=p_ext, duration=total_dur, steps=STEPS_DEFAULT, cfg_scale=CFG_DEFAULT, seed=seed + 99,
                inpaint_audio=(SR, torch.tensor(canvas_b1)),
                inpaint_mask_start_seconds=gap_start,
                inpaint_mask_end_seconds=gap_end,
                batch_size=1
            )
            wav_bridge_b1 = out_bridge_b1[0].float().cpu().numpy()
            save_audio(path_mode_b1, torch.tensor(wav_bridge_b1), SR)
            print(f"  Mode B1 (A2A 0.50 Seed+88 + Bridge) rendered in {time.time() - t0:.1f}s", flush=True)
        else:
            print(f"  Mode B1 already exists: {path_mode_b1}", flush=True)

        # ------------------------------------------------------------------
        # Mode B2: Island B2 (A2A 0.50, seed+89) + 20s+ Bridge
        # ------------------------------------------------------------------
        id_mode_b2 = f"{pid}_islands_v2_a2a_b2_bridge"
        path_mode_b2 = f"{out_dir}/{id_mode_b2}.wav"
        if not os.path.exists(path_mode_b2):
            t0 = time.time()
            # Step 1: A2A restyle of Island B at noise 0.50 (Seed + 89)
            out_a2a_b2 = model.generate(
                prompt=p_ext, duration=dur_b, steps=STEPS_DEFAULT, cfg_scale=CFG_DEFAULT, seed=seed + 89,
                init_audio=(SR, torch.tensor(crop_b)),
                init_noise_level=args.a2a_noise,
                batch_size=1
            )
            crop_b2_a2a = out_a2a_b2[0].float().cpu().numpy()[:, :n_b]

            # Step 2: Inpaint bridge between Island A and A2A Island B2
            canvas_b2 = np.zeros((crop_a.shape[0], total_samples), dtype=np.float32)
            canvas_b2[:, :n_a] = crop_a
            n_b2_actual = min(crop_b2_a2a.shape[-1], n_b)
            canvas_b2[:, n_a + n_gap : n_a + n_gap + n_b2_actual] = crop_b2_a2a[:, :n_b2_actual]

            out_bridge_b2 = model.generate(
                prompt=p_ext, duration=total_dur, steps=STEPS_DEFAULT, cfg_scale=CFG_DEFAULT, seed=seed + 101,
                inpaint_audio=(SR, torch.tensor(canvas_b2)),
                inpaint_mask_start_seconds=gap_start,
                inpaint_mask_end_seconds=gap_end,
                batch_size=1
            )
            wav_bridge_b2 = out_bridge_b2[0].float().cpu().numpy()
            save_audio(path_mode_b2, torch.tensor(wav_bridge_b2), SR)
            print(f"  Mode B2 (A2A 0.50 Seed+89 + Bridge) rendered in {time.time() - t0:.1f}s", flush=True)
        else:
            print(f"  Mode B2 already exists: {path_mode_b2}", flush=True)

        # Encode AACs
        encode_aac(path_parent, f"{aac_dir}/{pid}_parent_90s.m4a")
        encode_aac(path_core, f"{aac_dir}/{pid}_core.m4a")
        encode_aac(path_mode_a, f"{aac_dir}/{id_mode_a}.m4a")
        encode_aac(path_mode_b1, f"{aac_dir}/{id_mode_b1}.m4a")
        encode_aac(path_mode_b2, f"{aac_dir}/{id_mode_b2}.m4a")

        # Record manifest entries
        for mid, mode_name in [(id_mode_a, "direct_20s_bridge"),
                               (id_mode_b1, "a2a_b1_050_bridge"),
                               (id_mode_b2, "a2a_b2_050_bridge")]:
            manifest_entries.append({
                "id": mid,
                "pid": pid,
                "prompt_core": p_core,
                "prompt_ext": p_ext,
                "prompt_bridge": p_brg,
                "mode": mode_name,
                "seed": seed,
                "bpm": bpm,
                "key": trk.get("key", "unknown"),
                "fullft_w": args.fullft_w,
                "dora_ckpt": args.dora_ckpt,
                "dora_w": args.dora_w,
                "a2a_noise": args.a2a_noise,
                "dur": round(total_dur, 2),
                "dur_a": round(dur_a, 2),
                "dur_gap": round(gap_sec, 2),
                "bridge_bars": bridge_bars,
                "dur_b": round(dur_b, 2),
                "gap_start": round(gap_start, 2),
                "gap_end": round(gap_end, 2)
            })

        print(f"  -> Track {pid} complete in {time.time() - t_track_start:.1f}s\n", flush=True)

    with open(manifest_path, "w") as f:
        for entry in manifest_entries:
            f.write(json.dumps(entry) + "\n")

    print(f"=== All Requested Tracks Complete! Wrote manifest to {manifest_path} ===", flush=True)

if __name__ == "__main__":
    main()
    os._exit(0)
