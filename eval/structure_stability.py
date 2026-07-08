"""structure_stability.py — within-clip tempo/key/repetition stability meter.

Born 2026-07-08 from Kim's wager that the avp adapters' 'glitchy and disjointed'
character was structural, not timbral ('something with self-similarity') — and it was:
avp-adapter renders wander 6–28 bpm within a clip while real avp tracks and goa
adapters lock at IQR 0.0. Mechanism: 7 undisambiguated tempo/pitch augmentation
variants per track under one caption → tempo-multimodal conditioning → mode-hopping
mid-generation. See docs/layer-feature-map.md sibling finding + WORKLOG 2026-07-08.

Metrics per clip (mir venv: /home/kim/Projects/mir/mir/bin/python):
  tempo_iqr_bpm — IQR of the folded (100–200 bpm) dominant tempo across 5 s windows.
                  0.0 = locked grid (all real dance music + healthy adapters);
                  >3 = audible pulse instability, the 'disjointed' signature.
  key_shift     — mean gain of the best transposed chroma match over the identity
                  match vs the clip-global profile (>0 ⇒ tonal center moved).
  recurrence    — beat-synchronous chroma+MFCC recurrence rate (width 8): does
                  material ever return. Needs ≥24 tracked beats (~>25 s at 140 bpm).

CLI: structure_stability.py <wav-or-dir> [...] [--max-seconds 60] [--json out.json]
"""
import argparse
import glob
import json
import os
import warnings

import numpy as np

warnings.filterwarnings("ignore")


def fold_tempo(t, lo=100.0, hi=200.0):
    while t < lo:
        t *= 2
    while t >= hi:
        t /= 2
    return t


def analyze(path, max_seconds=60.0):
    import librosa
    import soundfile as sf
    y, sr = sf.read(path, dtype="float32", always_2d=True)
    y = y.mean(axis=1)[: int(max_seconds * sr)]
    if sr != 44100:
        y = librosa.resample(y, orig_sr=sr, target_sr=44100)
        sr = 44100
    oenv = librosa.onset.onset_strength(y=y, sr=sr)
    win = int(5 * sr / 512)

    tempos = []
    for i in range(0, len(oenv) - win, win):
        t = librosa.beat.tempo(onset_envelope=oenv[i:i + win], sr=sr)[0]
        if t > 0:
            tempos.append(fold_tempo(t))
    tempo_iqr = (float(np.percentile(tempos, 75) - np.percentile(tempos, 25))
                 if len(tempos) > 2 else float("nan"))

    C = librosa.feature.chroma_cqt(y=y, sr=sr)
    g = C.mean(axis=1)
    g /= np.linalg.norm(g) + 1e-9
    drops = []
    for i in range(0, C.shape[1] - win, win):
        p = C[:, i:i + win].mean(axis=1)
        p /= np.linalg.norm(p) + 1e-9
        best = max(float(np.roll(p, k) @ g) for k in range(12))
        drops.append(best - float(p @ g))
    key_shift = float(np.mean(drops)) if drops else float("nan")

    _, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=sr)
    if len(beats) > 24:
        Cb = librosa.util.sync(C, beats)
        Mb = librosa.util.sync(librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)[1:], beats)
        F = np.vstack([Cb / (np.linalg.norm(Cb, axis=0, keepdims=True) + 1e-9),
                       Mb / (np.linalg.norm(Mb, axis=0, keepdims=True) + 1e-9)])
        R = librosa.segment.recurrence_matrix(F, width=8, mode="connectivity", sym=True)
        recurrence = float(R.sum() / (R.shape[0] ** 2))
    else:
        recurrence = float("nan")

    return {"file": path, "tempo_iqr_bpm": tempo_iqr,
            "key_shift": key_shift, "recurrence": recurrence}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="wav files or dirs (dirs glob *.wav)")
    ap.add_argument("--max-seconds", type=float, default=60.0)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    files = []
    for p in args.paths:
        files.extend(sorted(glob.glob(os.path.join(p, "*.wav"))) if os.path.isdir(p) else [p])
    out = [analyze(f, args.max_seconds) for f in files]
    for r in out:
        print(f"{os.path.basename(r['file']):50s} tempoIQR={r['tempo_iqr_bpm']:6.2f} "
              f"keyshift={r['key_shift']:.3f} recur={100 * r['recurrence']:.2f}%")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
