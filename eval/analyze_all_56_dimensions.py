#!/usr/bin/env python3
"""analyze_all_56_dimensions.py -- Complete 56-dim continuous mood analysis for mood_oppose suite.

Evaluates every rendered clip in /home/kim/evals_aac/mood_oppose using the official
Essentia discogs-effnet -> mtg_jamendo_moodtheme (56 continuous sigmoid dimensions).
Outputs:
- CSV of all 56 dimensions across all clips
- JSON formatted for interactive web dashboard
- Formatted console report of trade-offs, co-elevated clusters, and cannibalized emotions.
"""
import sys, os, json, csv
from pathlib import Path
import numpy as np
import librosa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from mood_score_layeract_crops import EffnetMoodCPU

AAC_DIR = Path("/home/kim/evals_aac/mood_oppose")
MANIFEST = AAC_DIR / "manifest.json"
OUT_CSV = AAC_DIR / "mood_56d_predictions.csv"
OUT_JSON = AAC_DIR / "mood_56d_predictions.json"

def main():
    if not MANIFEST.exists():
        print(f"Error: {MANIFEST} does not exist yet.")
        sys.exit(1)

    with open(MANIFEST) as f:
        manifest = json.load(f)

    print("Initializing EffnetMoodCPU classifier...")
    extractor = EffnetMoodCPU()
    classes = extractor.classes
    print(f"Loaded {len(classes)} mood/theme classes.")

    results = []
    by_prompt = {}

    for item in manifest:
        aac_file = AAC_DIR / item["aac_file"]
        if not aac_file.exists():
            print(f"Warning: {aac_file} missing, skipping.")
            continue

        print(f"Analyzing {item['aac_file']} ({item['action']})...", flush=True)
        y, _ = librosa.load(str(aac_file), sr=16000, mono=True)
        preds = extractor(y)  # (56,) float32

        row = {
            "prompt_id": item["prompt_id"],
            "prompt_text": item["prompt_text"],
            "cond_id": item["cond_id"],
            "action": item["action"],
            "weight": item["weight"],
            "aac_file": item["aac_file"],
            "predictions": {classes[i]: float(preds[i]) for i in range(len(classes))}
        }
        results.append(row)
        by_prompt.setdefault(item["prompt_id"], {})[item["cond_id"]] = preds

    # Save CSV
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["prompt_id", "cond_id", "action", "weight", "aac_file"] + classes)
        for r in results:
            writer.writerow([r["prompt_id"], r["cond_id"], r["action"], r["weight"], r["aac_file"]] + [r["predictions"][c] for c in classes])
    print(f"\nSaved CSV: {OUT_CSV}")

    # Save JSON
    with open(OUT_JSON, "w") as f:
        json.dump({
            "classes": classes,
            "clips": results
        }, f, indent=2)
    print(f"Saved JSON: {OUT_JSON}")

    # Analysis Reporting
    print("\n" + "=" * 80)
    print("56-DIMENSIONAL MOOD REINFORCEMENT & OPPOSITION REPORT")
    print("=" * 80)

    for pid, ptitle in [
        ("prompt_melodic", "PROMPT A: Melodic Goa ('2020s goa trance, melodic mood, 148 bpm')"),
        ("prompt_dark", "PROMPT B: Dark Psytrance ('2020s dark psytrance, dark mood, heavy bass, 148 bpm')")
    ]:
        pdata = by_prompt.get(pid)
        if not pdata or "base" not in pdata:
            continue

        base_vec = pdata["base"]
        print(f"\n{'#' * 80}")
        print(f"# {ptitle}")
        print(f"{'#' * 80}")

        # Baseline top 5
        base_top5 = np.argsort(base_vec)[-5:][::-1]
        print(f"\nBaseline (Unguided) Top Moods:")
        for idx in base_top5:
            print(f"  {classes[idx]:<16}: {base_vec[idx]:.4f}")

        # Comparisons
        for cond_id, vec in pdata.items():
            if cond_id == "base":
                continue

            diff = vec - base_vec
            sorted_idx = np.argsort(diff)
            action = next(r["action"] for r in results if r["prompt_id"] == pid and r["cond_id"] == cond_id)

            print(f"\n--- Condition: {action} ({cond_id}) ---")
            print("  Top 5 Surging Emotions (what came up):")
            for idx in sorted_idx[-5:][::-1]:
                pct = (diff[idx] / (base_vec[idx] + 1e-6)) * 100.0
                print(f"    +{classes[idx]:<15}: {base_vec[idx]:.4f} -> {vec[idx]:.4f} (Δ = {diff[idx]:+.4f}, {pct:+.1f}%)")

            print("  Top 5 Collapsing Emotions (what went down):")
            for idx in sorted_idx[:5]:
                pct = (diff[idx] / (base_vec[idx] + 1e-6)) * 100.0
                print(f"    -{classes[idx]:<15}: {base_vec[idx]:.4f} -> {vec[idx]:.4f} (Δ = {diff[idx]:+.4f}, {pct:+.1f}%)")

if __name__ == "__main__":
    main()
