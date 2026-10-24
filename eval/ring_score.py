#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-24)
"""ring_score.py -- advisory "ringing" score for steered onset-grid clips (gain x density dirs from eval/latch_onset_eval.py).

Why: a listening pass (2026-10-24, latch_opt_grid_biggoa.html) heard overtrained heads ring -- a tone held on one frequency in
every glitch -- where the disintegration gate and the onset meter read "fewer transients" as success. Plain tonal energy cannot
catch it (pads are tonal too), so this scores only NEW persistent narrow peaks relative to the unsteered clip:
  per frame (STFT 8192 / hop 2048, 150 Hz-12 kHz, frames within 50 dB of the loudest), a bin is "prominent" when it stands
  > 12 dB above the median of its 41 neighbouring bins; persistence(f) = share of frames in which bin f is prominent.
  ring = max over f of persistence_steered(f) - persistence_unsteered(f), at the same requested density; ring_hz = that f.
0 = nothing new held, 1 = a new peak held through the whole clip. On the biggoa page it read 0.14 for the head heard clean at
gain 128 and 0.6-0.8 for the heads heard ringing. ADVISORY ONLY: not part of the gate until calibrated on more verdicts.

RUN (mir venv, CPU): mir/bin/python eval/ring_score.py <grid dir> [...] [--workers 6] [--force]
Writes <grid dir>/ring_score.json (local, beside onset_eval.json); skips dirs already scored unless --force.
"""
import argparse, glob, json, os, re, sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import soundfile as sf
from scipy.ndimage import median_filter
from scipy.signal import stft

NFFT, HOP, PROM_DB, MEDW, FLO, FHI, FLOOR_DB = 8192, 2048, 12.0, 41, 150.0, 12000.0, 50.0
FN = re.compile(r"onset_g([\d.]+)_d([\d.]+)\.wav$")


def persistence(path):
    x, sr = sf.read(path, always_2d=True)
    f, _, Z = stft(x.mean(1), sr, nperseg=NFFT, noverlap=NFFT - HOP)
    db = 20 * np.log10(np.abs(Z) + 1e-9)
    keep = (f > FLO) & (f < FHI)
    db, f = db[keep], f[keep]
    db = db[:, db.max(0) > db.max() - FLOOR_DB]
    if db.shape[1] == 0:
        return f, np.zeros(len(f))
    prom = db - median_filter(db, size=(MEDW, 1), mode="nearest")
    return f, (prom > PROM_DB).mean(1)


def _pers(path):
    f, p = persistence(path)
    return path, f, p


def score_dir(d, workers):
    wavs = sorted(w for w in glob.glob(f"{d}/onset_g*_d*.wav") if FN.search(w))
    if not wavs:
        return None
    with ProcessPoolExecutor(workers) as ex:
        P = {p: (f, v) for p, f, v in ex.map(_pers, wavs)}
    cells = []
    for w in wavs:
        g, q = (float(x) for x in FN.search(w).groups())
        if g == 0:
            continue
        b = f"{d}/onset_g0_d{q:g}.wav"
        if b not in P:
            continue
        f, ps = P[w]
        diff = ps - P[b][1]
        i = int(np.argmax(diff))
        cells.append({"gain": g, "requested": q, "ring": round(float(max(diff[i], 0.0)), 3), "ring_hz": round(float(f[i]), 1)})
    return cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    for d in a.dirs:
        out = f"{d}/ring_score.json"
        if os.path.exists(out) and not a.force:
            continue
        cells = score_dir(d, a.workers)
        if cells is None:
            print(f"{os.path.basename(d)}: no grid clips", file=sys.stderr)
            continue
        json.dump({"purpose": "Advisory ringing score per steered cell: new persistent narrow spectral peak vs the unsteered clip "
                              "at the same requested density (not part of the gate).",
                   "script": "eval/ring_score.py",
                   "params": {"nfft": NFFT, "hop": HOP, "prominence_db": PROM_DB, "median_bins": MEDW, "band_hz": [FLO, FHI],
                              "frame_floor_db": FLOOR_DB},
                   "cells": cells}, open(out, "w"), indent=1)
        top = max(cells, key=lambda c: c["ring"]) if cells else None
        print(f"{os.path.basename(d)}: {len(cells)} cells, max ring {top['ring']:.2f} at g{top['gain']:g} d{top['requested']:g} "
              f"({top['ring_hz'] / 1000:.2f} kHz)" if top else f"{os.path.basename(d)}: 0 cells", flush=True)


if __name__ == "__main__":
    main()
