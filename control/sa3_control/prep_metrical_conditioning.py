#!/usr/bin/env python3
"""prep_metrical_conditioning.py — E3 (metrical-position FiLM) input streams.

Design: docs/superpowers/specs/2026-07-31-metrical-tree-pe-design.md (F) §1-2, reviewed
by C. Mirrors prep_melody_conditioning.py's contract: one sidecar per crop that
LatentControlDataset finds by latent stem.

Derivation is CROP-LOCAL from the .TIMESERIES.npz companions (beat_activation_ts +
downbeat_activation_ts, 4096 frames @10.77 Hz, already crop-aligned; beat-aware crops
START on downbeats, which anchors the bar grid):
  bar boundaries  = peak-picked downbeat activation (min-distance guarded)
  beat positions  = peak-picked beat activation
  subdiv_in_beat  = fractional inter-beat position * 4 -> 0..3 (HARD class)
  beat_in_bar     = beats since last downbeat, clamped 0..3
  bar_in_phrase   = bar count since crop start mod 8   } v1 DEVIATION from F's spec:
  phrase_idx      = (bar count // 8) mod 8             } absolute phrase anchoring via
    musicology section_lens_bars is deferred — crop-local anchoring is well-defined
    (crops start on downbeats) and phrase PROGRESSION (the thing the model must learn)
    is preserved; only the global phrase-zero offset is arbitrary. Documented per-run.
  coverage_flag   = 0 where the activation evidence is too weak to trust (null token)
  coverage_conf   = per-frame local downbeat-evidence scalar (0..1)

Tempo drift honored: indices derive from the ACTUAL picked boundaries (variable bar
length), never a fixed frames-per-bar constant.

Output: <out>/<id>.metrical.npy int8 [5, 4096] (subdiv, beat_in_bar, bar_in_phrase,
phrase_idx, coverage_flag) + <id>.metrical_conf.npy float16 [4096].

Run (any py3+numpy+scipy, CPU, minutes):
  python3 control/sa3_control/prep_metrical_conditioning.py
"""
import argparse
import glob
import os

import numpy as np
from scipy.signal import find_peaks

LATENTS = "/home/kim/Projects/latents_sa3"
OUT_DEFAULT = "/home/kim/Projects/latents_sa3_metrical"
FRATE = 10.7666015625
# 145 bpm 4/4: beat 4.46 frames, bar 17.8 frames. Guards span 100-180 bpm.
BEAT_MIN_DIST = 3
BAR_MIN_DIST = 11
MIN_BARS = 8          # a 380 s crop with fewer than 8 picked bars = untrustworthy grid
MAX_BARS = 220


def per_crop(ts_path):
    z = np.load(ts_path, allow_pickle=True)
    beat = np.asarray(z["beat_activation_ts"], dtype=np.float32)
    down = np.asarray(z["downbeat_activation_ts"], dtype=np.float32)
    T = beat.shape[0]

    dpk, dprop = find_peaks(down, height=max(0.1, 0.3 * down.max()), distance=BAR_MIN_DIST)
    bpk, _ = find_peaks(beat, height=max(0.1, 0.3 * beat.max()), distance=BEAT_MIN_DIST)

    out = np.zeros((5, T), dtype=np.int8)
    conf = np.zeros(T, dtype=np.float16)
    if len(dpk) < MIN_BARS or len(dpk) > MAX_BARS or len(bpk) < 4 * MIN_BARS // 2:
        return out, conf, False      # coverage_flag stays 0 everywhere -> null token

    frames = np.arange(T)
    # bar index per frame (bars counted from crop start; frame before first pick -> bar of pick 0)
    bar_idx = np.clip(np.searchsorted(dpk, frames, side="right") - 1, 0, len(dpk) - 1)
    # beats within each frame's bar
    beat_idx_global = np.clip(np.searchsorted(bpk, frames, side="right") - 1, 0, len(bpk) - 1)
    # beats since the current bar's downbeat: count beat picks in (downbeat, frame]
    beats_at_bar_start = np.clip(np.searchsorted(bpk, dpk[bar_idx], side="right") - 1, 0, None)
    beat_in_bar = np.clip(beat_idx_global - beats_at_bar_start, 0, 3)
    # subdivision: fractional position between surrounding beat picks
    next_b = np.clip(beat_idx_global + 1, 0, len(bpk) - 1)
    span = np.maximum(bpk[next_b] - bpk[beat_idx_global], 1)
    frac = np.clip((frames - bpk[beat_idx_global]) / span, 0, 0.999)
    subdiv = (frac * 4).astype(np.int8)

    out[0] = subdiv
    out[1] = beat_in_bar.astype(np.int8)
    out[2] = (bar_idx % 8).astype(np.int8)
    out[3] = ((bar_idx // 8) % 8).astype(np.int8)
    out[4] = 1                                     # covered
    # confidence: normalized local downbeat evidence, smoothed bar-scale
    k = 19
    pad = np.pad(down, k // 2, mode="edge")
    local = np.array([pad[i:i + k].max() for i in range(T)])
    conf[:] = np.clip(local / (down.max() + 1e-6), 0, 1).astype(np.float16)
    return out, conf, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latents-dir", default=LATENTS)
    ap.add_argument("--out-dir", default=OUT_DEFAULT)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    ts_files = sorted(glob.glob(os.path.join(args.latents_dir, "*.TIMESERIES.npz")))
    n_ok = n_null = 0
    for f in ts_files:
        fid = os.path.basename(f).replace(".TIMESERIES.npz", "")
        op = os.path.join(args.out_dir, fid + ".metrical.npy")
        if os.path.exists(op):
            continue
        out, conf, ok = per_crop(f)
        np.save(op, out)
        np.save(os.path.join(args.out_dir, fid + ".metrical_conf.npy"), conf)
        n_ok += ok
        n_null += (not ok)
    print(f"[metrical] covered={n_ok} null={n_null} "
          f"({100*n_ok/max(n_ok+n_null,1):.1f}% coverage) -> {args.out_dir}")


if __name__ == "__main__":
    main()
