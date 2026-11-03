#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""e24_build_contour_packs.py -- EXPERIMENTS E24: per-crop melody control arrays from the MuScriptor MIDIs, pitch-invariant by construction, for the mir_ctrl per-block inlet.

Melodic line: the skyline (highest sounding non-drum note) of each crop's MIDI, at the latent rate (10.7666 fps, T = 4096, the same crops as latents_sa3).
  arm C  contour_centered  (2, T)   pitch minus the crop's median note, /12; note-on mask. Keeps interval size, ignores key. The easiest to learn.
  arm A  contour_interval  (26, T)  one-hot of the semitone step from the previous note, clipped to +-12, held for the note; onset flag on its first frame.
Arm B (K&P L3 tokens on the note grid) is not built: E23 found the L3 morph lane does not follow, so A and C come first.
Outputs float16 <stem>.ctrl.npy, as build_pianoroll_ctrl.py. RUN: mir/bin/python eval/e24_build_contour_packs.py
"""
import glob
import json
import os
from concurrent.futures import ProcessPoolExecutor

import mido
import numpy as np

MID_DIR = "/run/media/kim/Kosmos/muscriptor_full"
OUT = {"C": "/run/media/kim/Lehto/latents-all-backup/latents_sa3_contourC", "A": "/run/media/kim/Lehto/latents-all-backup/latents_sa3_contourA"}
FPS = 44100 / 4096
T = 4096
DRUM_CHANNEL = 9
LO, HI = 36, 108                     # ignore sub-bass and extreme register when picking the line


def skyline(path):
    """(T,) int16 highest sounding note per frame, -1 where nothing sounds."""
    m = mido.MidiFile(path)
    roll = np.zeros((128, T), dtype=bool)
    t_s, active = 0.0, {}
    for msg in m:
        t_s += msg.time
        if msg.type not in ("note_on", "note_off") or msg.channel == DRUM_CHANNEL or not (LO <= msg.note <= HI):
            continue
        if msg.type == "note_on" and msg.velocity > 0:
            active[msg.note] = t_s
        elif msg.note in active:
            s0 = active.pop(msg.note)
            f0, f1 = int(s0 * FPS), min(int(t_s * FPS) + 1, T)
            if f0 < T:
                roll[msg.note, f0:f1] = True
    for note, s0 in active.items():
        f0 = int(s0 * FPS)
        if f0 < T:
            roll[note, f0:] = True
    idx = np.arange(128)[:, None]
    top = (roll * idx).max(axis=0)
    return np.where(roll.any(axis=0), top, -1).astype(np.int16)


def arm_c(line):
    v = line >= 0
    if v.sum() == 0:
        return np.zeros((2, T), dtype=np.float16)
    med = float(np.median(line[v]))
    return np.stack([np.where(v, (line - med) / 12.0, 0.0), v.astype(np.float64)]).astype(np.float16)


def arm_a(line):
    out = np.zeros((26, T), dtype=np.float16)
    prev, cur = None, None
    for t in range(T):
        n = int(line[t])
        if n < 0:
            cur = None
            continue
        if n != cur:
            step = 0 if prev is None else int(np.clip(n - prev, -12, 12))
            out[25, t] = 1.0
            prev, cur, held = n, n, step
        out[held + 12, t] = 1.0
    return out


def one(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    oc, oa = os.path.join(OUT["C"], stem + ".ctrl.npy"), os.path.join(OUT["A"], stem + ".ctrl.npy")
    if os.path.exists(oc) and os.path.exists(oa):
        return None
    try:
        s = skyline(path)
        np.save(oc, arm_c(s))
        np.save(oa, arm_a(s))
        v = s >= 0
        return dict(stem=stem, voiced=float(v.mean()), span=float(np.percentile(s[v], 95) - np.percentile(s[v], 5)) if v.any() else 0.0, onsets=int(np.sum((s[1:] != s[:-1]) & (s[1:] >= 0))))
    except Exception as e:                      # noqa: BLE001
        return dict(stem=stem, error=str(e)[:200])


def main():
    for d in OUT.values():
        os.makedirs(d, exist_ok=True)
    mids = sorted(glob.glob(os.path.join(MID_DIR, "*.mid")))
    with ProcessPoolExecutor(10) as ex:
        res = [r for r in ex.map(one, mids, chunksize=16) if r]
    err = [r for r in res if "error" in r]
    ok = [r for r in res if "error" not in r]
    s = dict(n=len(ok), errors=len(err), first_errors=err[:3], voiced_mean=round(float(np.mean([r["voiced"] for r in ok])), 3) if ok else None,
             span_median=float(np.median([r["span"] for r in ok])) if ok else None, onsets_median=float(np.median([r["onsets"] for r in ok])) if ok else None,
             empty=sum(1 for r in ok if r["voiced"] == 0))
    with open(os.path.join(OUT["C"], "_build.json"), "w") as f:
        json.dump(s, f, indent=1)
    print(s)


if __name__ == "__main__":
    main()
