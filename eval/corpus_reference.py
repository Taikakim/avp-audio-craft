#!/usr/bin/env python3
"""
corpus_reference.py -- goa/avp TRAINING-SET reference distributions, so every eval metric can
be read as DRIFT-FROM-SOURCE not just an absolute (Kim 2026-07-22: "one column for the dataset
averages ... so we'll know things like is the stereo narrowing coming from the dataset").

Aggregates the corpus whole-track timeseries (Lehto, already extracted -- same effnet/essentia
path as the eval extractors, so eval vs reference is apples-to-apples) into per-corpus mean/std
of the pad-fill + mood metrics. Split by each npz's __meta__.source path (goa = /Goa_Separated/,
avp = the avp-analyzed dir).

Fields: stereo_width, stereo_corr, dissonance, inharmonicity (track-mean over time), and the
56-dim moodtheme mean profile (the melodic/retro/... signature). Reverb (RT60) is NOT in the
timeseries -- it comes from extract_reverb_depth.py separately.

OUT: eval/corpus_reference.json  {corpus: {metric: {mean,std,n}}, moodtheme_labels, mood_mean}
Run: mir/bin/python eval/corpus_reference.py [--cap-per-corpus 1200]
"""
import argparse
import glob
import json
import os
from pathlib import Path

import numpy as np

LT = Path("/run/media/kim/Kosmos/timeseries")
AVP = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-analyzed")
OUT = Path("/home/kim/Projects/SAO/eval/corpus_reference.json")
SCALAR = ["stereo_width_ts", "stereo_corr_ts", "dissonance_ts", "inharmonicity_ts",
          "spectral_flatness_ts", "spectral_flux_ts", "pitch_salience_ts"]
MOODJSON = Path("/home/kim/Projects/mir/models/essentia/mtg_jamendo_moodtheme-discogs-effnet-1.json")


def corpus_of(source):
    s = (source or "").lower()
    if "goa_separated" in s:
        return "goa"
    if "avp" in s:
        return "avp"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap-per-corpus", type=int, default=1500, help="max tracks/corpus (means stabilize)")
    a = ap.parse_args()

    files = glob.glob(str(LT / "*.npz"))                          # goa + genre refs (flat)
    if AVP.exists():
        files += glob.glob(str(AVP / "**" / "*.TIMESERIES.npz"), recursive=True)  # avp (nested)
    labels = json.loads(MOODJSON.read_text())["classes"] if MOODJSON.exists() else [f"m{i}" for i in range(56)]
    acc = {c: {k: [] for k in SCALAR} for c in ("goa", "avp")}
    mood = {c: [] for c in ("goa", "avp")}
    counts = {"goa": 0, "avp": 0, "other": 0}

    for f in files:
        try:
            d = np.load(f, allow_pickle=True)
            meta = json.loads(str(d["__meta__"])) if "__meta__" in d.files else {}
        except Exception:
            continue
        c = corpus_of(meta.get("source"))
        counts[c] += 1
        if c == "other" or counts[c] > a.cap_per_corpus:
            continue
        for k in SCALAR:
            if k in d.files:
                v = np.asarray(d[k], dtype=np.float64).ravel()
                v = v[np.isfinite(v)]
                if v.size:
                    acc[c][k].append(float(v.mean()))
        if "effnet_moodtheme_ts" in d.files:
            mt = np.asarray(d["effnet_moodtheme_ts"], dtype=np.float64)
            if mt.ndim == 2 and mt.shape[0]:
                mood[c].append(mt.mean(axis=0))

    ref = {"_counts_seen": counts, "moodtheme_labels": labels}
    for c in ("goa", "avp"):
        ref[c] = {}
        for k in SCALAR:
            arr = np.array(acc[c][k])
            ref[c][k.replace("_ts", "")] = {
                "mean": round(float(arr.mean()), 5) if arr.size else None,
                "std": round(float(arr.std()), 5) if arr.size else None, "n": int(arr.size)}
        if mood[c]:
            mm = np.mean(mood[c], axis=0)
            ref[c]["mood_mean"] = [round(float(x), 4) for x in mm]
            top = np.argsort(mm)[::-1][:10]
            ref[c]["mood_top10"] = [f"{labels[j]}:{mm[j]:.3f}" for j in top]
    OUT.write_text(json.dumps(ref, indent=1))
    print(f"[ref] wrote {OUT}  (seen {counts})")
    print("\n=== goa vs avp scalar reference (the dataset-baseline column) ===")
    print(f"{'metric':16}{'goa':>12}{'avp':>12}{'goa-avp':>10}")
    for k in SCALAR:
        kk = k.replace("_ts", "")
        g, v = ref["goa"][kk]["mean"], ref["avp"][kk]["mean"]
        gs = f"{g:>12.4f}" if g is not None else f"{'—':>12}"
        vs = f"{v:>12.4f}" if v is not None else f"{'—':>12}"
        ds = f"{g - v:>10.4f}" if (g is not None and v is not None) else f"{'—':>10}"
        print(f"{kk:16}{gs}{vs}{ds}")
    print(f"\ngoa top moods: {ref['goa'].get('mood_top10')}")
    print(f"avp top moods: {ref['avp'].get('mood_top10')}")


if __name__ == "__main__":
    main()
