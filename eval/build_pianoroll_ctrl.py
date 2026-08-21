#!/usr/bin/env python3
"""build_pianoroll_ctrl.py — per-crop PIANO-ROLL conditioners from MuScriptor MIDIs
(Kim direct 2026-08-21: "a 256x128 matrix for notes as a conditioner on its own lane,
sample matched, stretched to clip length, from the muscriptor midis").

Each latents_sa3 crop id has a MuScriptor .mid transcribing exactly its 380.4 s / 4096
latent-frame segment (time 0 = crop start). Rendered to a (128, 4096) float16 roll at the
latent rate (10.7666 fps) — velocity/64 while a note is held — and saved as
latents_sa3_proll/<stem>.ctrl.npy. train_lora's mir_ctrl machinery slices it to any crop
window (T256 etc.) exactly like the MIR ctrl arrays, which IS the sample-matched
stretch-to-clip-length semantics.

Run: /home/kim/Projects/mir/mir/bin/python eval/build_pianoroll_ctrl.py
"""
import glob
import os

import mido
import numpy as np

MID_DIR = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/muscriptor_full"
OUT = "/home/kim/Projects/latents_sa3_proll"
FPS = 44100 / 4096
T = 4096


def roll_of(path):
    m = mido.MidiFile(path)
    roll = np.zeros((128, T), dtype=np.float16)
    t_s = 0.0
    active = {}
    for msg in m:                       # merged, delta-times in seconds
        t_s += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            active[msg.note] = (t_s, msg.velocity)
        elif msg.type in ("note_off", "note_on"):
            if msg.note in active:
                s0, vel = active.pop(msg.note)
                f0, f1 = int(s0 * FPS), min(int(t_s * FPS) + 1, T)
                if f0 < T:
                    roll[msg.note, f0:f1] = vel / 64.0
    for note, (s0, vel) in active.items():     # notes held to the end
        f0 = int(s0 * FPS)
        if f0 < T:
            roll[note, f0:] = vel / 64.0
    return roll


def main():
    os.makedirs(OUT, exist_ok=True)
    mids = sorted(glob.glob(os.path.join(MID_DIR, "*.mid")))
    n = 0
    for i, p in enumerate(mids):
        stem = os.path.splitext(os.path.basename(p))[0]
        o = os.path.join(OUT, stem + ".ctrl.npy")
        if os.path.exists(o):
            continue
        try:
            np.save(o, roll_of(p))
            n += 1
        except Exception as e:
            print(f"[proll] FAIL {stem}: {e}")
        if (i + 1) % 1000 == 0:
            print(f"[proll] {i+1}/{len(mids)}", flush=True)
    print(f"[proll] done: {n} written")


if __name__ == "__main__":
    main()
