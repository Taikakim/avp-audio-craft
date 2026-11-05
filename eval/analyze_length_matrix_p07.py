#!/usr/bin/env python3
"""
analyze_length_matrix_p07.py — Quantitative DSP, Timbral, and Aesthetic Analysis
across Sequence Lengths (256 to 4096 frames) for P07.

Measures:
- Audiobox Aesthetics: PQ (Production Quality), CE (Content Enjoyment), CU, PC
- Stereo Imaging: Width mean/std, L/R Phase Correlation
- Spatial/Reverb: RT60 Reverb Time (seconds) & Reverb Probability
- Spectral Disintegration: Whitening (Spectral Flatness), HF Ratio (>6 kHz), ZCR
- Dynamics/Rhythm: Onset Density (onsets/sec), Spectral Centroid Mean/Std
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa

# Setup paths for mir tools
sys.path.insert(0, "/home/kim/Projects/mir/src")
sys.path.insert(0, "/home/kim/Projects/SAO/eval")

from disintegration_metrics import measure as measure_dsp
from width_metric import width_stats
import timbral_models

try:
    from timbral.audiobox_aesthetics import analyze_audiobox_aesthetics
    AUDIOBOX_OK = True
except ImportError:
    AUDIOBOX_OK = False

def analyze_clip(wav_path, run_audiobox=True):
    path = Path(wav_path)
    res = {"filename": path.name}
    
    # 1. DSP Disintegration & Whitening
    dsp = measure_dsp(path)
    res["onsets_per_sec"] = round(dsp["onsets"], 3)
    res["spectral_flatness"] = round(dsp["flatness"], 5)
    res["zcr"] = round(dsp["zcr"], 5)
    res["hf_ratio_gt_6khz"] = round(dsp["hf"], 4)

    # 2. Spectral Centroid
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    sc = librosa.feature.spectral_centroid(y=y, sr=sr)
    res["spectral_centroid_mean"] = round(float(np.mean(sc)), 1)
    res["spectral_centroid_std"] = round(float(np.std(sc)), 1)

    # 3. Stereo Width & Correlation
    w_stats = width_stats(str(path))
    res["stereo_width_mean"] = w_stats.get("width_mean", None)
    res["stereo_width_std"] = w_stats.get("width_std", None)
    res["stereo_corr_mean"] = w_stats.get("corr_mean", None)

    # 4. RT60 Reverb
    try:
        rt60, prob = timbral_models.timbral_reverb(str(path), dev_output=True)
        res["rt60_s"] = round(float(rt60), 3)
        res["reverb_prob"] = round(float(prob), 3)
    except Exception as e:
        res["rt60_s"] = None
        res["reverb_prob"] = None

    # 5. Audiobox Aesthetics
    if run_audiobox and AUDIOBOX_OK:
        try:
            aes = analyze_audiobox_aesthetics(str(path))
            res["audiobox_pq"] = round(float(aes.get("production_quality", 0)), 3)
            res["audiobox_ce"] = round(float(aes.get("content_enjoyment", 0)), 3)
            res["audiobox_cu"] = round(float(aes.get("content_usefulness", 0)), 3)
            res["audiobox_pc"] = round(float(aes.get("production_complexity", 0)), 3)
        except Exception as e:
            res["audiobox_pq"] = None
    
    return res

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wav-dir", type=str, default="/run/media/kim/Mantu/sa3_lora_runs/length_matrix_p07/wav")
    parser.add_argument("--out-json", type=str, default="/run/media/kim/Mantu/sa3_lora_runs/length_matrix_p07/analytics.json")
    parser.add_argument("--lengths", type=str, default="256,512,1024,2048,4096")
    parser.add_argument("--cfg", type=float, default=6.0)
    parser.add_argument("--seed", type=int, default=1391676905)
    parser.add_argument("--all", action="store_true", help="Analyze all files in directory")
    args = parser.parse_args()

    wav_dir = Path(args.wav_dir)
    target_lengths = [int(x) for x in args.lengths.split(",")]

    if args.all:
        files = sorted(list(wav_dir.glob("*.wav")))
    else:
        files = []
        for L in target_lengths:
            f = wav_dir / f"p07_len{L:04d}_cfg{args.cfg:02.0f}_s{args.seed}.wav"
            if f.exists():
                files.append(f)
            else:
                # Try float formatting in filename if exists
                alt = wav_dir / f"p07_len{L:04d}_cfg{args.cfg:04.1f}_s{args.seed}.wav"
                if alt.exists():
                    files.append(alt)

    print(f"Analyzing {len(files)} files...")
    results = []
    cached = {}
    if os.path.exists(args.out_json):
        try:
            with open(args.out_json, "r") as in_f:
                prev = json.load(in_f)
                for item in prev:
                    if "filename" in item:
                        cached[item["filename"]] = item
        except Exception:
            pass

    for i, f in enumerate(files):
        if f.name in cached:
            results.append(cached[f.name])
            continue
        t0 = time.time()
        print(f"[{i+1}/{len(files)}] Processing {f.name}...")
        r = analyze_clip(f, run_audiobox=True)
        import re
        m_len = re.search(r"len(\d+)", f.name)
        r["length_frames"] = int(m_len.group(1)) if m_len else None
        m_w = re.search(r"w(\d+)", f.name)
        r["adapter_weight"] = float(m_w.group(1)) / 100.0 if m_w else None
        m_cfg = re.search(r"cfg(\d+)", f.name)
        r["cfg"] = float(m_cfg.group(1)) if m_cfg else 6.0
        r["prompt"] = "acid145" if "acid145" in f.name else ("melodic151" if "melodic151" in f.name else "p07")
        r["adapter_name"] = "dora256_avp_aug10" if "dora256" in f.name else "subloss_k24"
        results.append(r)
        print(f"   PQ: {r.get('audiobox_pq')} | RT60: {r.get('rt60_s')}s | Flatness: {r.get('spectral_flatness')} | Onsets: {r.get('onsets_per_sec')}/s ({time.time()-t0:.1f}s)")

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w") as out_f:
        json.dump(results, out_f, indent=2)

    print(f"\nDone. Saved analytics to {args.out_json}")

if __name__ == "__main__":
    main()
