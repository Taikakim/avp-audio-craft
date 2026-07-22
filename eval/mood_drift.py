#!/usr/bin/env python3
"""
mood_drift.py -- how far a model's OUTPUT mood profile drifts from its TRAINING-SET mood
reference (Kim 2026-07-22: does the model drift away from the goa melodic/retro/... profile
as it degenerates?). Turns the mood vector into a drift-from-source signal using the
goa/avp baselines in eval/corpus_reference.json.

INPUT: a mood summary CSV from mood_timeseries.py (per-clip mean 56-dim mood + model/ckpt/
cfg/strength/clap_matched). Each model is compared to ITS dataset reference (goa vs avp,
inferred from the label).

PER (model,ckpt): mean output mood profile, cosine similarity to the dataset reference,
L1 drift, and the tags that GAINED / LOST the most vs reference (e.g. gained atmospheric/
soundscape, lost melodic = the pad-fill drift). Correlates mood-drift with clap degeneration.

Run: mir/bin/python eval/mood_drift.py --summary /tmp/mood_summary.csv --out /tmp/mood_drift.csv
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REF = Path("/home/kim/Projects/SAO/eval/corpus_reference.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    ref = json.loads(REF.read_text())
    labels = ref["moodtheme_labels"]
    refvec = {"goa": np.array(ref["goa"]["mood_mean"]), "avp": np.array(ref["avp"]["mood_mean"])}

    df = pd.read_csv(a.summary)
    mood_cols = [c for c in df.columns if c.startswith("mood_")]
    tag_of = [c[len("mood_"):] for c in mood_cols]
    df["dataset"] = np.where(df.model.str.contains("goa"), "goa", "avp")

    rows = []
    for (model, ckpt), g in df.groupby(["model", "ckpt"]):
        ds = g["dataset"].iloc[0]
        rv = refvec[ds]
        # align the summary's mood columns to the reference label order
        out = np.array([g[f"mood_{t}"].mean() if f"mood_{t}" in g else 0.0 for t in labels])
        cos = float(out @ rv / (np.linalg.norm(out) * np.linalg.norm(rv) + 1e-9))
        l1 = float(np.abs(out - rv).sum())
        delta = out - rv
        gain = np.argsort(delta)[::-1][:4]
        loss = np.argsort(delta)[:4]
        rows.append({
            "model": model, "ckpt": ckpt, "dataset": ds, "n": len(g),
            "clap_matched": round(float(g["clap_matched"].mean()), 3) if "clap_matched" in g else None,
            "mood_cos_to_ref": round(cos, 4), "mood_L1_drift": round(l1, 4),
            "gained": "|".join(f"{labels[j]}+{delta[j]:.02f}" for j in gain if delta[j] > 0.01),
            "lost": "|".join(f"{labels[j]}{delta[j]:.02f}" for j in loss if delta[j] < -0.01),
        })
    out = pd.DataFrame(rows).sort_values("mood_cos_to_ref")
    out.to_csv(a.out, index=False)
    pd.set_option("display.width", 200, "display.max_colwidth", 40)
    print(f"=== mood drift vs dataset reference ({len(out)} model-checkpoints) ===")
    print(out.to_string(index=False))
    if "clap_matched" in out and out["clap_matched"].notna().any():
        c = out[["mood_cos_to_ref", "clap_matched"]].dropna()
        if len(c) > 3:
            print(f"\ncorr(mood_cos_to_ref, clap_matched) = {c['mood_cos_to_ref'].corr(c['clap_matched']):.2f} "
                  "(positive => mood-drift tracks genre-degeneration)")
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
