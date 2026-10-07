#!/usr/bin/env python
"""stem_bass_capture.py — does a separator's BASS stem actually contain the bassline? (psytrance trap)

WHY (CONTINUITY, 2026-10-07; finding by G, confirmed here). For the DJ mix v7 stem-transition plan we separated 35
mix clips with BS-RoFormer (4 stems). G measured that the bass stem holds 0.4 % of the sub-150 Hz energy. That number alone
cannot say WHERE the bassline went (kick energy dominates the low band), so this tool splits each stem's low band into
  HARMONIC  (sustained tones: the bassline)  and  PERCUSSIVE  (transients: the kicks)
with librosa HPSS (long-in-time vs long-in-frequency median filters) and reports, per clip, where the HARMONIC low-band energy
sits: in bass / drums / other / vocals. Measured on 7 of the 35 v7 clips: the bass stem holds ~0 % of the harmonic low band in 6
(it sits in 'other' or 'drums'), and 20.7 % in one. A separator is only usable for "never two basslines at once" transitions if
its bass stem captures most of the harmonic low band.

CAPTURE = bass_harmonic / (sum of harmonic over all stems). Pass bar suggested for the spike: median capture >= 0.6 and no
clip below 0.3. Also prints the drums stem's percussive share (the kick) for orientation.

USAGE  mir venv (librosa):  /home/kim/Projects/mir/mir/bin/python eval/stem_bass_capture.py --stems-root DIR [--every 5] [--seconds 40]
  DIR holds one sub-directory per clip with bass.wav, drums.wav, other.wav, vocals.wav (as mixtape_v7_stems/ does);
  clip separations from a DIFFERENT model go in a different DIR, so models can be compared by the median capture.
Heavy-ish (HPSS on 4 stems x clips): the default every-5th-clip sample takes ~1 minute on CPU.
"""
import argparse
import glob
import os
import subprocess

import librosa
import numpy as np
from scipy.signal import butter, sosfiltfilt

SR = 22050


def load(path, seconds):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-t", str(seconds), "-"],
                         capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32)


def low_hp(y):
    sos = butter(4, 150, "low", fs=SR, output="sos")
    S = librosa.stft(sosfiltfilt(sos, y), n_fft=4096, hop_length=1024)
    H, P = librosa.decompose.hpss(S, kernel_size=(31, 17))
    return float((np.abs(H) ** 2).sum()), float((np.abs(P) ** 2).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems-root", required=True)
    ap.add_argument("--every", type=int, default=5)
    ap.add_argument("--seconds", type=float, default=40.0)
    a = ap.parse_args()
    dirs = sorted(d for d in glob.glob(os.path.join(a.stems_root, "*")) if os.path.isdir(d))[::a.every]
    caps = []
    print("clip   bass-capture  | harmonic low-band share by stem (bass drums other vocals) | kick = drums percussive share")
    for d in dirs:
        res = {}
        for k in ("bass", "drums", "other", "vocals"):
            f = os.path.join(d, k + ".wav")
            if os.path.exists(f):
                res[k] = low_hp(load(f, a.seconds))
        th = sum(v[0] for v in res.values()) or 1.0
        tot = sum(v[0] + v[1] for v in res.values()) or 1.0
        cap = res.get("bass", (0, 0))[0] / th
        caps.append(cap)
        print(f"{os.path.basename(d):>6} {cap:8.2f}      | " + " ".join(f"{100 * res.get(k, (0, 0))[0] / th:5.1f}%" for k in ("bass", "drums", "other", "vocals"))
              + f" | kick {100 * res.get('drums', (0, 0))[1] / tot:5.1f}%")
    if caps:
        print(f"\nmedian bass capture {np.median(caps):.2f}, min {min(caps):.2f}, max {max(caps):.2f} over {len(caps)} clips "
              f"(suggested bar: median >= 0.60 and min >= 0.30)")


if __name__ == "__main__":
    main()
