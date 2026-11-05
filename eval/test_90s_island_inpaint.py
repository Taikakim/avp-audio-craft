#!/usr/bin/env python3
"""test_90s_island_inpaint.py -- Two clean div4 blocks from a 90s parent render with 4-bar inpaint bridge.
Also tests Variant 2: A2A (0.60 noising) on the downstream block before inpainting.
"""
import os
import sys
import time
import json
import torch
import numpy as np
import soundfile as sf

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

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
OUT_DIR = "/run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_v3/ab_tests"
os.makedirs(OUT_DIR, exist_ok=True)

CKPT = "/run/media/kim/Mantu/sa3_lora_runs/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt"
BPM = 145.0
PROMPT_CORE = "mid 90s goa trance, melodic mood, 145 bpm"
PROMPT_EXT = "mid 90s goa trance, 145 bpm, Roland SH-101 lead, euphoric mood" # Max 2 terms!
SEED = 20261104
CFG = 10.0
STEPS = 24

def find_div4_crop(audio, sr, min_start_sec, target_bars=12, bpm=145.0):
    mono = audio.mean(axis=0)
    db = np.array(madmom_downbeats(audio, sr))
    
    # Filter for starts after min_start_sec
    valid_starts = [t for t in db if t >= min_start_sec]
    start_t = valid_starts[0] if valid_starts else db[0]
    start_idx = np.where(db == start_t)[0][0]
    
    # Find an end downbeat exactly target_bars away
    target_idx = start_idx + target_bars
    if target_idx < len(db):
        end_t = db[target_idx]
    else:
        # Fallback to calculated duration
        sec_per_bar = (60.0 / bpm) * 4.0
        end_t = start_t + target_bars * sec_per_bar
        
    s_samp = find_zero_crossing_backwards(mono, int(start_t * sr), search_window=int(0.05 * sr))
    e_samp = find_zero_crossing_backwards(mono, int(end_t * sr), search_window=int(0.05 * sr))
    
    crop = audio[:, s_samp:e_samp]
    dur = (e_samp - s_samp) / sr
    return crop, dur, s_samp / sr, e_samp / sr

def main():
    print("=== Loading Full-FT ep80 Model ===")
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    load_fullft(model, CKPT, weights="online")
    
    print("\n=== Step 1: Rendering Full 90-Second Parent Track ===")
    t0 = time.time()
    out_90 = model.generate(prompt=PROMPT_CORE, duration=90.0, steps=STEPS, cfg_scale=CFG, seed=SEED, batch_size=1)
    raw_90 = out_90[0].float().cpu().numpy()
    print(f"  Rendered 90s in {time.time() - t0:.1f}s")
    
    # Save parent track
    path_parent = f"{OUT_DIR}/test_p00_parent_90s.wav"
    save_audio(path_parent, torch.tensor(raw_90), SR)
    
    print("\n=== Step 2: Extracting Two Clean div4 Islands ===")
    # Island A: 12 bars (~19.86s) from the early section
    crop_a, dur_a, s_a, e_a = find_div4_crop(raw_90, SR, min_start_sec=2.0, target_bars=12, bpm=BPM)
    print(f"  Island A (Core): {dur_a:.2f}s ({s_a:.2f}s -> {e_a:.2f}s, 12 bars)")
    
    # Island B: 12 bars (~19.86s) from downstream section (after 50s)
    crop_b, dur_b, s_b, e_b = find_div4_crop(raw_90, SR, min_start_sec=52.0, target_bars=12, bpm=BPM)
    print(f"  Island B (Later): {dur_b:.2f}s ({s_b:.2f}s -> {e_b:.2f}s, 12 bars)")
    
    # 4 bars gap at 145 BPM = 16 beats = 6.620689s
    gap_bars = 4
    beats_gap = gap_bars * 4
    gap_sec = beats_gap * (60.0 / BPM)
    n_gap = int(round(gap_sec * SR))
    n_a = crop_a.shape[-1]
    n_b = crop_b.shape[-1]
    
    # ----------------------------------------------------
    # Workflow 1: Direct 4-Bar Inpaint Bridge
    # ----------------------------------------------------
    print(f"\n=== Workflow 1: Direct 4-Bar Inpaint Bridge ({gap_sec:.3f}s gap) ===")
    total_samples = n_a + n_gap + n_b
    total_dur = total_samples / SR
    canvas1 = np.zeros((crop_a.shape[0], total_samples), dtype=np.float32)
    canvas1[:, :n_a] = crop_a
    canvas1[:, n_a + n_gap : total_samples] = crop_b
    
    gap_start = n_a / SR
    gap_end = (n_a + n_gap) / SR
    
    out_bridge1 = model.generate(
        prompt=PROMPT_EXT, duration=total_dur, steps=STEPS, cfg_scale=CFG, seed=SEED + 77,
        inpaint_audio=(SR, torch.tensor(canvas1)),
        inpaint_mask_start_seconds=gap_start,
        inpaint_mask_end_seconds=gap_end,
        batch_size=1
    )
    wav_bridge1 = out_bridge1[0].float().cpu().numpy()
    path_wf1 = f"{OUT_DIR}/test_90s_islands_4bar_inpaint.wav"
    save_audio(path_wf1, torch.tensor(wav_bridge1), SR)
    print(f"  -> Saved {path_wf1} (Dur: {total_dur:.2f}s, gap: {gap_start:.2f}s - {gap_end:.2f}s)")
    
    # ----------------------------------------------------
    # Workflow 2: A2A (0.60 noising) on Island B + 4-Bar Bridge
    # ----------------------------------------------------
    print(f"\n=== Workflow 2: A2A (0.60 noising) on Island B + Inpaint Bridge ===")
    # Step 2a: Run A2A on Island B with PROMPT_EXT at init_noise_level = 0.60
    out_a2a_b = model.generate(
        prompt=PROMPT_EXT, duration=dur_b, steps=STEPS, cfg_scale=CFG, seed=SEED + 88,
        init_audio=(SR, torch.tensor(crop_b)),
        init_noise_level=0.60,
        batch_size=1
    )
    crop_b_a2a = out_a2a_b[0].float().cpu().numpy()[:, :n_b]
    path_b_a2a = f"{OUT_DIR}/test_island_b_a2a_060.wav"
    save_audio(path_b_a2a, torch.tensor(crop_b_a2a), SR)
    print(f"  -> Island B re-styled via A2A (0.60 noise): {crop_b_a2a.shape[-1]/SR:.2f}s")
    
    # Step 2b: Canvas with Island A + gap + Island B (A2A)
    canvas2 = np.zeros((crop_a.shape[0], total_samples), dtype=np.float32)
    canvas2[:, :n_a] = crop_a
    canvas2[:, n_a + n_gap : total_samples] = crop_b_a2a
    
    out_bridge2 = model.generate(
        prompt=PROMPT_EXT, duration=total_dur, steps=STEPS, cfg_scale=CFG, seed=SEED + 99,
        inpaint_audio=(SR, torch.tensor(canvas2)),
        inpaint_mask_start_seconds=gap_start,
        inpaint_mask_end_seconds=gap_end,
        batch_size=1
    )
    wav_bridge2 = out_bridge2[0].float().cpu().numpy()
    path_wf2 = f"{OUT_DIR}/test_90s_islands_a2a_060_bridge.wav"
    save_audio(path_wf2, torch.tensor(wav_bridge2), SR)
    print(f"  -> Saved {path_wf2} (Dur: {total_dur:.2f}s)")
    
    print("\n=== All Tests Successfully Completed! ===")

if __name__ == "__main__":
    main()
