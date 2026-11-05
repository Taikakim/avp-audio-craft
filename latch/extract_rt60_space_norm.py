#!/usr/bin/env python3
"""extract_rt60_space_norm.py -- Extract Audio Commons RT60 reverb activations across the Goa corpus
and compute de-coupled Space Mood targets (S_norm) normalized against reverberation time/probability.

For all 5,401 crops in /run/media/kim/Kosmos/latents/latents_sa3/:
1. Reads audio slice from source_path at seconds_start (20.0s).
2. Computes RT60 and logistic regression soft probability using timbral_models.timbral_reverb(dev_output=True).
3. Reads 'space' mood time-series from /run/media/kim/Mantu/latents_sa3_mood/{stem}.npy (tag index 49).
4. Fits global regression S = alpha * P_reverb + beta.
5. Saves de-coupled space target S_norm(t) = S_space(t) - (alpha * P_reverb + beta) to /run/media/kim/Mantu/latents_sa3_space_norm/.
6. Writes comprehensive summary census.json.
"""
import os
import sys
import glob
import time
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import soundfile as sf

sys.path.insert(0, "/home/kim/Projects/mir/repos/timbral_models")
import timbral_models

LATENT_DIR = Path("/run/media/kim/Kosmos/latents/latents_sa3")
MOOD_DIR = Path("/run/media/kim/Mantu/latents_sa3_mood")
OUT_DIR = Path("/run/media/kim/Mantu/latents_sa3_space_norm")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SR = 44100
DUR = 20.0
FRAMES = int(DUR * SR)
SPACE_TAG_IDX = 49  # 'space' in mtg_jamendo_moodtheme-discogs-effnet-1.json

def process_single_crop(json_path):
    stem = Path(json_path).stem
    mood_file = MOOD_DIR / f"{stem}.npy"
    if not mood_file.exists():
        return None
    try:
        with open(json_path) as f:
            meta = json.load(f)
        flac_path = meta.get("source_path")
        if not flac_path or not os.path.exists(flac_path):
            return None
        start_sec = float(meta.get("seconds_start", 0.0))
        audio, fs = sf.read(flac_path, start=int(start_sec * SR), frames=FRAMES)
        rt60, prob = timbral_models.timbral_reverb(audio, fs=fs, dev_output=True)
        mood_arr = np.load(mood_file)
        space_ts = mood_arr[SPACE_TAG_IDX]
        space_mean = float(np.mean(space_ts))
        return {
            "stem": stem,
            "rt60": float(rt60),
            "reverb_prob": float(prob),
            "space_mean": space_mean,
            "space_ts": space_ts.astype(np.float32)
        }
    except Exception as e:
        return None

def main():
    print(f"=== Scanning crops in {LATENT_DIR} ===", flush=True)
    all_jsons = sorted(glob.glob(str(LATENT_DIR / "*.json")))
    print(f"Found {len(all_jsons)} candidate crops.", flush=True)
    
    t0 = time.time()
    results = []
    max_workers = min(20, os.cpu_count() or 4)
    print(f"Extracting RT60 & space mood with {max_workers} CPU workers...", flush=True)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_single_crop, p): p for p in all_jsons}
        done_cnt = 0
        total = len(futures)
        for fut in as_completed(futures):
            res = fut.result()
            if res is not None:
                results.append(res)
            done_cnt += 1
            if done_cnt % 500 == 0 or done_cnt == total:
                elapsed = time.time() - t0
                rate = done_cnt / max(1.0, elapsed)
                rem = (total - done_cnt) / max(0.01, rate)
                print(f"  [{done_cnt}/{total}] ({done_cnt/total*100:.1f}%) | "
                      f"Valid crops: {len(results)} | Rate: {rate:.1f} crops/s | "
                      f"ETA: {rem/60:.1f}m", flush=True)

    print(f"\nExtraction complete! Processed {len(results)} valid crops in {time.time() - t0:.1f}s.", flush=True)
    if not results:
        print("No valid crops processed!")
        sys.exit(1)

    # 1. Compute global regression statistics
    s = np.array([r["space_mean"] for r in results])
    p = np.array([r["reverb_prob"] for r in results])
    rt = np.array([r["rt60"] for r in results])

    # Linear fit: space = alpha * prob + beta
    cov_sp = np.cov(s, p)[0, 1]
    var_p = np.var(p)
    alpha = float(cov_sp / max(1e-8, var_p))
    beta = float(np.mean(s) - alpha * np.mean(p))
    corr_p = float(np.corrcoef(s, p)[0, 1])
    corr_rt = float(np.corrcoef(s, rt)[0, 1])

    print("\n=== Corpus Global Statistics ===")
    print(f"Total Valid Crops: {len(results)}")
    print(f"Space Mood Mean:   {np.mean(s):.4f} +/- {np.std(s):.4f} (range [{np.min(s):.4f}, {np.max(s):.4f}])")
    print(f"Reverb Prob Mean:  {np.mean(p):.4f} +/- {np.std(p):.4f} (range [{np.min(p):.4f}, {np.max(p):.4f}])")
    print(f"RT60 (s) Mean:     {np.mean(rt):.4f} +/- {np.std(rt):.4f} (range [{np.min(rt):.4f}, {np.max(rt):.4f}])")
    print(f"Correlation (Space vs Reverb Prob): r = {corr_p:.3f} (R^2 = {corr_p**2:.3f})")
    print(f"Correlation (Space vs RT60 sec):    r = {corr_rt:.3f} (R^2 = {corr_rt**2:.3f})")
    print(f"Fitted De-coupling: S_pred = {alpha:.4f} * P_reverb + {beta:.4f}")

    # 2. Compute residual S_norm and save control arrays
    print(f"\nSaving normalized targets to {OUT_DIR}...", flush=True)
    saved_cnt = 0
    s_norm_means = []

    for r in results:
        stem = r["stem"]
        p_val = r["reverb_prob"]
        raw_ts = r["space_ts"]
        
        # De-coupled space: residual over time
        # Baseline expected space purely from reverb:
        s_base = alpha * p_val + beta
        s_norm_ts = raw_ts - s_base
        s_norm_mean = float(np.mean(s_norm_ts))
        s_norm_means.append(s_norm_mean)
        
        # Pack 2-channel control array: ch0 = S_norm(t), ch1 = P_reverb(t)
        # Reverb prob is static over the crop, expanded to 280 frames
        ctrl_2ch = np.zeros((2, len(raw_ts)), dtype=np.float32)
        ctrl_2ch[0] = s_norm_ts
        ctrl_2ch[1] = np.full(len(raw_ts), p_val, dtype=np.float32)
        
        np.save(OUT_DIR / f"{stem}.npy", ctrl_2ch)
        saved_cnt += 1

    s_norm_arr = np.array(s_norm_means)
    print(f"Saved {saved_cnt} .npy control files.")
    print(f"S_norm Mean: {s_norm_arr.mean():.4f} +/- {s_norm_arr.std():.4f} (zero-centered residual)")

    # 3. Write summary census.json
    summary = {
        "n_crops": len(results),
        "alpha": alpha,
        "beta": beta,
        "corr_space_reverb_prob": corr_p,
        "corr_space_rt60": corr_rt,
        "space_mean": float(np.mean(s)),
        "space_std": float(np.std(s)),
        "reverb_prob_mean": float(np.mean(p)),
        "reverb_prob_std": float(np.std(p)),
        "rt60_mean": float(np.mean(rt)),
        "rt60_std": float(np.std(rt)),
        "s_norm_std": float(s_norm_arr.std()),
        "description": "2-channel control pack: ch0 = de-coupled space mood S_norm(t), ch1 = Audio Commons reverb probability P_reverb"
    }
    with open(OUT_DIR / "census_space_norm.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Summary saved to {OUT_DIR / 'census_space_norm.json'}")
    print("ALL DONE!", flush=True)

if __name__ == "__main__":
    main()
