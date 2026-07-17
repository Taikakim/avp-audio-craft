#!/usr/bin/env python3
"""corpus_bands.py -- E0-D: corpus reference distributions for the loop meters
(plan 2026-07-15 §2-E0 item 4). Runs the recurrence meter's three statistic
families over every latents_sa3 crop (latent mode, fps 10.767) and writes
quantile bands that parameterize the E1/E2 potentials (lens-B band form).

Run (any venv with numpy; meter core is numpy-only):
  setsid nohup python3 eval/corpus_bands.py > /tmp/corpus_bands.log 2>&1 &
Output: eval/corpus_bands.json
"""
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/kim/Projects/mir/src/tools")

LATENTS = Path("/home/kim/Projects/latents_sa3")
OUT = Path("/home/kim/Projects/SAO/eval/corpus_bands.json")
FPS = 10.767
STATS = ["r_max", "r_median", "novelty_floor", "corr_dim", "det", "det_soft",
         "line_frac_8s", "line_frac_16s", "l_max_sec"]


def one(p):
    from recurrence_meter import calibrate_source, dynamics_stats
    try:
        x = np.load(p)
        cal = calibrate_source(x, fps=FPS)
        dyn = dynamics_stats(x, fps=FPS, ci=False)
        row = {k: cal.get(k) for k in ("r_max", "r_median", "novelty_floor")}
        row.update({k: dyn.get(k) for k in STATS if k not in row})
        return row
    except Exception as e:
        return {"_err": f"{Path(p).name}: {e}"}


def main():
    files = sorted(LATENTS.glob("*.npy"))
    print(f"[bands] {len(files)} latents", flush=True)
    t0 = time.time()
    rows, errs = [], []
    with ProcessPoolExecutor(max_workers=12) as ex:
        for i, row in enumerate(ex.map(one, map(str, files), chunksize=16)):
            (errs if "_err" in row else rows).append(row)
            if i % 250 == 0:
                print(f"[bands] {i}/{len(files)} ({time.time()-t0:.0f}s)", flush=True)
    qs = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
    bands = {}
    for s in STATS:
        v = np.array([r[s] for r in rows if r.get(s) is not None], float)
        bands[s] = {"n": int(v.size),
                    **{f"q{int(q*100):02d}": float(np.quantile(v, q)) for q in qs},
                    "mean": float(v.mean()), "std": float(v.std())}
    OUT.write_text(json.dumps({
        "_doc": "Corpus reference bands over latents_sa3 (latent-mode meter, fps 10.767). "
                "E1/E2 band-hinge potentials use [q25, q90] by default (lens-B: tilt toward "
                "the corpus BAND, never a point). Built by eval/corpus_bands.py.",
        "created": time.strftime("%Y-%m-%d %H:%M"), "n_ok": len(rows),
        "n_err": len(errs), "errors_sample": [e["_err"] for e in errs[:5]],
        "bands": bands}, indent=1))
    print(f"[bands] done: {len(rows)} ok, {len(errs)} err, {time.time()-t0:.0f}s -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
