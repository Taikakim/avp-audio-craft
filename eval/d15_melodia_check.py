#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""d15_melodia_check.py -- EXPERIMENTS D15: an independent meter on the invented-melody clips. MuScriptor made the training rolls and also scored the renders, so check with Melodia, the f0 tracker of E23a, which played no part in training.
Share of voiced frames within 1 semitone of a line, octave folded, against the fed melody, its shuffled blocks, another melody; the no-stream clip against the melodies of its prompt. RUN: mir/bin/python eval/d15_melodia_check.py
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import soundfile as sf

OUT = Path("/home/kim/evals_aac/control_runs/pianoroll_newmelody_goa_t256_step2688_20261103")
FPS = 44100 / 4096
HOP = 441


def f0_of(path):
    import essentia.standard as es
    x, sr = sf.read(path)
    x = x.mean(1) if x.ndim > 1 else x
    x = es.EqualLoudness(sampleRate=sr)(x.astype(np.float32))
    f0, _ = es.PredominantPitchMelodia(sampleRate=sr, frameSize=2048, hopSize=HOP, minFrequency=55, maxFrequency=1760)(x)
    return np.asarray(f0, dtype=np.float64)


def near(f0, line):
    """line: MIDI per latent frame. Within 1 st, octave folded, over voiced tracker frames."""
    v = f0 > 0
    if v.sum() < 50:
        return 0.0, float(v.mean())
    idx = np.minimum((np.arange(f0.size) * HOP / 44100 * FPS).astype(int), line.size - 1)
    st = 69 + 12 * np.log2(f0[v] / 440.0)
    d = np.abs(((st - line[idx][v]) + 6) % 12 - 6)
    return float((d <= 1.0).mean()), float(v.mean())


def job(c):
    import d15_new_melodies as D
    f0 = f0_of(str(OUT / f"{c['id']}.wav"))
    if c["kind"] == "new":
        m = D.melody(c["melody"])
        return dict(id=c["id"], kind="new", fed=near(f0, m)[0], shuf=near(f0, D.shuffle_line(m))[0], other=near(f0, D.melody(c["other"]))[0], voiced=near(f0, m)[1])
    ms = [D.melody(k) for k in c["ms"]]
    return dict(id=c["id"], kind="zero", fed=float(np.mean([near(f0, m)[0] for m in ms])), voiced=float((f0 > 0).mean()))


def main():
    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    todo = [c for c in cells if c["kind"] == "new"]
    for c in cells:
        if c["kind"] == "zero":
            todo.append(dict(c, ms=[k["melody"] for k in cells if k["kind"] == "new" and k["p"] == c["p"]]))
    with ProcessPoolExecutor(8) as ex:
        rows = list(ex.map(job, todo))
    (OUT / "melodia.json").write_text(json.dumps(rows, indent=0))
    new = [r for r in rows if r["kind"] == "new"]
    zero = [r for r in rows if r["kind"] == "zero"]
    rng = np.random.default_rng(1)

    def ci(d):
        d = np.asarray(d)
        b = [rng.choice(d, d.size).mean() for _ in range(4000)]
        return f"{d.mean():+.3f} [{np.percentile(b, 2.5):+.3f}, {np.percentile(b, 97.5):+.3f}] {int((d > 0).sum())}/{d.size}"

    L = [f"MELODIA, an independent meter: voiced frames within 1 semitone of a line, octave folded. Fed {np.mean([r['fed'] for r in new]):.3f}, shuffled {np.mean([r['shuf'] for r in new]):.3f}, other melody {np.mean([r['other'] for r in new]):.3f}, no stream {np.mean([r['fed'] for r in zero]):.3f}. Voiced share: generated {np.mean([r['voiced'] for r in new]):.2f}, no stream {np.mean([r['voiced'] for r in zero]):.2f}.",
         f"   fed minus shuffled {ci([r['fed'] - r['shuf'] for r in new])}; fed minus other {ci([r['fed'] - r['other'] for r in new])}"]
    print("\n".join(L))
    with (OUT / "report.txt").open("a") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
