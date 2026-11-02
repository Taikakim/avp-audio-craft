#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""mood_deconf_score.py -- Essentia discogs-effnet -> MTG-Jamendo mood/theme scores (56 dimensions, CPU) for every clip of
eval/mood_deconf_render.py. Resumable. Writes mood_scores.jsonl beside cells.jsonl: {"id", "scores": [56 floats]}, plus classes.json.
RUN: mir/bin/python eval/mood_deconf_score.py
"""
import json
import sys
from pathlib import Path

import librosa

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mood_score_layeract_crops import EffnetMoodCPU  # noqa: E402

OUT = Path("/home/kim/evals_aac/control_runs/mood_deconf_20261103")


def main():
    log = OUT / "mood_scores.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    todo = [c["id"] for c in cells if "dropped" not in c and c["id"] not in done]
    print(f"{len(todo)} clips to score", flush=True)
    model = EffnetMoodCPU()
    (OUT / "classes.json").write_text(json.dumps(list(model.classes)))
    with log.open("a") as f:
        for i, cid in enumerate(todo):
            y, _ = librosa.load(str(OUT / f"{cid}.m4a"), sr=16000, mono=True)
            f.write(json.dumps({"id": cid, "scores": [round(float(x), 5) for x in model(y)]}) + "\n")
            f.flush()
            if i % 100 == 0:
                print(f"  {i + 1}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()
