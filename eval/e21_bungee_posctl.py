#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-10-28)
"""e21_bungee_posctl.py -- positive control for EXPERIMENTS E21: pitch-shift the k=0 steered renders by 3/6/9 semitones with
bungee (never sox), so the E21 meter must report the shift. Run with the mir pitch venv:
  /home/kim/Projects/mir/pitch_venv/bin/python eval/e21_bungee_posctl.py
"""
import argparse
from pathlib import Path
import numpy as np, soundfile as sf
from bungee_python import bungee as B

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="/run/media/kim/Mantu/sa3_control_runs/e21_transposition_probe_20261028")
ap.add_argument("--glob", default="e21__*__k0__g2048__*.wav", help="the k=0 renders to shift")
a = ap.parse_args()
OUT = Path(a.out)
for src in sorted(OUT.glob(a.glob)):
    x, sr = sf.read(src, always_2d=True)
    for k in (3, 6, 9):
        dst = OUT / f"posctl__{src.stem}__k{k}.wav"
        if dst.exists():
            continue
        st = B.Bungee(sample_rate=sr, channels=x.shape[1])
        st.set_pitch(2.0 ** (k / 12.0))
        y = np.asarray(st.process(x.astype(np.float32)), dtype=np.float32)
        y = y[: len(x)] if len(y) >= len(x) else np.pad(y, ((0, len(x) - len(y)), (0, 0)))
        sf.write(dst, y, sr)
        print("posctl", dst.name, flush=True)
