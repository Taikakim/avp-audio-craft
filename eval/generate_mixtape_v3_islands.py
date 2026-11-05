#!/usr/bin/env python3
"""generate_mixtape_v3_islands.py -- Batch generation of full 10-track Mixtape Pool V3 using the 90s Island + 4-Bar Bridge Architecture.

For all 10 tracks (p00-p09):
1. Render 90s parent track at registered seed with fullft_avp_t256_ep80.
2. Beat-quantized zero-crossing crop of two 12-bar (div4) islands:
   - Island A (Core): starts after ~2.0s
   - Island B (Later): starts after ~50.0s
3. Mode A: Direct 4-Bar Inpaint Bridge (exact 16 beats) with moderated prompt (max 2 terms).
4. Mode B: Island B restyled via A2A (0.60 noise) with extension prompt, then 4-bar inpaint bridge.
5. Saves all WAVs and metadata to /run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_v3/
"""
import os
import sys
import time
import json
import torch
import numpy as np
import soundfile as sf
import subprocess

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
from forge.fullft import load_fullft
from sa3_control.audio_io import save_audio
from stable_audio_3 import StableAudioModel
from dj_beatmatch import madmom_downbeats
sys.path.insert(0, "/home/kim/Projects/mir/src")
from tools.create_training_crops import find_zero_crossing_backwards

SR = 44100
OUT_DIR = "/run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_v3"
AAC_DIR = os.path.expanduser("~/evals_aac/mixtape_trackpool_v3")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(AAC_DIR, exist_ok=True)

CKPT = "/run/media/kim/Mantu/sa3_lora_runs/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt"
CFG = 10.0
STEPS = 24

TRACKS = [
    {
        "pid": "p00",
        "seed": 1321560844,
        "bpm": 143.0,
        "prompt_core": "2020s goa trance, space retro mood, 143 bpm",
        "prompt_ext": "2020s goa trance, space retro mood, 143 bpm, Roland SH-101 lead, euphoric mood"
    },
    {
        "pid": "p01",
        "seed": 1382257276,
        "bpm": 136.0,
        "prompt_core": "psychedelic trance, 136 bpm, bubbling acid line, pulsating sub bass, tight kick and hi-hats, mystical",
        "prompt_ext": "psychedelic trance, 136 bpm, bubbling acid line, pulsating sub bass, tight kick and hi-hats, mystical, goa trance, TB-303 resonance"
    },
    {
        "pid": "p02",
        "seed": 729796532,
        "bpm": 125.0,
        "prompt_core": "high-energy psytrance, driving classic goa trance, polished production, 125 bpm, E-flat major, lush jazzy lift",
        "prompt_ext": "high-energy psytrance, driving classic goa trance, polished production, 125 bpm, E-flat major, analog lead, cosmic mood"
    },
    {
        "pid": "p03",
        "seed": 158725066,
        "bpm": 132.0,
        "prompt_core": "2020s tech trance, trance, space mood, 132 bpm",
        "prompt_ext": "2020s tech trance, trance, space mood, 132 bpm, goa trance, euphoric mood"
    },
    {
        "pid": "p04",
        "seed": 782949196,
        "bpm": 151.0,
        "prompt_core": "mid 90s goa trance, melodic mood, 151 bpm",
        "prompt_ext": "mid 90s goa trance, melodic mood, 151 bpm, hypnotic arpeggio, uplifting mood"
    },
    {
        "pid": "p05",
        "seed": 1262357892,
        "bpm": 110.0,
        "prompt_core": "mid 90s goa trance, ambient, space soundscape mood, 110 bpm",
        "prompt_ext": "mid 90s goa trance, ambient, space soundscape mood, 110 bpm, mystical pads, deep meditation"
    },
    {
        "pid": "p06",
        "seed": 451991434,
        "bpm": 102.0,
        "prompt_core": "early 90s downtempo, ambient, meditative soundscape mood, 102 bpm",
        "prompt_ext": "early 90s downtempo, ambient, meditative soundscape mood, 102 bpm, goa trance, lush synth"
    },
    {
        "pid": "p07",
        "seed": 1391676905,
        "bpm": 145.0,
        "prompt_core": "early 2000s goa trance, melodic dark mood, 145 bpm",
        "prompt_ext": "early 2000s goa trance, melodic dark mood, 145 bpm, driving acid lead, energetic mood"
    },
    {
        "pid": "p08",
        "seed": 1126148435,
        "bpm": 150.0,
        "prompt_core": "hi-tech psytrance, 150 bpm, soaring synth lead, rolling bassline, intricate percussion patterns, dark and hypnotic",
        "prompt_ext": "hi-tech psytrance, 150 bpm, soaring synth lead, rolling bassline, intricate percussion patterns, dark and hypnotic, goa trance, psychedelic mood"
    },
    {
        "pid": "p09",
        "seed": 1403519739,
        "bpm": 147.0,
        "prompt_core": "late 90s goa trance, 147 bpm",
        "prompt_ext": "late 90s goa trance, 147 bpm, melodic lead, euphoric mood"
    }
]

def find_div4_crop(audio, sr, min_start_sec, target_bars=12, bpm=145.0):
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
    print("=== Loading Full-FT ep80 Backbone Model ===", flush=True)
    t_start = time.time()
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    load_fullft(model, CKPT, weights="online")
    print(f"Model ready in {time.time() - t_start:.1f}s\n", flush=True)

    manifest_path = f"{OUT_DIR}/cells_islands.jsonl"
    manifest_entries = []

    for idx, trk in enumerate(TRACKS):
        pid = trk["pid"]
        seed = trk["seed"]
        bpm = trk["bpm"]
        p_core = trk["prompt_core"]
        p_ext = trk["prompt_ext"]
        t_track_start = time.time()

        print(f"[{idx+1}/10] Processing {pid} (BPM={bpm}, Seed={seed})...", flush=True)

        # 1. 90-Second Parent Render
        path_parent = f"{OUT_DIR}/{pid}_parent_90s.wav"
        if not os.path.exists(path_parent):
            t0 = time.time()
            out_90 = model.generate(prompt=p_core, duration=90.0, steps=STEPS, cfg_scale=CFG, seed=seed, batch_size=1)
            raw_90 = out_90[0].float().cpu().numpy()
            save_audio(path_parent, torch.tensor(raw_90), SR)
            print(f"  Rendered 90s parent in {time.time() - t0:.1f}s", flush=True)
        else:
            raw_90, _ = sf.read(path_parent)
            raw_90 = raw_90.T if raw_90.ndim == 2 and raw_90.shape[0] > raw_90.shape[1] else raw_90
            print(f"  Loaded existing 90s parent: {path_parent}", flush=True)

        # 2. Extract Islands A and B (12 bars each)
        crop_a, dur_a, s_a, e_a = find_div4_crop(raw_90, SR, min_start_sec=2.0, target_bars=12, bpm=bpm)
        crop_b, dur_b, s_b, e_b = find_div4_crop(raw_90, SR, min_start_sec=50.0, target_bars=12, bpm=bpm)

        path_core = f"{OUT_DIR}/{pid}_core.wav"
        save_audio(path_core, torch.tensor(crop_a), SR)

        # 4 bars gap at BPM = 16 beats
        gap_sec = 16.0 * (60.0 / bpm)
        n_gap = int(round(gap_sec * SR))
        n_a = crop_a.shape[-1]
        n_b = crop_b.shape[-1]
        total_samples = n_a + n_gap + n_b
        total_dur = total_samples / SR
        gap_start = n_a / SR
        gap_end = (n_a + n_gap) / SR

        print(f"  Island A: {dur_a:.2f}s | Gap: {gap_sec:.2f}s (16 beats) | Island B: {dur_b:.2f}s | Total: {total_dur:.2f}s", flush=True)

        # ------------------------------------------------------------------
        # Mode A: Direct 4-Bar Inpaint Bridge
        # ------------------------------------------------------------------
        id_mode_a = f"{pid}_islands_4bar_direct"
        path_mode_a = f"{OUT_DIR}/{id_mode_a}.wav"
        if not os.path.exists(path_mode_a):
            t0 = time.time()
            canvas_a = np.zeros((crop_a.shape[0], total_samples), dtype=np.float32)
            canvas_a[:, :n_a] = crop_a
            canvas_a[:, n_a + n_gap : n_a + n_gap + crop_b.shape[-1]] = crop_b

            out_bridge_a = model.generate(
                prompt=p_ext, duration=total_dur, steps=STEPS, cfg_scale=CFG, seed=seed + 77,
                inpaint_audio=(SR, torch.tensor(canvas_a)),
                inpaint_mask_start_seconds=gap_start,
                inpaint_mask_end_seconds=gap_end,
                batch_size=1
            )
            wav_bridge_a = out_bridge_a[0].float().cpu().numpy()
            save_audio(path_mode_a, torch.tensor(wav_bridge_a), SR)
            print(f"  Mode A (Direct Bridge) rendered in {time.time() - t0:.1f}s", flush=True)

        # ------------------------------------------------------------------
        # Mode B: A2A (0.60 noised) Island B + 4-Bar Inpaint Bridge
        # ------------------------------------------------------------------
        id_mode_b = f"{pid}_islands_a2a_060_bridge"
        path_mode_b = f"{OUT_DIR}/{id_mode_b}.wav"
        if not os.path.exists(path_mode_b):
            t0 = time.time()
            # Step 1: A2A restyle of Island B at noise level 0.60
            out_a2a_b = model.generate(
                prompt=p_ext, duration=dur_b, steps=STEPS, cfg_scale=CFG, seed=seed + 88,
                init_audio=(SR, torch.tensor(crop_b)),
                init_noise_level=0.60,
                batch_size=1
            )
            crop_b_a2a = out_a2a_b[0].float().cpu().numpy()[:, :n_b]

            # Step 2: Inpaint bridge between Island A and A2A Island B
            canvas_b = np.zeros((crop_a.shape[0], total_samples), dtype=np.float32)
            canvas_b[:, :n_a] = crop_a
            n_b_actual = min(crop_b_a2a.shape[-1], n_b)
            canvas_b[:, n_a + n_gap : n_a + n_gap + n_b_actual] = crop_b_a2a[:, :n_b_actual]

            out_bridge_b = model.generate(
                prompt=p_ext, duration=total_dur, steps=STEPS, cfg_scale=CFG, seed=seed + 99,
                inpaint_audio=(SR, torch.tensor(canvas_b)),
                inpaint_mask_start_seconds=gap_start,
                inpaint_mask_end_seconds=gap_end,
                batch_size=1
            )
            wav_bridge_b = out_bridge_b[0].float().cpu().numpy()
            save_audio(path_mode_b, torch.tensor(wav_bridge_b), SR)
            print(f"  Mode B (A2A + Bridge) rendered in {time.time() - t0:.1f}s", flush=True)

        # Encode AACs
        encode_aac(path_parent, f"{AAC_DIR}/{pid}_parent_90s.m4a")
        encode_aac(path_core, f"{AAC_DIR}/{pid}_core.m4a")
        encode_aac(path_mode_a, f"{AAC_DIR}/{id_mode_a}.m4a")
        encode_aac(path_mode_b, f"{AAC_DIR}/{id_mode_b}.m4a")

        # Record manifest entries
        manifest_entries.append({
            "id": id_mode_a,
            "pid": pid,
            "prompt_core": p_core,
            "prompt_ext": p_ext,
            "mode": "4bar_direct",
            "seed": seed,
            "bpm": bpm,
            "dur": total_dur,
            "dur_a": dur_a,
            "dur_gap": gap_sec,
            "dur_b": dur_b,
            "gap_start": gap_start,
            "gap_end": gap_end
        })
        manifest_entries.append({
            "id": id_mode_b,
            "pid": pid,
            "prompt_core": p_core,
            "prompt_ext": p_ext,
            "mode": "a2a_060_bridge",
            "seed": seed,
            "bpm": bpm,
            "dur": total_dur,
            "dur_a": dur_a,
            "dur_gap": gap_sec,
            "dur_b": dur_b,
            "gap_start": gap_start,
            "gap_end": gap_end
        })
        print(f"  -> Track {pid} complete in {time.time() - t_track_start:.1f}s\n", flush=True)

    with open(manifest_path, "w") as f:
        for entry in manifest_entries:
            f.write(json.dumps(entry) + "\n")

    print(f"=== All 10 Tracks Complete! Wrote manifest to {manifest_path} ===", flush=True)

if __name__ == "__main__":
    main()
    import os
    os._exit(0)
