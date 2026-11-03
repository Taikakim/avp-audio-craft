#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-11-03)
"""e25b_score.py -- CPU meters for E25b clips: 56-d Essentia mood plus spectral centroid and flatness, which see what the mood tags have no word for.
Writes scores.jsonl. RUN: mir/bin/python eval/e25b_score.py"""
import json, sys
from pathlib import Path
import librosa, numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mood_score_layeract_crops import EffnetMoodCPU
OUT = Path("/home/kim/evals_aac/control_runs/e25b_caption_words_20261103")
log = OUT / "scores.jsonl"
done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
todo = [json.loads(l)["id"] for l in (OUT / "cells.jsonl").read_text().splitlines()]
todo = [c for c in todo if c not in done]
M = EffnetMoodCPU()
(OUT / "classes.json").write_text(json.dumps(list(M.classes)))
with log.open("a") as f:
    for i, c in enumerate(todo):
        y, _ = librosa.load(str(OUT / f"{c}.m4a"), sr=16000, mono=True)
        z, sr = librosa.load(str(OUT / f"{c}.m4a"), sr=44100, mono=True)
        f.write(json.dumps({"id": c, "mood": [round(float(x), 5) for x in M(y)], "centroid": float(librosa.feature.spectral_centroid(y=z, sr=sr).mean()),
                            "flatness": float(librosa.feature.spectral_flatness(y=z).mean()), "onsets": float(len(librosa.onset.onset_detect(y=z, sr=sr)) / (len(z) / sr))}) + "\n")
        f.flush()
print("scored", len(todo))
