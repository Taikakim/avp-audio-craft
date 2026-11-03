#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""e24_build_l3_pack.py -- EXPERIMENTS E24 arm B: K&P L3 contour symbols on the NOTE grid, from the MuScriptor MIDIs, for the mir_ctrl per-block inlet.

Line: the same skyline as arms A and C (e24_build_contour_packs.skyline). Grid: one point per note (a pitch change, or a new note after a rest).
Symbol: the dense-rank shape of the last 3 notes (13 shapes, tolerance 0.5 st), held from its note until the next note, zero while nothing sounds.
Output float16 <stem>.ctrl.npy, (15, 4096): 13 one-hot shapes, note-on flag, sounding mask. The first two notes of a crop have no shape yet: all 13 are zero.
Differs from the morph streams of D12/D17 (latents_sa3_morphL3): notes instead of Melodia on the other stem, and a note grid instead of every 4th voiced frame.
RUN: mir/bin/python eval/e24_build_l3_pack.py
"""
import glob
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, "/home/kim/Projects/mir")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.conditioners.contour_codes import n_contours           # noqa: E402
from src.conditioners.contour_streams import contour_stream, expand_to_frames  # noqa: E402
from e24_build_contour_packs import MID_DIR, T, skyline     # noqa: E402

OUT = "/run/media/kim/Lehto/latents-all-backup/latents_sa3_contourB"
L = 3
TOL = 0.5
N_SYM = n_contours(L)


def note_points(line):
    """Frames where a note starts: sounding, and either a new pitch or the first frame after a rest."""
    prev = np.concatenate([[-1], line[:-1]])
    return np.flatnonzero((line >= 0) & (line != prev))


def arm_b(line):
    out = np.zeros((N_SYM + 2, T), dtype=np.float16)
    v = line >= 0
    pts = note_points(line)
    out[N_SYM + 1] = v
    out[N_SYM, pts] = 1.0
    if pts.size >= L:
        syms, anchors = contour_stream(line.astype(np.float64), pts, L=L, tol=TOL)
        st = expand_to_frames(syms, anchors, T)
        on = (st >= 0) & v
        out[st[on], np.flatnonzero(on)] = 1.0
    return out


def one(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    o = os.path.join(OUT, stem + ".ctrl.npy")
    if os.path.exists(o):
        return None
    try:
        line = skyline(path)
        a = arm_b(line)
        np.save(o, a)
        return dict(stem=stem, notes=int(a[N_SYM].sum()), coded=float(a[:N_SYM].sum(axis=0).mean()), counts=a[:N_SYM].sum(axis=1).astype(int).tolist())
    except Exception as e:                      # noqa: BLE001
        return dict(stem=stem, error=str(e)[:200])


def main():
    os.makedirs(OUT, exist_ok=True)
    mids = sorted(glob.glob(os.path.join(MID_DIR, "*.mid")))
    with ProcessPoolExecutor(10) as ex:
        res = [r for r in ex.map(one, mids, chunksize=16) if r]
    err = [r for r in res if "error" in r]
    ok = [r for r in res if "error" not in r]
    tot = np.sum([r["counts"] for r in ok], axis=0) if ok else np.zeros(N_SYM)
    s = dict(n=len(ok), errors=len(err), first_errors=err[:3], n_symbols=N_SYM, notes_median=float(np.median([r["notes"] for r in ok])) if ok else None,
             coded_mean=round(float(np.mean([r["coded"] for r in ok])), 3) if ok else None, symbol_share=[round(float(x), 3) for x in tot / max(tot.sum(), 1)])
    with open(os.path.join(OUT, "_build.json"), "w") as f:
        json.dump(s, f, indent=1)
    print(s)


if __name__ == "__main__":
    main()
