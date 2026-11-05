#!/usr/bin/env python3
"""test_4bar_inpaint_bridge.py -- A/B test of Beat-Quantized 4-Bar Inpainting vs Unsynced Seam Inpainting.
Tests on prompt p00 (145 bpm) using Full-FT ep80 at CFG 10.0, 24 steps.
Prompts use max 2 extension terms with 'goa trance' and moods.
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

def extract_downbeat_crop(audio, sr, min_sec=16.0, max_sec=24.0):
    mono = audio.mean(axis=0)
    db = np.array(madmom_downbeats(audio, sr))
    valid_starts = [t for t in db if t >= 1.5]
    start_t = valid_starts[0] if valid_starts else db[0]
    start_idx = np.where(db == start_t)[0][0]
    
    # End on downbeat that is a multiple of 4 bars from start
    ends = [db[i] for i in range(start_idx + 4, len(db), 4) if min_sec <= (db[i] - start_t) <= max_sec]
    end_t = ends[-1] if ends else [t for t in db if t > start_t + min_sec][0]
    
    s_samp = find_zero_crossing_backwards(mono, int(start_t * sr), search_window=int(0.05 * sr))
    e_samp = find_zero_crossing_backwards(mono, int(end_t * sr), search_window=int(0.05 * sr))
    
    crop = audio[:, s_samp:e_samp]
    return crop, (e_samp - s_samp) / sr

def main():
    print("=== Loading Full-FT ep80 Model ===")
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    load_fullft(model, CKPT, weights="online")
    
    print("=== Step 1: Rendering Clip A (Core Prompt) ===")
    out_a = model.generate(prompt=PROMPT_CORE, duration=28.0, steps=STEPS, cfg_scale=CFG, seed=SEED, batch_size=1)
    raw_a = out_a[0].float().cpu().numpy()
    crop_a, dur_a = extract_downbeat_crop(raw_a, SR, min_sec=18.0, max_sec=22.0)
    print(f"  Clip A: {dur_a:.2f}s, ends on clean downbeat boundary")
    
    print("=== Step 2: Rendering Clip B (Extended Prompt: Max 2 terms) ===")
    out_b = model.generate(prompt=PROMPT_EXT, duration=28.0, steps=STEPS, cfg_scale=CFG, seed=SEED+10, batch_size=1)
    raw_b = out_b[0].float().cpu().numpy()
    crop_b, dur_b = extract_downbeat_crop(raw_b, SR, min_sec=18.0, max_sec=22.0)
    print(f"  Clip B: {dur_b:.2f}s, starts on clean downbeat boundary")
    
    # 4 bars at 145 BPM = 16 beats = 16 * 60 / 145 = 6.620689655s
    bars = 4
    beats = bars * 4
    sec_per_beat = 60.0 / BPM
    exact_gap_sec = beats * sec_per_beat
    n_gap_exact = int(round(exact_gap_sec * SR))
    
    # Unsynced gap: arbitrary length (e.g. 5.17s) that breaks the beat grid
    unsynced_gap_sec = 5.17
    n_gap_unsynced = int(round(unsynced_gap_sec * SR))
    
    print(f"=== Rendering Variant B: Beat-Quantized 4-Bar Inpaint Bridge ({exact_gap_sec:.3f}s gap) ===")
    n_a = crop_a.shape[-1]
    n_b = crop_b.shape[-1]
    total_samples_quant = n_a + n_gap_exact + n_b
    z_quant = np.zeros((crop_a.shape[0], total_samples_quant), dtype=np.float32)
    z_quant[:, :n_a] = crop_a
    z_quant[:, n_a + n_gap_exact : total_samples_quant] = crop_b
    total_dur_quant = total_samples_quant / SR
    
    gap_start_sec = n_a / SR
    gap_end_sec = (n_a + n_gap_exact) / SR
    
    # Inpaint the 4-bar bridge
    inpaint_prompt = f"{PROMPT_CORE}, continuing groove into {PROMPT_EXT}"
    out_quant = model.generate(
        prompt=PROMPT_EXT, duration=total_dur_quant, steps=STEPS, cfg_scale=CFG, seed=SEED+42,
        inpaint_audio=(SR, torch.tensor(z_quant)),
        inpaint_mask_start_seconds=gap_start_sec,
        inpaint_mask_end_seconds=gap_end_sec,
        batch_size=1
    )
    wav_quant = out_quant[0].float().cpu().numpy()
    path_quant = f"{OUT_DIR}/test_p00_quantized_4bar_inpaint.wav"
    save_audio(path_quant, torch.tensor(wav_quant), SR)
    print(f"  -> Saved {path_quant} (Dur: {total_dur_quant:.2f}s, gap: {gap_start_sec:.2f}s - {gap_end_sec:.2f}s)")
    
    print(f"=== Rendering Variant A: Unsynced Gap Inpaint ({unsynced_gap_sec:.3f}s gap) ===")
    total_samples_unsync = n_a + n_gap_unsynced + n_b
    z_unsync = np.zeros((crop_a.shape[0], total_samples_unsync), dtype=np.float32)
    z_unsync[:, :n_a] = crop_a
    z_unsync[:, n_a + n_gap_unsynced : total_samples_unsync] = crop_b
    total_dur_unsync = total_samples_unsync / SR
    
    unsync_start_sec = n_a / SR
    unsync_end_sec = (n_a + n_gap_unsynced) / SR
    
    out_unsync = model.generate(
        prompt=PROMPT_EXT, duration=total_dur_unsync, steps=STEPS, cfg_scale=CFG, seed=SEED+42,
        inpaint_audio=(SR, torch.tensor(z_unsync)),
        inpaint_mask_start_seconds=unsync_start_sec,
        inpaint_mask_end_seconds=unsync_end_sec,
        batch_size=1
    )
    wav_unsync = out_unsync[0].float().cpu().numpy()
    path_unsync = f"{OUT_DIR}/test_p00_unsynced_gap_inpaint.wav"
    save_audio(path_unsync, torch.tensor(wav_unsync), SR)
    print(f"  -> Saved {path_unsync} (Dur: {total_dur_unsync:.2f}s, gap: {unsync_start_sec:.2f}s - {unsync_end_sec:.2f}s)")
    
    print("=== A/B Render Complete! ===")

if __name__ == "__main__":
    main()
