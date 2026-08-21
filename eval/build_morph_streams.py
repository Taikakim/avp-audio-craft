#!/usr/bin/env python3
"""build_morph_streams.py — per-crop CONTOUR SYMBOL sidecars for the morph-conditioning
bracket (D12/Q-lane; Kim direct 2026-08-21: "the morph stuff... the one actually new idea").

From each latents_sa3 crop's f0_other_ts (the melodic line, D3 fields, latent-frame rate):
semitone values on VOICED frames -> sparse grid (voiced frames, stride 4 ≈ 2.7 Hz) ->
K&P dense-rank contour symbols over sliding windows of L grid points (contour_streams,
mir 42c3a83; ordered-Bell alphabets: L=2 -> 3 symbols, L=3 -> 13, L=4 -> 75) ->
piecewise-constant per-frame stream. Written as <stem>.melody8.npy (int8, 4096) into
SIBLING dirs latents_sa3_morphL{2,3,4}/ — the filename convention keeps sa3_control's
melody_contour loader unchanged; semantics are per-dir.

Encoding: 0 = UNDEFINED/unvoiced (held-forward gaps before first window), symbol s -> s+1.
Vocab for the encoder = Bell(L) + 2 (0 undefined + symbols + reserved null slot):
L2 -> 5, L3 -> 15, L4 -> 77.  Crops with < L+2 voiced grid points are SKIPPED (the
dataset's melody filter drops them, same as Head-B's 2649/5400 coverage behaviour).

Run: /home/kim/Projects/mir/mir/bin/python eval/build_morph_streams.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, "/home/kim/Projects/mir")
from src.conditioners.contour_streams import contour_stream, expand_to_frames  # noqa: E402

LAT = "/home/kim/Projects/latents_sa3"
STRIDE = 4
TOL_SEMITONES = 0.5
LS = (2, 3, 4)
IOI_TOL = 0.15          # relative IOI tolerance: within 15% = "equal" duration (log-space)

def main():
    outs = {L: f"{LAT}_morphL{L}" for L in LS}
    for d in outs.values():
        os.makedirs(d, exist_ok=True)
    import glob
    npzs = sorted(glob.glob(os.path.join(LAT, "*.TIMESERIES.npz")))
    n_ok = {L: 0 for L in LS}
    n_skip = 0
    for i, p in enumerate(npzs):
        stem = os.path.basename(p).replace(".TIMESERIES.npz", "")
        try:
            z = np.load(p)
            f0 = np.asarray(z["f0_other_ts"], np.float64)
            v = np.asarray(z["f0_other_voiced_ts"], np.float64) > 0.5
        except Exception:
            n_skip += 1
            continue
        T = f0.shape[0]
        semis = np.zeros(T)
        semis[v] = 12.0 * np.log2(np.maximum(f0[v], 1e-3) / 440.0)
        voiced_frames = np.flatnonzero(v)
        points = voiced_frames[::STRIDE]
        for L in LS:
            if points.size < L + 2:
                continue
            syms, anchors = contour_stream(semis, points, L=L, tol=TOL_SEMITONES)
            stream = expand_to_frames(syms, anchors, T)
            enc = np.where(stream < 0, 0, stream + 1).astype(np.int8)
            np.save(os.path.join(outs[L], stem + ".melody8.npy"), enc)
            n_ok[L] += 1
        # IOI-rhythm stream (Q1: rhythm is the channel the model KEEPS): onset events from
        # the global onset envelope (p95-gated peak-pick per the meter lesson), values =
        # log inter-onset interval at each event, event grid = the onsets themselves.
        try:
            env = np.asarray(z["onset_envelope_ts"], np.float64)
            thr = np.percentile(env, 95) * 0.5
            on = np.flatnonzero((env[1:-1] > env[:-2]) & (env[1:-1] >= env[2:]) & (env[1:-1] > thr)) + 1
            if on.size >= 6:
                ioi = np.diff(on).astype(np.float64)
                vals = np.zeros(T)
                vals[on[1:]] = np.log(np.maximum(ioi, 1.0))
                syms, anchors = contour_stream(vals, on[1:], L=3, tol=IOI_TOL)
                stream = expand_to_frames(syms, anchors, T)
                enc = np.where(stream < 0, 0, stream + 1).astype(np.int8)
                d = LAT + "_morphIOI3"
                os.makedirs(d, exist_ok=True)
                np.save(os.path.join(d, stem + ".melody8.npy"), enc)
                n_ok.setdefault("ioi", 0)
                n_ok["ioi"] += 1
        except Exception:
            pass
        if (i + 1) % 1000 == 0:
            print(f"[morph] {i+1}/{len(npzs)}", flush=True)
    print("[morph] done: " + ", ".join(f"{k}={v}" for k, v in n_ok.items()) + f", skipped {n_skip}")

if __name__ == "__main__":
    main()
