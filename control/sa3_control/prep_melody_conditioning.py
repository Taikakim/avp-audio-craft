#!/usr/bin/env python3
"""prep_melody_conditioning.py — Head B (melody FiLM conditioning) input streams.

REUSES the Head A ceiling study's per-frame targets (eval/musicology/head_a_ceiling/
targets/<id>.npz, y8 (4096, 8) fp16 soft time-overlap class weights, built by
prep_targets.py for the 2,649 melodies.jsonl ids with latents) — does NOT re-derive
anything from MIDI. Spec: docs/superpowers/specs/2026-07-22-melodic-latch-film.md §0/§2.

Output: one int8 (4096,) hard class array per crop, values 0..7 in FOLD_NAMES order
(rest, pedal, m1, m2, m3, m5, m7, m12), saved as <out_dir>/<id>.melody8.npy — a sidecar
dir LatentControlDataset(melody_dir=...) finds by latent stem.

WHY HARD CLASSES (argmax), NO soft boundary weights: the conditioning INPUT is not a
loss target. Head A's soft y8 rows encode *supervision uncertainty* at ~1-frame note
boundaries — meaningful for a readout CE loss, meaningless as a generative conditioning
symbol: Head B's contract (spec §2/§4: catalog cells, bring-your-own 16-step contour)
hands the model a definite per-frame symbol stream, and inference-time streams (motif
catalog cells, user input) are hard by construction, so training on hard streams keeps
train/inference input distributions identical. Boundary softness (~93 ms) is also below
the adapter's temporal resolution of interest. (Input stream ≠ loss target.)

Run (any py3 + numpy, CPU, ~seconds):
  python3 control/sa3_control/prep_melody_conditioning.py
"""
import argparse
import json
import os
import time

import numpy as np

TARGETS = "/home/kim/Projects/SAO/eval/musicology/head_a_ceiling/targets"
LATENTS = "/home/kim/Projects/latents_sa3"
OUT_DEFAULT = "/run/media/kim/Kosmos/latents_sa3_melody"
FOLD_NAMES = ["rest", "pedal", "m1", "m2", "m3", "m5", "m7", "m12"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets-dir", default=TARGETS)
    ap.add_argument("--latents-dir", default=LATENTS)
    ap.add_argument("--out-dir", default=OUT_DEFAULT)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    ids = sorted(f[:-4] for f in os.listdir(args.targets_dir) if f.endswith(".npz"))
    n_done = n_skip = 0
    class_hist = np.zeros(len(FOLD_NAMES), dtype=np.int64)
    for fid in ids:
        if not os.path.exists(os.path.join(args.latents_dir, fid + ".npy")):
            n_skip += 1
            continue
        out_p = os.path.join(args.out_dir, fid + ".melody8.npy")
        y8 = np.load(os.path.join(args.targets_dir, fid + ".npz"))["y8"].astype(np.float32)
        cls = np.argmax(y8, axis=1).astype(np.int8)          # hard classes (see header)
        np.save(out_p, cls)
        class_hist += np.bincount(cls, minlength=len(FOLD_NAMES))
        n_done += 1

    tot = int(class_hist.sum())
    meta = {
        "source_targets": args.targets_dir,
        "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_streams": n_done,
        "n_skipped_no_latent": n_skip,
        "class_names": FOLD_NAMES,
        "encoding": "int8 (4096,) argmax of head_a_ceiling y8; 0=rest",
        "class_fractions": {n: round(int(c) / max(tot, 1), 5)
                            for n, c in zip(FOLD_NAMES, class_hist)},
        "note": ("hard classes on purpose — conditioning input, not a loss target; "
                 "see prep_melody_conditioning.py docstring"),
    }
    with open(os.path.join(args.out_dir, "_meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(f"[prep] wrote {n_done} streams -> {args.out_dir} (skipped {n_skip} w/o latent)")
    print("[prep] class fractions:", meta["class_fractions"])


if __name__ == "__main__":
    main()
