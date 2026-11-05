#!/usr/bin/env python3
"""test_v3_outpaint.py -- test beat-aware steady crop and two-pass outpainting on 1 clip."""
import os, sys, time
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import numpy as np, soundfile as sf, torch
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
from forge.fullft import load_fullft
from stable_audio_3 import StableAudioModel
from dj_beatmatch import madmom_downbeats
sys.path.insert(0, "/home/kim/Projects/mir/src/tools")
from create_training_crops import find_zero_crossing_backwards

SR = 44100
RUNS = "/run/media/kim/Mantu/sa3_lora_runs"

def extract_steady_crop(audio, sr):
    mono = audio.mean(axis=0)
    hop = int(0.25 * sr)
    rms = [np.sqrt(np.mean(mono[i:i+hop]**2)) for i in range(0, len(mono)-hop, hop)]
    times = [i / sr for i in range(0, len(mono)-hop, hop)]
    mid_rms = np.median([r for t, r in zip(times, rms) if 4.0 <= t <= 20.0])
    
    # Locate fadeout start
    fadeout_time = audio.shape[-1] / sr
    for t, r in zip(times, rms):
        if t > 18.0 and r < 0.65 * mid_rms:
            fadeout_time = t
            break
            
    db = np.array(madmom_downbeats(audio, sr))
    valid_starts = [t for t in db if t >= 1.5]
    start_t = valid_starts[0] if valid_starts else db[0]
    start_idx = np.where(db == start_t)[0][0]
    
    valid_ends = [db[i] for i in range(start_idx + 4, len(db), 4) if db[i] < (fadeout_time - 0.2)]
    if valid_ends:
        end_t = valid_ends[-1]
    else:
        # Fallback to any downbeat before fadeout
        earlier = [t for t in db if start_t + 5.0 <= t < (fadeout_time - 0.2)]
        end_t = earlier[-1] if earlier else (fadeout_time - 0.5)
        
    s_samp = find_zero_crossing_backwards(mono, int(start_t * sr), search_window=int(0.05 * sr))
    e_samp = find_zero_crossing_backwards(mono, int(end_t * sr), search_window=int(0.05 * sr))
    
    crop = audio[:, s_samp:e_samp]
    dur = crop.shape[-1] / sr
    print(f"[steady_crop] Extracted {dur:.2f}s ({s_samp/sr:.2f}s -> {e_samp/sr:.2f}s), fadeout was at {fadeout_time:.2f}s")
    return crop, dur

def test():
    print("Loading model...")
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    fullft_ckpt = f"{RUNS}/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt"
    load_fullft(model, fullft_ckpt, weights="ema")
    
    prompt = "2020s goa trance, space retro mood, 143 bpm"
    prompt_enriched = "2020s goa trance, space retro mood, 143 bpm, Roland SH-101 portamento lead, legato bittersweet synth melody a fifth above the fundamental, lush vintage chorus, punchy analog kick, cosmic resonant sweeps"
    
    # 1. Generate 30s core
    print("Generating core...")
    t0 = time.time()
    out = model.generate(prompt=prompt, duration=30.0, steps=24, cfg_scale=10.0, seed=12345, batch_size=1)
    core_raw = out[0].float().cpu().numpy()
    print(f"Core generated in {time.time()-t0:.1f}s")
    
    # 2. Extract steady crop
    crop, crop_dur = extract_steady_crop(core_raw, SR)
    
    # 3. Test Pass 1: Latter Outpaint (Extend forward by 25s)
    D_post = 25.0
    W1 = crop_dur + D_post
    z1 = np.zeros((crop.shape[0], int(W1 * SR)), dtype=np.float32)
    z1[:, :crop.shape[-1]] = crop
    
    print(f"Pass 1: Latter outpaint to {W1:.2f}s with enriched prompt...")
    t1 = time.time()
    out_fwd = model.generate(prompt=prompt_enriched, duration=W1, steps=24, cfg_scale=10.0, seed=12346,
                             inpaint_audio=(SR, torch.tensor(z1)),
                             inpaint_mask_start_seconds=crop_dur, inpaint_mask_end_seconds=W1,
                             batch_size=1)
    fwd = out_fwd[0].float().cpu().numpy()
    fwd = np.pad(fwd, ((0, 0), (0, max(0, int(W1 * SR) - fwd.shape[-1]))))[:, :int(W1 * SR)]
    print(f"Pass 1 generated in {time.time()-t1:.1f}s")
    
    # 4. Test Pass 2: Preceding Outpaint (Extend backward by 25s)
    D_pre = 25.0
    W2 = D_pre + W1
    z2 = np.zeros((crop.shape[0], int(W2 * SR)), dtype=np.float32)
    z2[:, int(D_pre * SR):] = fwd
    
    print(f"Pass 2: Preceding outpaint to {W2:.2f}s with enriched prompt...")
    t2 = time.time()
    out_full = model.generate(prompt=prompt_enriched, duration=W2, steps=24, cfg_scale=10.0, seed=12347,
                              inpaint_audio=(SR, torch.tensor(z2)),
                              inpaint_mask_start_seconds=0.0, inpaint_mask_end_seconds=D_pre,
                              batch_size=1)
    full = out_full[0].float().cpu().numpy()
    full = np.pad(full, ((0, 0), (0, max(0, int(W2 * SR) - full.shape[-1]))))[:, :int(W2 * SR)]
    print(f"Pass 2 generated in {time.time()-t2:.1f}s")
    
    out_path = "/tmp/test_v3_outpaint.wav"
    sf.write(out_path, full.T, SR)
    print(f"Saved test output to {out_path} (shape: {full.shape}, dur: {full.shape[-1]/SR:.2f}s)")
    os._exit(0)

if __name__ == "__main__":
    test()
